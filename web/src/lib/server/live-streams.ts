import fs from 'node:fs/promises';
import * as v from 'valibot';
import { configSchema } from '$lib/schema';
import { CONFIG_PATH } from '$lib/server/shared-paths';

export interface LiveRtspStream {
	id: number;
	source: string;
	label: string;
	displaySource: string;
}

function sourceList(value: string | string[]): string[] {
	if (typeof value === 'string') {
		return [value];
	}
	return value;
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
		const parsedConfig = v.safeParse(
			configSchema,
			JSON.parse(await fs.readFile(CONFIG_PATH, 'utf8')) as unknown
		);

		if (!parsedConfig.success) {
			console.error(parsedConfig.issues);
			return [];
		}

		const config = parsedConfig.output;
		const streams: LiveRtspStream[] = [];
		for (const detector of config.detectors) {
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
