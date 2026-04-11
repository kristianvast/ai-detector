import { spawn, spawnSync, type ChildProcessByStdio } from 'node:child_process';
import { existsSync } from 'node:fs';
import { chmod, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import type { Readable } from 'node:stream';
import { error } from '@sveltejs/kit';
import ffmpegStatic from 'ffmpeg-static';
import type { RequestHandler } from './$types';

const MJPEG_BOUNDARY = 'frame';
const FIRST_FRAME_TIMEOUT_MS = 10_000;
const NO_FRAME_TIMEOUT_MS = 8_000;
const FORCE_KILL_DELAY_MS = 2_000;
const MAX_STDERR_TAIL_LENGTH = 4_000;

type Timeout = ReturnType<typeof setTimeout>;
type StreamController = ReadableStreamDefaultController<Uint8Array>;

let cachedFfmpegPath: string | null | undefined;
let ffmpegPathPromise: Promise<string | null> | null = null;

function clearTimer(timer: Timeout | null): null {
	if (timer) {
		clearTimeout(timer);
	}

	return null;
}

function isInvalidControllerState(value: unknown): boolean {
	return (
		value instanceof TypeError && (value as NodeJS.ErrnoException).code === 'ERR_INVALID_STATE'
	);
}

function closeController(controller: StreamController): void {
	try {
		controller.close();
	} catch (value) {
		if (!isInvalidControllerState(value)) {
			throw value;
		}
	}
}

function errorController(controller: StreamController, reason: Error): void {
	try {
		controller.error(reason);
	} catch (value) {
		if (!isInvalidControllerState(value)) {
			throw value;
		}
	}
}

function appendStderrTail(current: string, chunk: Buffer<ArrayBufferLike>): string {
	const next = current + chunk.toString('utf8');
	return next.length > MAX_STDERR_TAIL_LENGTH ? next.slice(-MAX_STDERR_TAIL_LENGTH) : next;
}

function getExecutableName(): string {
	return process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
}

function canResolveCommand(command: string): boolean {
	const probe = spawnSync(command, ['-version'], {
		stdio: ['ignore', 'ignore', 'ignore'],
		windowsHide: true
	});

	return !probe.error && probe.status === 0;
}

async function extractEmbeddedFfmpeg(requestUrl: URL): Promise<string | null> {
	const executableName = getExecutableName();
	const extractionDirectory = path.resolve(tmpdir(), 'ai-detector-web', 'bin');
	const extractedPath = path.resolve(extractionDirectory, executableName);

	if (existsSync(extractedPath)) {
		return extractedPath;
	}

	let assetResponse: Response;

	try {
		assetResponse = await fetch(new URL(`/_internal/${executableName}`, requestUrl));
	} catch {
		return null;
	}

	if (!assetResponse.ok) {
		return null;
	}

	const binaryContent = new Uint8Array(await assetResponse.arrayBuffer());
	if (binaryContent.byteLength === 0) {
		return null;
	}

	await mkdir(extractionDirectory, { recursive: true });
	await writeFile(extractedPath, binaryContent);

	if (process.platform !== 'win32') {
		await chmod(extractedPath, 0o755);
	}

	return extractedPath;
}

async function resolveFfmpegPath(requestUrl: URL): Promise<string | null> {
	const configuredPath = process.env.FFMPEG_PATH?.trim();
	if (configuredPath && (existsSync(configuredPath) || canResolveCommand(configuredPath))) {
		return configuredPath;
	}

	if (typeof ffmpegStatic === 'string' && existsSync(ffmpegStatic)) {
		return ffmpegStatic;
	}

	const executableName = getExecutableName();
	const executableDirectory = path.dirname(process.execPath);
	const candidatePaths = [
		path.resolve(executableDirectory, executableName),
		path.resolve(executableDirectory, 'bin', executableName),
		path.resolve(process.cwd(), executableName),
		path.resolve(process.cwd(), 'bin', executableName)
	];

	for (const candidatePath of candidatePaths) {
		if (existsSync(candidatePath)) {
			return candidatePath;
		}
	}

	const extractedPath = await extractEmbeddedFfmpeg(requestUrl);
	if (extractedPath) {
		return extractedPath;
	}

	return canResolveCommand('ffmpeg') ? 'ffmpeg' : null;
}

async function getFfmpegPathWithFallback(requestUrl: URL): Promise<string | null> {
	if (cachedFfmpegPath !== undefined) {
		return cachedFfmpegPath;
	}

	if (!ffmpegPathPromise) {
		ffmpegPathPromise = resolveFfmpegPath(requestUrl).finally(() => {
			ffmpegPathPromise = null;
		});
	}

	cachedFfmpegPath = await ffmpegPathPromise;
	return cachedFfmpegPath;
}

function getFfmpegArgs(source: string): string[] {
	return [
		'-hide_banner',
		'-loglevel',
		'error',
		'-rtsp_transport',
		'tcp',
		'-i',
		source,
		'-an',
		'-sn',
		'-dn',
		'-c:v',
		'mjpeg',
		'-vf',
		'fps=8,scale=960:-1:flags=lanczos',
		'-q:v',
		'7',
		'-f',
		'mpjpeg',
		'-boundary_tag',
		MJPEG_BOUNDARY,
		'pipe:1'
	];
}

function sanitizeSourceForLogs(source: string): string {
	try {
		const url = new URL(source);
		if (url.username) {
			url.username = '***';
		}
		if (url.password) {
			url.password = '***';
		}
		return url.toString();
	} catch {
		return source;
	}
}

function isRtspSource(source: string): boolean {
	return /^rtsps?:\/\//i.test(source.trim());
}

function createMjpegReadable(
	source: string,
	ffmpegPath: string,
	abortSignal: AbortSignal
): ReadableStream<Uint8Array> {
	let controller: StreamController | null = null;
	let ffmpeg: ChildProcessByStdio<null, Readable, Readable> | null = null;
	let firstFrameTimer: Timeout | null = null;
	let noFrameTimer: Timeout | null = null;
	let forceKillTimer: Timeout | null = null;
	let stderrTail = '';
	let hadFrame = false;
	let finished = false;
	let stopReason: string | null = null;

	function clearTimers(): void {
		firstFrameTimer = clearTimer(firstFrameTimer);
		noFrameTimer = clearTimer(noFrameTimer);
		forceKillTimer = clearTimer(forceKillTimer);
	}

	function finish(reason?: Error): void {
		if (finished) {
			return;
		}

		finished = true;
		clearTimers();
		abortSignal.removeEventListener('abort', onAbort);

		if (!controller) {
			return;
		}

		if (reason) {
			errorController(controller, reason);
			return;
		}

		closeController(controller);
	}

	function stopProcess(signal: NodeJS.Signals = 'SIGTERM', reason?: string): void {
		if (reason && !stopReason) {
			stopReason = reason;
		}

		if (!ffmpeg || ffmpeg.exitCode !== null) {
			return;
		}

		ffmpeg.kill(signal);

		if (signal === 'SIGTERM') {
			forceKillTimer = clearTimer(forceKillTimer);
			forceKillTimer = setTimeout(() => {
				if (ffmpeg && ffmpeg.exitCode === null) {
					ffmpeg.kill('SIGKILL');
				}
			}, FORCE_KILL_DELAY_MS);
		}
	}

	function resetNoFrameTimeout(): void {
		noFrameTimer = clearTimer(noFrameTimer);
		noFrameTimer = setTimeout(() => {
			console.warn('FFmpeg preview stalled after frames stopped', {
				source: sanitizeSourceForLogs(source)
			});
			stopProcess('SIGTERM', 'No frames received before timeout.');
		}, NO_FRAME_TIMEOUT_MS);
	}

	function onAbort(): void {
		stopProcess('SIGTERM', 'Client disconnected.');
		finish();
	}

	return new ReadableStream<Uint8Array>({
		start(streamController) {
			controller = streamController;

			if (abortSignal.aborted) {
				onAbort();
				return;
			}

			abortSignal.addEventListener('abort', onAbort, { once: true });

			const child = spawn(ffmpegPath, getFfmpegArgs(source), {
				stdio: ['ignore', 'pipe', 'pipe'],
				windowsHide: true
			});
			ffmpeg = child;

			firstFrameTimer = setTimeout(() => {
				console.warn('FFmpeg preview stalled before first frame', {
					source: sanitizeSourceForLogs(source)
				});
				stopProcess('SIGTERM', 'No first frame received before timeout.');
			}, FIRST_FRAME_TIMEOUT_MS);

			child.stdout.on('data', (chunk: Buffer<ArrayBufferLike>) => {
				if (finished || !controller) {
					return;
				}

				if (!hadFrame) {
					hadFrame = true;
					firstFrameTimer = clearTimer(firstFrameTimer);
				}

				resetNoFrameTimeout();

				try {
					controller.enqueue(chunk);
				} catch {
					stopProcess('SIGTERM', 'Client could not accept more stream data.');
					finish();
				}
			});

			child.stderr.on('data', (chunk: Buffer<ArrayBufferLike>) => {
				stderrTail = appendStderrTail(stderrTail, chunk);
			});

			child.once('error', (processError) => {
				console.error('FFmpeg preview process error', {
					source: sanitizeSourceForLogs(source),
					error: processError
				});
				finish(new Error('Failed to start live stream preview.'));
			});

			child.once('close', (exitCode, signal) => {
				if (finished) {
					return;
				}

				clearTimers();

				const details = {
					source: sanitizeSourceForLogs(source),
					exitCode: exitCode ?? 'unknown',
					signal: signal ?? undefined,
					hadFrame,
					reason: stopReason ?? undefined,
					stderr: stderrTail.trim() || undefined
				};

				if (!hadFrame) {
					console.warn('FFmpeg preview exited before first frame', details);
					finish(new Error('Live stream unavailable.'));
					return;
				}

				console.warn('FFmpeg preview ended', details);
				finish(new Error('Live stream ended.'));
			});
		},
		cancel() {
			stopProcess('SIGTERM', 'Stream response cancelled.');
			finish();
		}
	});
}

export const GET: RequestHandler = async ({ params, request }) => {
	const source = params.source.trim();
	if (!isRtspSource(source)) {
		throw error(400, 'Only RTSP and RTSPS sources are supported for live preview.');
	}

	const ffmpegPath = await getFfmpegPathWithFallback(new URL(request.url));
	if (!ffmpegPath) {
		const executableName = getExecutableName();
		throw error(
			500,
			`FFmpeg binary not available. Set FFMPEG_PATH, install ffmpeg in PATH, or place ${executableName} next to ${path.basename(process.execPath)}.`
		);
	}

	return new Response(createMjpegReadable(source, ffmpegPath, request.signal), {
		headers: {
			'Content-Type': `multipart/x-mixed-replace; boundary=${MJPEG_BOUNDARY}`,
			'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
			Pragma: 'no-cache',
			Connection: 'keep-alive',
			'X-Accel-Buffering': 'no'
		}
	});
};
