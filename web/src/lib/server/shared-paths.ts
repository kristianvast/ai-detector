import { dev } from '$app/environment';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';

export const CONFIG_PATH = path.resolve(
	dev ? process.cwd() : path.dirname(process.execPath),
	'config.json'
);
export const APP_CONFIG_PATH = path.resolve(
	dev ? process.cwd() : path.dirname(process.execPath),
	'app.json'
);
export const DETECTIONS_DIR = path.resolve(
	dev ? process.cwd() : path.dirname(process.execPath),
	'detections'
);

export function resolveWithinDirectory(
	directoryPath: string,
	requestedPath: string
): string | null {
	const normalizedPath = requestedPath.replaceAll('\\', '/').replace(/^\/+/, '');
	const resolvedPath = path.resolve(directoryPath, normalizedPath);
	const relativePath = path.relative(directoryPath, resolvedPath);

	if (relativePath.startsWith('..') || path.isAbsolute(relativePath)) {
		return null;
	}

	return resolvedPath;
}

export const saveConfig = async ({ config, app }: { config: any, app: any }) => {
	await writeFile(CONFIG_PATH, JSON.stringify(config, null, 2));
	await writeFile(APP_CONFIG_PATH, JSON.stringify(app, null, 2));
};