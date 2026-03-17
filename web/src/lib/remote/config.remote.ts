import { command, query } from "$app/server";
import { CONFIG_PATH } from "$lib/server/shared-paths";
import { readFile, writeFile } from "node:fs/promises";
import type { Config } from "$lib/schema";
import { DEFAULT_SCHEMA_URL } from "$lib/schema";

export const getConfig = query(async (): Promise<Config> => {
	const nullableConfig = await readFile(CONFIG_PATH, 'utf8');
	const config = nullableConfig ? JSON.parse(nullableConfig) : undefined;
	config.app = config.app ?? {};

	if (!config) {
		const default_config = await fetch(DEFAULT_SCHEMA_URL).then((res) => res.json());
		default_config.app = default_config.app ?? {};
		await writeFile(CONFIG_PATH, JSON.stringify(default_config, null, 2));
		return default_config;
	} else {
		return config;
	}
})

export const saveConfig = command("unchecked", async ({ config }) => {
	await writeFile(CONFIG_PATH, JSON.stringify(config, null, 2));
})