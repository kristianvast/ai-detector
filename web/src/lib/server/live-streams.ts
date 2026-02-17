import fs from 'node:fs/promises';
import { CONFIG_PATH } from '$lib/server/shared-paths';

export interface LiveRtspStream {
	id: number;
	source: string;
	label: string;
	displaySource: string;
}

function isObject(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function sourceList(value: unknown): string[] {
	if (typeof value === 'string') {
		return [value];
	}
	if (!Array.isArray(value)) {
		return [];
	}
	return value.filter((item): item is string => typeof item === 'string');
}

function parseRtspUrl(source: string): URL | null {
	const trimmed = source.trim();
	if (!/^rtsps?:\/\//i.test(trimmed)) {
		return null;
	}

	try {
		return new URL(trimmed);
	} catch {
		return null;
	}
}

function displaySource(url: URL): string {
	const host = url.port ? `${url.hostname}:${url.port}` : url.hostname;
	return url.pathname && url.pathname !== '/' ? `${host}${url.pathname}` : host;
}

export async function getRtspStreamsFromConfig(): Promise<LiveRtspStream[]> {
	try {
		const config = JSON.parse(await fs.readFile(CONFIG_PATH, 'utf8')) as unknown;
		console.log(config)
		if (!isObject(config) || !Array.isArray(config.detectors)) {
			return [];
		}

		const streams: LiveRtspStream[] = [];
		for (const detector of config.detectors) {
			if (!isObject(detector) || !isObject(detector.detection)) {
				continue;
			}

			for (const source of sourceList(detector.detection.source)) {
				const parsed = parseRtspUrl(source);
				if (!parsed) {
					continue;
				}
				const nextId = streams.length;
				streams.push({
					id: nextId,
					source,
					label: `Stream ${nextId + 1}`,
					displaySource: displaySource(parsed)
				});
			}
		}

		return streams;
	} catch (error) {
		console.error(error);
		return [];
	}
}
