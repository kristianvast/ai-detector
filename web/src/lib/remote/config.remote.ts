import { command, query } from '$app/server';
import { APP_CONFIG_PATH, CONFIG_PATH, saveConfig as saveConfigShared } from '$lib/server/shared-paths';
import { readFile } from 'node:fs/promises';
import type { Config, AppConfig } from '$lib/schema';
import { DEFAULT_SCHEMA_URL } from '$lib/schema';

export const getConfig = query(async (): Promise<{ config: Config; app: AppConfig }> => {
	const config = await readFile(CONFIG_PATH, 'utf8')
		.then((res) => JSON.parse(res))
		.catch(() => fetch(DEFAULT_SCHEMA_URL).then((res) => res.json()));
	const appConfig = await readFile(APP_CONFIG_PATH, 'utf8')
		.then((res) => JSON.parse(res))
		.catch(() => ({
			streams: [],
			telegrams: [],
			detectors: []
		}));
	return { config, app: appConfig };
});

export const saveConfig = command('unchecked', async ({ config, app }) => {
	await saveConfigShared({ config, app })
});
