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
const IDLE_KILL_DELAY_MS = 3_000;
const FORCE_KILL_DELAY_MS = 2_000;
const FIRST_FRAME_TIMEOUT_MS = 10_000;
const NO_FRAME_TIMEOUT_MS = 15_000;
const MAX_BLOCKED_FRAMES = 240;
const MAX_SUBSCRIBERS_PER_STREAM = 4;
const MAX_TOTAL_SUBSCRIBERS = 16;
const MAX_STDERR_TAIL_LENGTH = 4_000;
const RESTART_DELAYS_MS = [1_000, 2_000, 5_000, 10_000] as const;
const WORKER_REGISTRY_KEY = '__ai_detector_stream_workers__';

type Timeout = ReturnType<typeof setTimeout>;
type StreamController = ReadableStreamDefaultController<Uint8Array>;

interface StreamSubscriber {
	controller: StreamController;
	blockedFrames: number;
	detach: () => void;
}

interface StreamWorker {
	source: string;
	ffmpegPath: string;
	ffmpeg: ChildProcessByStdio<null, Readable, Readable> | null;
	subscribers: Set<StreamSubscriber>;
	idleKillTimer: Timeout | null;
	forceKillTimer: Timeout | null;
	firstFrameTimer: Timeout | null;
	noFrameTimer: Timeout | null;
	restartTimer: Timeout | null;
	restartDelayMs: number;
	stopRequested: boolean;
	hadFrameThisRun: boolean;
	stderrTail: string;
}

type GlobalWorkerRegistry = typeof globalThis & {
	[WORKER_REGISTRY_KEY]?: Map<string, StreamWorker>;
};

const globalWorkerRegistry = globalThis as GlobalWorkerRegistry;
const workers =
	globalWorkerRegistry[WORKER_REGISTRY_KEY] ??
	(globalWorkerRegistry[WORKER_REGISTRY_KEY] = new Map<string, StreamWorker>());

let cachedFfmpegPath: string | null | undefined;
let ffmpegPathPromise: Promise<string | null> | null = null;

function clearTimer(timer: Timeout | null): null {
	if (timer) {
		clearTimeout(timer);
	}
	return null;
}

function nextRestartDelay(current: number): number {
	for (const delay of RESTART_DELAYS_MS) {
		if (delay > current) {
			return delay;
		}
	}
	return RESTART_DELAYS_MS[RESTART_DELAYS_MS.length - 1];
}

function canResolveCommand(command: string): boolean {
	const probe = spawnSync(command, ['-version'], {
		stdio: ['ignore', 'ignore', 'ignore'],
		windowsHide: true
	});
	return !probe.error;
}

function getExecutableName(): string {
	return process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
}

async function extractEmbeddedFfmpeg(requestUrl: URL): Promise<string | null> {
	const executableName = getExecutableName();
	const extractionDirectory = path.resolve(tmpdir(), 'ai-detector-web', 'bin');
	const extractedPath = path.resolve(extractionDirectory, executableName);

	if (existsSync(extractedPath)) {
		return extractedPath;
	}

	const assetUrl = new URL(`/_internal/${executableName}`, requestUrl);
	let assetResponse: Response;

	try {
		assetResponse = await fetch(assetUrl);
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

	if (ffmpegStatic && existsSync(ffmpegStatic)) {
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

async function getFfmpegPath(requestUrl: URL): Promise<string | null> {
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

function isInvalidControllerState(error: unknown): boolean {
	return (
		error instanceof TypeError && (error as NodeJS.ErrnoException).code === 'ERR_INVALID_STATE'
	);
}

function closeController(controller: StreamController): void {
	try {
		controller.close();
	} catch (error) {
		if (!isInvalidControllerState(error)) {
			throw error;
		}
	}
}

function errorController(controller: StreamController, reason: Error): void {
	try {
		controller.error(reason);
	} catch (error) {
		if (!isInvalidControllerState(error)) {
			throw error;
		}
	}
}

function clearProcessTimers(worker: StreamWorker): void {
	worker.firstFrameTimer = clearTimer(worker.firstFrameTimer);
	worker.noFrameTimer = clearTimer(worker.noFrameTimer);
	worker.forceKillTimer = clearTimer(worker.forceKillTimer);
}

function appendStderrTail(current: string, chunk: Buffer<ArrayBufferLike>): string {
	const next = current + chunk.toString('utf8');
	return next.length > MAX_STDERR_TAIL_LENGTH ? next.slice(-MAX_STDERR_TAIL_LENGTH) : next;
}

function countActiveSubscribers(): number {
	let total = 0;
	for (const worker of workers.values()) {
		total += worker.subscribers.size;
	}
	return total;
}

function closeSubscribers(worker: StreamWorker): void {
	const subscribers = Array.from(worker.subscribers);
	worker.subscribers.clear();

	for (const subscriber of subscribers) {
		subscriber.detach();
		closeController(subscriber.controller);
	}
}

function scheduleIdleKill(worker: StreamWorker): void {
	if (worker.stopRequested || worker.subscribers.size > 0 || worker.idleKillTimer) {
		return;
	}

	worker.idleKillTimer = setTimeout(() => {
		worker.idleKillTimer = null;
		if (worker.subscribers.size === 0) {
			destroyWorker(worker.source);
		}
	}, IDLE_KILL_DELAY_MS);
}

function removeSubscriber(
	worker: StreamWorker,
	subscriber: StreamSubscriber,
	options: { close?: boolean } = {}
): void {
	worker.subscribers.delete(subscriber);
	subscriber.detach();

	if (options.close) {
		closeController(subscriber.controller);
	}

	scheduleIdleKill(worker);
}

function broadcastFrame(worker: StreamWorker, chunk: Buffer<ArrayBufferLike>): void {
	for (const subscriber of Array.from(worker.subscribers)) {
		if (subscriber.controller.desiredSize !== null && subscriber.controller.desiredSize <= 0) {
			subscriber.blockedFrames += 1;
			if (subscriber.blockedFrames >= MAX_BLOCKED_FRAMES) {
				removeSubscriber(worker, subscriber, { close: true });
			}
			continue;
		}

		subscriber.blockedFrames = 0;

		try {
			subscriber.controller.enqueue(chunk);
		} catch (enqueueError) {
			if (!isInvalidControllerState(enqueueError)) {
				console.error('Live stream subscriber enqueue failed', enqueueError);
			}
			removeSubscriber(worker, subscriber);
		}
	}
}

function stopProcess(worker: StreamWorker, signal: NodeJS.Signals = 'SIGTERM'): void {
	const ffmpeg = worker.ffmpeg;
	if (!ffmpeg) {
		return;
	}

	clearProcessTimers(worker);
	ffmpeg.kill(signal);

	if (signal === 'SIGTERM') {
		worker.forceKillTimer = setTimeout(() => {
			if (worker.ffmpeg === ffmpeg) {
				ffmpeg.kill('SIGKILL');
			}
		}, FORCE_KILL_DELAY_MS);
	}
}

function scheduleRestart(worker: StreamWorker, reason: string): void {
	if (worker.stopRequested || worker.restartTimer || worker.ffmpeg) {
		return;
	}

	if (worker.subscribers.size === 0) {
		destroyWorker(worker.source);
		return;
	}

	const delay = worker.restartDelayMs;
	const stderr = worker.stderrTail.trim();

	console.warn('Restarting FFmpeg preview', {
		source: worker.source,
		reason,
		delay,
		stderr: stderr || undefined
	});

	worker.restartTimer = setTimeout(() => {
		worker.restartTimer = null;

		if (worker.stopRequested) {
			return;
		}

		if (worker.subscribers.size === 0) {
			destroyWorker(worker.source);
			return;
		}

		startProcess(worker);
	}, delay);

	worker.restartDelayMs = nextRestartDelay(delay);
}

function releaseProcess(
	worker: StreamWorker,
	ffmpeg: ChildProcessByStdio<null, Readable, Readable>
): boolean {
	if (worker.ffmpeg !== ffmpeg) {
		return false;
	}

	worker.ffmpeg = null;
	clearProcessTimers(worker);
	return true;
}

function startProcess(worker: StreamWorker): void {
	if (worker.stopRequested || worker.ffmpeg || worker.subscribers.size === 0) {
		return;
	}

	worker.hadFrameThisRun = false;
	worker.stderrTail = '';

	const ffmpeg = spawn(worker.ffmpegPath, getFfmpegArgs(worker.source), {
		stdio: ['ignore', 'pipe', 'pipe']
	});

	worker.ffmpeg = ffmpeg;

	worker.firstFrameTimer = setTimeout(() => {
		if (worker.ffmpeg !== ffmpeg || worker.stopRequested) {
			return;
		}

		console.warn('FFmpeg preview stalled before first frame', { source: worker.source });
		stopProcess(worker);
	}, FIRST_FRAME_TIMEOUT_MS);

	ffmpeg.stdout.on('data', (chunk) => {
		if (worker.ffmpeg !== ffmpeg || worker.stopRequested) {
			return;
		}

		if (!worker.hadFrameThisRun) {
			worker.hadFrameThisRun = true;
			worker.restartDelayMs = RESTART_DELAYS_MS[0];
			worker.firstFrameTimer = clearTimer(worker.firstFrameTimer);
		}

		worker.noFrameTimer = clearTimer(worker.noFrameTimer);
		worker.noFrameTimer = setTimeout(() => {
			if (worker.ffmpeg !== ffmpeg || worker.stopRequested) {
				return;
			}

			console.warn('FFmpeg preview stalled after frames stopped', { source: worker.source });
			stopProcess(worker);
		}, NO_FRAME_TIMEOUT_MS);

		broadcastFrame(worker, chunk);
	});

	ffmpeg.stderr?.on('data', (chunk) => {
		if (worker.ffmpeg === ffmpeg) {
			worker.stderrTail = appendStderrTail(worker.stderrTail, chunk);
		}
	});

	ffmpeg.once('error', (processError) => {
		if (!releaseProcess(worker, ffmpeg)) {
			return;
		}

		console.error('FFmpeg process error', { source: worker.source, error: processError });

		if (!worker.stopRequested) {
			scheduleRestart(worker, 'process error');
		}
	});

	ffmpeg.once('close', (exitCode) => {
		if (!releaseProcess(worker, ffmpeg)) {
			return;
		}

		if (worker.stopRequested) {
			return;
		}

		const reason = exitCode === 0 ? 'process closed' : `exit code ${exitCode ?? 'unknown'}`;

		console.warn('FFmpeg preview exited', {
			source: worker.source,
			exitCode: exitCode ?? 'unknown',
			hadFrameThisRun: worker.hadFrameThisRun,
			stderr: worker.stderrTail.trim() || undefined
		});

		scheduleRestart(worker, reason);
	});
}

function createWorker(source: string, ffmpegPath: string): StreamWorker {
	return {
		source,
		ffmpegPath,
		ffmpeg: null,
		subscribers: new Set(),
		idleKillTimer: null,
		forceKillTimer: null,
		firstFrameTimer: null,
		noFrameTimer: null,
		restartTimer: null,
		restartDelayMs: RESTART_DELAYS_MS[0],
		stopRequested: false,
		hadFrameThisRun: false,
		stderrTail: ''
	};
}

function getOrCreateWorker(source: string, ffmpegPath: string): StreamWorker {
	const existing = workers.get(source);
	if (existing) {
		return existing;
	}

	const worker = createWorker(source, ffmpegPath);
	workers.set(source, worker);
	return worker;
}

function destroyWorker(source: string): void {
	const worker = workers.get(source);
	if (!worker) {
		return;
	}

	workers.delete(source);
	worker.stopRequested = true;
	worker.idleKillTimer = clearTimer(worker.idleKillTimer);
	worker.restartTimer = clearTimer(worker.restartTimer);
	closeSubscribers(worker);
	stopProcess(worker);
}

function attachSubscriber(
	source: string,
	ffmpegPath: string,
	controller: StreamController,
	abortSignal: AbortSignal
): () => void {
	const current = workers.get(source);

	if ((current?.subscribers.size ?? 0) >= MAX_SUBSCRIBERS_PER_STREAM) {
		errorController(controller, new Error('Too many live viewers for this stream.'));
		return () => {};
	}

	if (countActiveSubscribers() >= MAX_TOTAL_SUBSCRIBERS) {
		errorController(controller, new Error('Live stream capacity reached. Please retry.'));
		return () => {};
	}

	const worker = getOrCreateWorker(source, ffmpegPath);
	worker.idleKillTimer = clearTimer(worker.idleKillTimer);

	let detached = false;

	const detach = () => {
		if (detached) {
			return;
		}
		detached = true;
		abortSignal.removeEventListener('abort', onAbort);
	};

	const subscriber: StreamSubscriber = {
		controller,
		blockedFrames: 0,
		detach
	};

	const unsubscribe = () => {
		if (detached) {
			return;
		}

		removeSubscriber(worker, subscriber);
	};

	const onAbort = () => unsubscribe();

	worker.subscribers.add(subscriber);
	abortSignal.addEventListener('abort', onAbort, { once: true });

	if (!worker.ffmpeg && !worker.restartTimer) {
		startProcess(worker);
	}

	return unsubscribe;
}

function createMjpegReadable(
	source: string,
	ffmpegPath: string,
	abortSignal: AbortSignal
): ReadableStream<Uint8Array> {
	let unsubscribe: (() => void) | null = null;

	return new ReadableStream<Uint8Array>({
		start(controller) {
			if (abortSignal.aborted) {
				closeController(controller);
				return;
			}

			unsubscribe = attachSubscriber(source, ffmpegPath, controller, abortSignal);
		},
		cancel() {
			unsubscribe?.();
			unsubscribe = null;
		}
	});
}

const hot = (import.meta as ImportMeta & { hot?: { dispose(cb: () => void): void } }).hot;
hot?.dispose(() => {
	for (const source of Array.from(workers.keys())) {
		destroyWorker(source);
	}
});

export const GET: RequestHandler = async ({ params, request }) => {
	const ffmpegPath = await getFfmpegPath(new URL(request.url));
	if (!ffmpegPath) {
		const executableName = getExecutableName();
		throw error(
			500,
			`FFmpeg binary not available. Set FFMPEG_PATH, install ffmpeg in PATH, or place ${executableName} next to ${path.basename(process.execPath)}.`
		);
	}

	return new Response(createMjpegReadable(params.source, ffmpegPath, request.signal), {
		headers: {
			'Content-Type': `multipart/x-mixed-replace; boundary=${MJPEG_BOUNDARY}`,
			'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
			Pragma: 'no-cache',
			Connection: 'keep-alive',
			'X-Accel-Buffering': 'no'
		}
	});
};
