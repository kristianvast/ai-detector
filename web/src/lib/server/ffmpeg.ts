import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { chmod, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { tmpdir } from 'node:os';
import ffmpegStatic from 'ffmpeg-static';

let cachedFfmpegPath: string | null | undefined;
let ffmpegPathPromise: Promise<string | null> | null = null;
const DEFAULT_RTSP_TRANSPORT_MODE = 'prefer_tcp';
const VALID_RTSP_TRANSPORT_MODES = new Set([
	'auto',
	'prefer_tcp',
	'tcp',
	'udp',
	'udp_multicast',
	'http',
	'https'
]);

export function getExecutableName(): string {
	return process.platform === 'win32' ? 'ffmpeg.exe' : 'ffmpeg';
}

export function isRtspSource(source: string): boolean {
	return /^rtsps?:\/\//i.test(source.trim());
}

export function sanitizeSourceForLogs(source: string): string {
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

export function getRtspInputArgs(source: string): string[] {
	const configuredMode =
		process.env.AI_DETECTOR_RTSP_TRANSPORT?.trim().toLowerCase() ?? DEFAULT_RTSP_TRANSPORT_MODE;
	const transportMode = VALID_RTSP_TRANSPORT_MODES.has(configuredMode)
		? configuredMode
		: DEFAULT_RTSP_TRANSPORT_MODE;

	if (transportMode === 'auto') {
		return ['-i', source];
	}

	if (transportMode === 'prefer_tcp') {
		return ['-rtsp_flags', 'prefer_tcp', '-i', source];
	}

	return ['-rtsp_transport', transportMode, '-i', source];
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

export async function getFfmpegPathWithFallback(requestUrl: URL): Promise<string | null> {
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
