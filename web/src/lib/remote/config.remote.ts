import { command, query } from '$app/server';
import {
	APP_CONFIG_PATH,
	CONFIG_PATH,
	saveConfig as saveConfigShared
} from '$lib/server/shared-paths';
import { readFile } from 'node:fs/promises';
import type { AppConfig, Config } from '$lib/schema';
import { DEFAULT_SCHEMA_URL } from '$lib/schema';

async function readConfigDocument(): Promise<Config | null> {
	const config = await readFile(CONFIG_PATH, 'utf8').then(JSON.parse).catch(() => null);
	if (!config) {
		return null;
	}
	console.log(config)
	config.detectors = config.detectors.map((detector) => {
		const source = detector.detection?.source ?? [];
		detector.detection.source = Array.isArray(source) ? source : [source];
		detector.exporters = Object.entries(detector.exporters ?? {}).reduce((acc, [key, value]) => {
			acc[key] = value ? Array.isArray(value) ? value : [value] : [];
			return acc;
		}, {} as Record<string, unknown[]>);
		return detector
	});
	console.log(config)
	return config;
}

async function fetchSchema(schemaUrl: string) {
	const response = await fetch(schemaUrl);
	if (!response.ok) {
		throw new Error(`Failed to load config schema from ${schemaUrl}`);
	}

	return response.json();
}

export const getConfig = query(async (): Promise<{ config: Config; app: AppConfig }> => {
	const config = await readConfigDocument().then((res) => res ?? fetchSchema(DEFAULT_SCHEMA_URL));
	const appConfig = await readFile(APP_CONFIG_PATH, 'utf8')
		.then((res) => JSON.parse(res))
		.catch(() => ({
			streams: [],
			telegrams: [],
			detectors: []
		}));
	return { config, app: appConfig };
});

export const getConfigSchema = query(async () => {
	const config = await readConfigDocument();
	const schemaUrl = config?.$schema ?? DEFAULT_SCHEMA_URL;

	try {
		return await fetchSchema(schemaUrl);
	} catch (error) {
		if (schemaUrl === DEFAULT_SCHEMA_URL) {
			throw error;
		}

		return fetchSchema(DEFAULT_SCHEMA_URL);
	}
});

export const saveConfig = command('unchecked', async ({ config, app }) => {
	await saveConfigShared({ config, app });
});
