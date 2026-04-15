import 'reflect-metadata';
import { randomUUID } from 'node:crypto';
import { spawn, type ChildProcessByStdio } from 'node:child_process';
import type { Readable } from 'node:stream';
import {
	MediaStreamTrack,
	MediaStreamTrackFactory,
	RTCPeerConnection,
	useH264,
	type RTCSessionDescriptionInit
} from 'werift';
import {
	getExecutableName,
	getFfmpegPathWithFallback,
	getRtspInputArgs,
	isRtspSource,
	sanitizeSourceForLogs
} from '$lib/server/ffmpeg';
import {
	WEBRTC_PREVIEW_FIRST_FRAME_TIMEOUT_MS,
	WEBRTC_PREVIEW_FORCE_KILL_DELAY_MS,
	WEBRTC_PREVIEW_H264_PAYLOAD_TYPE,
	WEBRTC_PREVIEW_ICE_GATHERING_TIMEOUT_MS,
	WEBRTC_PREVIEW_ICE_SERVERS,
	WEBRTC_PREVIEW_MAX_WIDTH,
	WEBRTC_PREVIEW_NO_FRAME_TIMEOUT_MS,
	WEBRTC_PREVIEW_RTP_PACKET_SIZE,
	WEBRTC_PREVIEW_SESSION_IDLE_TIMEOUT_MS
} from '$lib/streams/webrtc-preview-config';

const MAX_STDERR_TAIL_LENGTH = 4_000;

type Timeout = ReturnType<typeof setTimeout>;

declare global {
	// eslint-disable-next-line no-var
	var __aiDetectorWebRtcPreviewSessions: Map<string, PreviewSession> | undefined;
}

const sessions = globalThis.__aiDetectorWebRtcPreviewSessions ?? new Map<string, PreviewSession>();
globalThis.__aiDetectorWebRtcPreviewSessions = sessions;

export class PreviewSessionError extends Error {
	status: number;

	constructor(status: number, message: string) {
		super(message);
		this.status = status;
	}
}

function clearTimer(timer: Timeout | null): null {
	if (timer) {
		clearTimeout(timer);
	}

	return null;
}

function appendStderrTail(current: string, chunk: Buffer<ArrayBufferLike>): string {
	const next = current + chunk.toString('utf8');
	return next.length > MAX_STDERR_TAIL_LENGTH ? next.slice(-MAX_STDERR_TAIL_LENGTH) : next;
}

function normalizeSources(sources: string[]): string[] {
	const uniqueSources = new Set<string>();

	for (const source of sources) {
		const normalizedSource = source.trim();
		if (!normalizedSource) {
			continue;
		}

		uniqueSources.add(normalizedSource);
	}

	return [...uniqueSources];
}

function getWebRtcFfmpegArgs(source: string, port: number): string[] {
	return [
		'-hide_banner',
		'-loglevel',
		'error',
		...getRtspInputArgs(source),
		'-an',
		'-sn',
		'-dn',
		'-c:v',
		'libx264',
		'-preset',
		'ultrafast',
		'-tune',
		'zerolatency',
		'-profile:v',
		'baseline',
		'-pix_fmt',
		'yuv420p',
		'-g',
		'30',
		'-keyint_min',
		'30',
		'-sc_threshold',
		'0',
		'-x264-params',
		'repeat-headers=1:aud=1',
		'-vf',
		`scale=w='min(${WEBRTC_PREVIEW_MAX_WIDTH},iw)':h=-2:force_original_aspect_ratio=decrease:flags=lanczos`,
		'-payload_type',
		String(WEBRTC_PREVIEW_H264_PAYLOAD_TYPE),
		'-f',
		'rtp',
		`rtp://127.0.0.1:${port}?pkt_size=${WEBRTC_PREVIEW_RTP_PACKET_SIZE}`
	];
}

async function waitForIceGatheringComplete(pc: RTCPeerConnection): Promise<void> {
	if (pc.iceGatheringState === 'complete') {
		return;
	}

	try {
		await pc.iceGatheringStateChange.watch(
			(state) => state === 'complete',
			WEBRTC_PREVIEW_ICE_GATHERING_TIMEOUT_MS
		);
	} catch {
		throw new PreviewSessionError(
			504,
			'WebRTC signaling timed out while gathering ICE candidates.'
		);
	}
}

function normalizeDescription(
	description: RTCSessionDescriptionInit | undefined,
	fallback: RTCSessionDescriptionInit
): RTCSessionDescriptionInit {
	return {
		type: description?.type ?? fallback.type,
		sdp: description?.sdp ?? fallback.sdp
	};
}

function validateSessionDescription(description: RTCSessionDescriptionInit): void {
	if (description.type !== 'offer' || !description.sdp?.trim()) {
		throw new PreviewSessionError(400, 'Expected a valid WebRTC offer.');
	}
}

class SourcePipeline {
	static async create(source: string, ffmpegPath: string): Promise<SourcePipeline> {
		const pipeline = new SourcePipeline(source, ffmpegPath);
		const [track, port, disposeTrackInput] = await MediaStreamTrackFactory.rtpSource({
			kind: 'video',
			cb: (packet) => {
				pipeline.handleIncomingPacket();
				return packet;
			}
		});

		track.streamId = randomUUID();
		pipeline.track = track;
		pipeline.port = port;
		pipeline.disposeTrackInput = disposeTrackInput;

		return pipeline;
	}

	readonly source: string;
	readonly ffmpegPath: string;
	track!: MediaStreamTrack;
	port!: number;
	ffmpeg: ChildProcessByStdio<null, null, Readable> | null = null;
	firstFrameTimer: Timeout | null = null;
	noFrameTimer: Timeout | null = null;
	forceKillTimer: Timeout | null = null;
	stderrTail = '';
	hadFrame = false;
	disposed = false;
	stopReason: string | null = null;

	private disposeTrackInput: () => void = () => { };

	private constructor(source: string, ffmpegPath: string) {
		this.source = source;
		this.ffmpegPath = ffmpegPath;
	}

	start(): void {
		if (this.disposed || this.ffmpeg) {
			return;
		}

		const child = spawn(this.ffmpegPath, getWebRtcFfmpegArgs(this.source, this.port), {
			stdio: ['ignore', 'ignore', 'pipe'],
			windowsHide: true
		});
		this.ffmpeg = child;
		this.firstFrameTimer = setTimeout(() => {
			console.warn('WebRTC preview source stalled before first frame', {
				source: sanitizeSourceForLogs(this.source)
			});
			this.stop('No first frame received before timeout.');
		}, WEBRTC_PREVIEW_FIRST_FRAME_TIMEOUT_MS);

		child.stderr.on('data', (chunk: Buffer<ArrayBufferLike>) => {
			this.stderrTail = appendStderrTail(this.stderrTail, chunk);
		});

		child.once('error', (processError) => {
			console.error('WebRTC preview FFmpeg process error', {
				source: sanitizeSourceForLogs(this.source),
				error: processError
			});
			this.dispose();
		});

		child.once('close', (exitCode, signal) => {
			if (this.disposed) {
				return;
			}

			this.clearTimers();

			const details = {
				source: sanitizeSourceForLogs(this.source),
				exitCode: exitCode ?? 'unknown',
				signal: signal ?? undefined,
				hadFrame: this.hadFrame,
				reason: this.stopReason ?? undefined,
				stderr: this.stderrTail.trim() || undefined
			};

			if (!this.hadFrame) {
				console.warn('WebRTC preview source exited before first frame', details);
			} else {
				console.warn('WebRTC preview source ended', details);
			}

			this.dispose();
		});
	}

	stop(reason?: string): void {
		if (reason && !this.stopReason) {
			this.stopReason = reason;
		}

		this.firstFrameTimer = clearTimer(this.firstFrameTimer);
		this.noFrameTimer = clearTimer(this.noFrameTimer);

		if (!this.ffmpeg || this.ffmpeg.exitCode !== null) {
			this.dispose();
			return;
		}

		this.ffmpeg.kill('SIGTERM');
		this.forceKillTimer = clearTimer(this.forceKillTimer);
		this.forceKillTimer = setTimeout(() => {
			if (this.ffmpeg && this.ffmpeg.exitCode === null) {
				this.ffmpeg.kill('SIGKILL');
			}
		}, WEBRTC_PREVIEW_FORCE_KILL_DELAY_MS);
	}

	dispose(): void {
		if (this.disposed) {
			return;
		}

		this.disposed = true;
		this.clearTimers();
		this.disposeTrackInput();

		if (!this.track.stopped) {
			this.track.stop();
		}

		if (this.ffmpeg && this.ffmpeg.exitCode === null) {
			try {
				this.ffmpeg.kill('SIGKILL');
			} catch {
				// Process may already be gone.
			}
		}

		this.ffmpeg = null;
	}

	private clearTimers(): void {
		this.firstFrameTimer = clearTimer(this.firstFrameTimer);
		this.noFrameTimer = clearTimer(this.noFrameTimer);
		this.forceKillTimer = clearTimer(this.forceKillTimer);
	}

	private handleIncomingPacket(): void {
		if (this.disposed) {
			return;
		}

		if (!this.hadFrame) {
			this.hadFrame = true;
			this.firstFrameTimer = clearTimer(this.firstFrameTimer);
		}

		this.noFrameTimer = clearTimer(this.noFrameTimer);
		this.noFrameTimer = setTimeout(() => {
			console.warn('WebRTC preview source stalled after frames stopped', {
				source: sanitizeSourceForLogs(this.source)
			});
			this.stop('No frames received before timeout.');
		}, WEBRTC_PREVIEW_NO_FRAME_TIMEOUT_MS);
	}
}

class PreviewSession {
	static async create(input: {
		offer: RTCSessionDescriptionInit;
		sources: string[];
		ffmpegPath: string;
	}): Promise<{ session: PreviewSession; answer: RTCSessionDescriptionInit }> {
		const pipelines = await Promise.all(
			input.sources.map((source) => SourcePipeline.create(source, input.ffmpegPath))
		);
		const pc = new RTCPeerConnection({
			codecs: {
				video: [useH264({ payloadType: WEBRTC_PREVIEW_H264_PAYLOAD_TYPE })]
			},
			iceServers: [...WEBRTC_PREVIEW_ICE_SERVERS]
		});
		const session = new PreviewSession(pc, pipelines);

		for (const pipeline of pipelines) {
			pc.addTrack(pipeline.track);
		}

		await pc.setRemoteDescription(input.offer);
		const answer = await pc.createAnswer();
		await pc.setLocalDescription(answer);
		await waitForIceGatheringComplete(pc);

		for (const pipeline of pipelines) {
			pipeline.start();
		}

		return {
			session,
			answer: normalizeDescription(pc.localDescription, answer)
		};
	}

	readonly id = randomUUID();
	readonly pc: RTCPeerConnection;
	readonly pipelines: SourcePipeline[];
	cleanupTimer: Timeout | null = null;
	closed = false;

	constructor(pc: RTCPeerConnection, pipelines: SourcePipeline[]) {
		this.pc = pc;
		this.pipelines = pipelines;
		this.attachLifecycle();
	}

	async close(): Promise<void> {
		if (this.closed) {
			return;
		}

		this.closed = true;
		this.clearCleanupTimer();

		for (const pipeline of this.pipelines) {
			pipeline.stop('Preview session closed.');
			pipeline.dispose();
		}

		try {
			await this.pc.close();
		} catch {
			// Ignore peer cleanup errors during shutdown.
		}
	}

	private attachLifecycle(): void {
		this.pc.connectionStateChange.subscribe((state) => {
			if (this.closed) {
				return;
			}

			if (state === 'connected' || state === 'connecting' || state === 'new') {
				this.clearCleanupTimer();
				return;
			}

			if (state === 'disconnected') {
				this.clearCleanupTimer();
				this.cleanupTimer = setTimeout(() => {
					void destroyPreviewSession(this.id);
				}, WEBRTC_PREVIEW_SESSION_IDLE_TIMEOUT_MS);
				return;
			}

			void destroyPreviewSession(this.id);
		});
	}

	private clearCleanupTimer(): void {
		this.cleanupTimer = clearTimer(this.cleanupTimer);
	}
}

export async function createPreviewSession(input: {
	offer: RTCSessionDescriptionInit;
	sources: string[];
	requestUrl: URL;
}): Promise<{ sessionId: string; answer: RTCSessionDescriptionInit }> {
	validateSessionDescription(input.offer);

	const sources = normalizeSources(input.sources);
	if (sources.length === 0) {
		throw new PreviewSessionError(400, 'Select at least one RTSP source for preview.');
	}

	for (const source of sources) {
		if (!isRtspSource(source)) {
			throw new PreviewSessionError(400, 'Only RTSP and RTSPS sources are supported for preview.');
		}
	}

	const ffmpegPath = await getFfmpegPathWithFallback(input.requestUrl);
	if (!ffmpegPath) {
		throw new PreviewSessionError(
			500,
			`FFmpeg binary not available. Set FFMPEG_PATH, install ffmpeg in PATH, or place ${getExecutableName()} next to ${process.execPath.split(/[\\\\/]/).pop()}.`
		);
	}

	const { session, answer } = await PreviewSession.create({
		offer: input.offer,
		sources,
		ffmpegPath
	});
	sessions.set(session.id, session);

	try {
		return {
			sessionId: session.id,
			answer
		};
	} catch (error) {
		await destroyPreviewSession(session.id);
		throw error;
	}
}

export async function destroyPreviewSession(sessionId: string): Promise<void> {
	const session = sessions.get(sessionId);
	if (!session) {
		return;
	}

	sessions.delete(sessionId);
	await session.close();
}
