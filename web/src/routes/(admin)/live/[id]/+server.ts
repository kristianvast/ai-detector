import { spawn, spawnSync, type ChildProcessByStdio } from 'node:child_process';
import { existsSync } from 'node:fs';
import { chmod, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import type { Readable } from 'node:stream';
import { error } from '@sveltejs/kit';
import { getRtspStreamsFromConfig } from '$lib/server/live-streams';
import ffmpegStatic from 'ffmpeg-static';
import type { RequestHandler } from './$types';

const MJPEG_BOUNDARY = 'frame';
const IDLE_KILL_DELAY_MS = 3_000;
const FORCE_KILL_DELAY_MS = 2_000;
const MAX_BLOCKED_FRAMES = 240;
const WORKER_REGISTRY_KEY = '__ai_detector_stream_workers__';

type StreamController = ReadableStreamDefaultController<Uint8Array>;
interface StreamSubscriber {
	controller: StreamController;
	detach: () => void;
	blockedFrames: number;
}

interface StreamWorker {
	ffmpeg: ChildProcessByStdio<null, Readable, null>;
	subscribers: Set<StreamSubscriber>;
	idleKillTimer: ReturnType<typeof setTimeout> | null;
	forceKillTimer: ReturnType<typeof setTimeout> | null;
	closed: boolean;
}

type GlobalWorkerRegistry = typeof globalThis & {
	[WORKER_REGISTRY_KEY]?: Map<number, StreamWorker>;
};

const globalWorkerRegistry = globalThis as GlobalWorkerRegistry;
const workers =
	globalWorkerRegistry[WORKER_REGISTRY_KEY] ??
	(globalWorkerRegistry[WORKER_REGISTRY_KEY] = new Map<number, StreamWorker>());
let cachedFfmpegPath: string | null | undefined;
let ffmpegPathPromise: Promise<string | null> | null = null;

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

function destroyWorker(streamId: number): void {
	const worker = workers.get(streamId);
	if (!worker || worker.closed) {
		return;
	}

	worker.closed = true;
	if (worker.idleKillTimer) {
		clearTimeout(worker.idleKillTimer);
		worker.idleKillTimer = null;
	}

	worker.ffmpeg.kill('SIGTERM');
	worker.forceKillTimer = setTimeout(() => {
		if (!worker.closed) {
			return;
		}
		worker.ffmpeg.kill('SIGKILL');
	}, FORCE_KILL_DELAY_MS);
}

function scheduleIdleKill(streamId: number, worker: StreamWorker): void {
	if (worker.closed || worker.subscribers.size > 0 || worker.idleKillTimer) {
		return;
	}

	worker.idleKillTimer = setTimeout(() => {
		worker.idleKillTimer = null;
		if (worker.subscribers.size === 0) {
			destroyWorker(streamId);
		}
	}, IDLE_KILL_DELAY_MS);
}

function createWorker(streamId: number, source: string, ffmpegPath: string): StreamWorker {
	const ffmpegArgs = [
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

	const ffmpeg = spawn(ffmpegPath, ffmpegArgs, {
		stdio: ['ignore', 'pipe', 'ignore']
	});

	const worker: StreamWorker = {
		ffmpeg,
		subscribers: new Set(),
		idleKillTimer: null,
		forceKillTimer: null,
		closed: false
	};

	const broadcast = (chunk: Buffer<ArrayBufferLike>) => {
		for (const subscriber of worker.subscribers) {
			if (subscriber.controller.desiredSize !== null && subscriber.controller.desiredSize <= 0) {
				subscriber.blockedFrames += 1;
				if (subscriber.blockedFrames >= MAX_BLOCKED_FRAMES) {
					worker.subscribers.delete(subscriber);
					subscriber.detach();
					closeController(subscriber.controller);
					scheduleIdleKill(streamId, worker);
				}
				continue;
			}

			subscriber.blockedFrames = 0;
			try {
				subscriber.controller.enqueue(chunk);
			} catch (enqueueError) {
				if (!isInvalidControllerState(enqueueError)) {
					throw enqueueError;
				}
				worker.subscribers.delete(subscriber);
				subscriber.detach();
				scheduleIdleKill(streamId, worker);
			}
		}
	};

	const closeAll = (reason?: Error) => {
		const subscribers = Array.from(worker.subscribers);
		worker.subscribers.clear();
		for (const subscriber of subscribers) {
			subscriber.detach();
			if (reason) {
				errorController(subscriber.controller, reason);
			} else {
				closeController(subscriber.controller);
			}
		}
	};

	ffmpeg.stdout.on('data', broadcast);
	ffmpeg.once('error', (error) => {
		console.error('FFmpeg process error', error);
		closeAll(new Error('FFmpeg process error'));
	});
	ffmpeg.once('close', (exitCode) => {
		worker.closed = true;
		if (worker.idleKillTimer) {
			clearTimeout(worker.idleKillTimer);
			worker.idleKillTimer = null;
		}
		if (worker.forceKillTimer) {
			clearTimeout(worker.forceKillTimer);
			worker.forceKillTimer = null;
		}
		workers.delete(streamId);

		if (exitCode === 0) {
			closeAll();
		} else {
			closeAll(new Error(`FFmpeg exited with code ${exitCode ?? 'unknown'}`));
		}
	});

	return worker;
}

function getWorker(streamId: number, source: string, ffmpegPath: string): StreamWorker {
	const current = workers.get(streamId);
	if (current && !current.closed) {
		return current;
	}

	const created = createWorker(streamId, source, ffmpegPath);
	workers.set(streamId, created);
	return created;
}

function createMjpegReadable(
	streamId: number,
	source: string,
	ffmpegPath: string,
	abortSignal: AbortSignal
): ReadableStream<Uint8Array> {
	let subscriberRef: StreamSubscriber | null = null;
	let workerRef: StreamWorker | null = null;
	let detached = false;

	const detach = () => {
		if (detached) {
			return;
		}
		detached = true;
		abortSignal.removeEventListener('abort', onAbort);
		subscriberRef = null;
		workerRef = null;
	};

	const unsubscribe = () => {
		if (detached) {
			return;
		}
		const subscriber = subscriberRef;
		const worker = workerRef;
		detach();

		if (!subscriber || !worker) {
			return;
		}

		worker.subscribers.delete(subscriber);
		scheduleIdleKill(streamId, worker);
	};

	const onAbort = () => unsubscribe();

	return new ReadableStream<Uint8Array>({
		start(controller) {
			if (abortSignal.aborted) {
				closeController(controller);
				return;
			}

			const worker = getWorker(streamId, source, ffmpegPath);
			if (worker.idleKillTimer) {
				clearTimeout(worker.idleKillTimer);
				worker.idleKillTimer = null;
			}

			subscriberRef = { controller, detach, blockedFrames: 0 };
			workerRef = worker;
			worker.subscribers.add(subscriberRef);
			abortSignal.addEventListener('abort', onAbort, { once: true });
		},
		cancel() {
			unsubscribe();
		}
	});
}

const hot = (import.meta as ImportMeta & { hot?: { dispose(cb: () => void): void } }).hot;
hot?.dispose(() => {
	for (const streamId of Array.from(workers.keys())) {
		destroyWorker(streamId);
	}
	workers.clear();
});

export const GET: RequestHandler = async ({ params, request }) => {
	const streamId = Number.parseInt(params.id, 10);
	if (!Number.isInteger(streamId) || streamId < 0) {
		throw error(404, 'Stream not found');
	}

	const streams = await getRtspStreamsFromConfig();
	const stream = streams.find((candidate) => candidate.id === streamId);

	if (!stream) {
		throw error(404, 'Stream not found');
	}

	const ffmpegPath = await getFfmpegPath(new URL(request.url));
	if (!ffmpegPath) {
		const executableName = getExecutableName();
		throw error(
			500,
			`FFmpeg binary not available. Set FFMPEG_PATH, install ffmpeg in PATH, or place ${executableName} next to ${path.basename(process.execPath)}.`
		);
	}

	return new Response(createMjpegReadable(stream.id, stream.source, ffmpegPath, request.signal), {
		headers: {
			'Content-Type': `multipart/x-mixed-replace; boundary=${MJPEG_BOUNDARY}`,
			'Cache-Control': 'no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0',
			Pragma: 'no-cache',
			Connection: 'keep-alive',
			'X-Accel-Buffering': 'no'
		}
	});
};
