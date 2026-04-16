import 'reflect-metadata';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createSocket, type Socket } from 'node:dgram';
import type { AddressInfo } from 'node:net';
import {
	MediaStreamTrack,
	RTCPeerConnection,
	useH264,
	type RTCSessionDescriptionInit
} from 'werift';
import {
	getExecutableName,
	getFfmpegPathWithFallback,
	getRtspInputArgs,
	isRtspSource,
	sanitizeSourceForLogs,
	sanitizeTextForLogs
} from '$lib/server/ffmpeg';
import {
	WEBRTC_PREVIEW_FIRST_FRAME_TIMEOUT_MS,
	WEBRTC_PREVIEW_FORCE_KILL_DELAY_MS,
	WEBRTC_PREVIEW_H264_PAYLOAD_TYPE,
	WEBRTC_PREVIEW_ICE_GATHERING_TIMEOUT_MS,
	WEBRTC_PREVIEW_ICE_SERVERS,
	WEBRTC_PREVIEW_MAX_WIDTH,
	WEBRTC_PREVIEW_NO_FRAME_TIMEOUT_MS,
	WEBRTC_PREVIEW_RECONNECT_DELAY_MS,
	WEBRTC_PREVIEW_RTP_PACKET_SIZE,
	WEBRTC_PREVIEW_SESSION_IDLE_TIMEOUT_MS
} from '$lib/streams/webrtc-preview-config';

const MAX_STDERR_TAIL_LENGTH = 4_000;
const MAX_RESTART_DELAY_MS = 30_000;

type Timeout = ReturnType<typeof setTimeout>;
type TrackSink = {
	track: MediaStreamTrack;
	onPacket: () => void;
};
type SessionSource = {
	source: string;
	relay: SourceRelay;
	track: MediaStreamTrack;
	unsubscribe: () => void;
	hadFrame: boolean;
	firstFrameTimer: Timeout | null;
	noFrameTimer: Timeout | null;
};

declare global {
	// eslint-disable-next-line no-var
	var __aiDetectorWebRtcPreviewSessions: Map<string, PreviewSession> | undefined;
	// eslint-disable-next-line no-var
	var __aiDetectorWebRtcPreviewRelays: Map<string, SourceRelay> | undefined;
}

const sessions = globalThis.__aiDetectorWebRtcPreviewSessions ?? new Map<string, PreviewSession>();
const relays = globalThis.__aiDetectorWebRtcPreviewRelays ?? new Map<string, SourceRelay>();
globalThis.__aiDetectorWebRtcPreviewSessions = sessions;
globalThis.__aiDetectorWebRtcPreviewRelays = relays;

export class PreviewSessionError extends Error {
	constructor(
		readonly status: number,
		message: string
	) {
		super(message);
	}
}

const clearTimer = (timer: Timeout | null) => {
	if (timer) {
		clearTimeout(timer);
	}
	return null;
};

const normalizeSources = (sources: string[]) =>
	[...new Set(sources.map((source) => source.trim()).filter(Boolean))];

function appendStderrTail(stderr: string, chunk: Buffer<ArrayBufferLike>) {
	const next = stderr + chunk.toString('utf8');
	return next.length > MAX_STDERR_TAIL_LENGTH ? next.slice(-MAX_STDERR_TAIL_LENGTH) : next;
}

function bindSocket(socket: Socket) {
	return new Promise<number>((resolve, reject) => {
		const cleanup = () => {
			socket.off('error', onError);
			socket.off('listening', onListening);
		};
		const onError = (error: Error) => {
			cleanup();
			reject(error);
		};
		const onListening = () => {
			cleanup();
			resolve((socket.address() as AddressInfo).port);
		};

		socket.once('error', onError);
		socket.once('listening', onListening);
		socket.bind(0, '127.0.0.1');
	});
}

async function waitForIceGatheringComplete(pc: RTCPeerConnection) {
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

class SourceRelay {
	socket!: Socket;
	port = 0;
	ffmpeg: ReturnType<typeof spawn> | null = null;
	stderr = '';
	hadFrame = false;
	disposed = false;
	restartDelay = WEBRTC_PREVIEW_RECONNECT_DELAY_MS;
	idleTimer: Timeout | null = null;
	killTimer: Timeout | null = null;
	restartTimer: Timeout | null = null;
	readonly subscribers = new Set<TrackSink>();

	constructor(
		readonly source: string,
		readonly ffmpegPath: string
	) { }

	static async create(source: string, ffmpegPath: string) {
		const relay = new SourceRelay(source, ffmpegPath);
		relay.socket = createSocket('udp4');
		relay.socket.on('message', (packet) => relay.send(packet));
		relay.socket.on('error', (error) => {
			console.error('WebRTC preview RTP socket error', {
				source: sanitizeSourceForLogs(source),
				error
			});
			relay.dispose();
		});
		relay.port = await bindSocket(relay.socket);
		return relay;
	}

	subscribe(sink: TrackSink) {
		this.subscribers.add(sink);
		this.idleTimer = clearTimer(this.idleTimer);
		this.start();

		return () => {
			this.subscribers.delete(sink);
			if (this.subscribers.size === 0) {
				this.idleTimer = setTimeout(() => this.dispose(), WEBRTC_PREVIEW_SESSION_IDLE_TIMEOUT_MS);
			}
		};
	}

	start() {
		if (this.disposed || this.ffmpeg || this.subscribers.size === 0) {
			return;
		}

		this.restartTimer = clearTimer(this.restartTimer);
		this.stderr = '';
		this.hadFrame = false;
		this.ffmpeg = spawn(this.ffmpegPath, this.args(), {
			stdio: ['ignore', 'ignore', 'pipe'],
			windowsHide: true
		});

		this.ffmpeg.stderr?.on('data', (chunk: Buffer<ArrayBufferLike>) => {
			this.stderr = appendStderrTail(this.stderr, chunk);
		});

		this.ffmpeg.once('error', (error) => {
			console.error('WebRTC preview FFmpeg process error', {
				source: sanitizeSourceForLogs(this.source),
				error
			});
		});

		this.ffmpeg.once('close', (exitCode, signal) => {
			if (this.disposed) {
				return;
			}

			this.ffmpeg = null;
			this.killTimer = clearTimer(this.killTimer);
			const failed = exitCode !== 0 && exitCode !== null;
			console.warn(
				!failed && this.hadFrame
					? 'WebRTC preview source FFmpeg ended'
					: 'WebRTC preview source FFmpeg exited before first frame',
				{
					source: sanitizeSourceForLogs(this.source),
					exitCode: exitCode ?? 'unknown',
					signal: signal ?? undefined,
					stderr: this.stderr.trim() ? sanitizeTextForLogs(this.stderr.trim()) : undefined
				}
			);

			if (this.subscribers.size > 0) {
				this.restartTimer = setTimeout(() => this.start(), this.restartDelay);
				this.restartDelay = Math.min(this.restartDelay * 2, MAX_RESTART_DELAY_MS);
			}
		});
	}

	send(packet: Buffer) {
		this.hadFrame = true;
		this.restartDelay = WEBRTC_PREVIEW_RECONNECT_DELAY_MS;

		for (const sink of this.subscribers) {
			try {
				sink.track.writeRtp(Buffer.from(packet));
				sink.onPacket();
			} catch (error) {
				this.subscribers.delete(sink);
				console.warn('WebRTC preview failed to write RTP packet to subscriber', {
					source: sanitizeSourceForLogs(this.source),
					error
				});
			}
		}
	}

	dispose() {
		if (this.disposed) {
			return;
		}

		this.disposed = true;
		relays.delete(this.source);
		this.idleTimer = clearTimer(this.idleTimer);
		this.killTimer = clearTimer(this.killTimer);
		this.restartTimer = clearTimer(this.restartTimer);
		this.subscribers.clear();

		if (this.ffmpeg && this.ffmpeg.exitCode === null) {
			try {
				this.ffmpeg.kill('SIGKILL');
			} catch {
				// Process may already be gone.
			}
		}

		try {
			this.socket.close();
		} catch {
			// Socket may already be closed.
		}
	}

	private args() {
		return [
			'-hide_banner',
			'-loglevel',
			'error',
			'-nostdin',
			...getRtspInputArgs(this.source),
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
			`rtp://127.0.0.1:${this.port}?pkt_size=${WEBRTC_PREVIEW_RTP_PACKET_SIZE}`
		];
	}
}

async function getRelay(source: string, ffmpegPath: string) {
	const existing = relays.get(source);
	if (existing) {
		return existing;
	}

	const relay = await SourceRelay.create(source, ffmpegPath);
	relays.set(source, relay);
	return relay;
}

class PreviewSession {
	readonly id = randomUUID();
	cleanupTimer: Timeout | null = null;
	closed = false;

	constructor(
		readonly pc: RTCPeerConnection,
		readonly sources: SessionSource[]
	) {
		this.pc.connectionStateChange.subscribe((state) => {
			if (this.closed) {
				return;
			}

			if (state === 'new' || state === 'connecting' || state === 'connected') {
				this.cleanupTimer = clearTimer(this.cleanupTimer);
				return;
			}

			if (state === 'disconnected') {
				this.cleanupTimer = clearTimer(this.cleanupTimer);
				this.cleanupTimer = setTimeout(() => {
					void destroyPreviewSession(this.id);
				}, WEBRTC_PREVIEW_SESSION_IDLE_TIMEOUT_MS);
				return;
			}

			void destroyPreviewSession(this.id);
		});
	}

	static async create(input: {
		offer: RTCSessionDescriptionInit;
		sources: string[];
		ffmpegPath: string;
	}) {
		const pc = new RTCPeerConnection({
			codecs: {
				video: [useH264({ payloadType: WEBRTC_PREVIEW_H264_PAYLOAD_TYPE })]
			},
			iceServers: [...WEBRTC_PREVIEW_ICE_SERVERS]
		});
		const sources: SessionSource[] = [];

		try {
			for (const source of input.sources) {
				const track = new MediaStreamTrack({ kind: 'video' });
				track.streamId = randomUUID();
				sources.push({
					source,
					relay: await getRelay(source, input.ffmpegPath),
					track,
					unsubscribe: () => { },
					hadFrame: false,
					firstFrameTimer: null,
					noFrameTimer: null
				});
				pc.addTrack(track);
			}

			await pc.setRemoteDescription(input.offer);
			const answer = await pc.createAnswer();
			await pc.setLocalDescription(answer);
			await waitForIceGatheringComplete(pc);

			return {
				session: new PreviewSession(pc, sources),
				answer: {
					type: pc.localDescription?.type ?? answer.type,
					sdp: pc.localDescription?.sdp ?? answer.sdp
				}
			};
		} catch (error) {
			for (const source of sources) {
				source.unsubscribe();
				source.track.stop();
			}

			try {
				await pc.close();
			} catch {
				// Ignore peer cleanup errors while failing setup.
			}

			throw error;
		}
	}

	start() {
		for (const source of this.sources) {
			source.firstFrameTimer = setTimeout(() => {
				console.warn('WebRTC preview source stalled before first frame', {
					source: sanitizeSourceForLogs(source.source)
				});
			}, WEBRTC_PREVIEW_FIRST_FRAME_TIMEOUT_MS);
			source.unsubscribe = source.relay.subscribe({
				track: source.track,
				onPacket: () => this.handlePacket(source)
			});
		}
	}

	handlePacket(source: SessionSource) {
		if (this.closed) {
			return;
		}

		if (!source.hadFrame) {
			source.hadFrame = true;
			source.firstFrameTimer = clearTimer(source.firstFrameTimer);
		}

		source.noFrameTimer = clearTimer(source.noFrameTimer);
		source.noFrameTimer = setTimeout(() => {
			console.warn('WebRTC preview source stalled after frames stopped', {
				source: sanitizeSourceForLogs(source.source)
			});
		}, WEBRTC_PREVIEW_NO_FRAME_TIMEOUT_MS);
	}

	async close() {
		if (this.closed) {
			return;
		}

		this.closed = true;
		this.cleanupTimer = clearTimer(this.cleanupTimer);

		for (const source of this.sources) {
			source.firstFrameTimer = clearTimer(source.firstFrameTimer);
			source.noFrameTimer = clearTimer(source.noFrameTimer);
			source.unsubscribe();
			source.track.stop();
		}

		try {
			await this.pc.close();
		} catch {
			// Ignore peer cleanup errors during shutdown.
		}
	}
}

export async function createPreviewSession(input: {
	offer: RTCSessionDescriptionInit;
	sources: string[];
	requestUrl: URL;
}): Promise<{ sessionId: string; answer: RTCSessionDescriptionInit }> {
	if (input.offer.type !== 'offer' || !input.offer.sdp?.trim()) {
		throw new PreviewSessionError(400, 'Expected a valid WebRTC offer.');
	}

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
		session.start();
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
