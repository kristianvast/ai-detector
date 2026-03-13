import fs from 'node:fs/promises';
import { command, query } from '$app/server';
import * as v from 'valibot';
import {
	createDefaultConfigEditor,
	getConfigDocument,
	normalizeConfigDocument,
	serializeConfigEditor,
	type ConfigEditor
} from '$lib/config-editor';
import { configSchema } from '$lib/schema';
import { CONFIG_PATH } from '$lib/server/shared-paths';

function toIssueList(issues: ReadonlyArray<{ message: string }> | undefined): string[] {
	return (issues ?? []).map((issue) => issue.message);
}

async function readEditableConfig() {
	try {
		const rawText = await fs.readFile(CONFIG_PATH, 'utf8');
		const rawConfig = JSON.parse(rawText) as unknown;
		const { config, schemaUrl } = getConfigDocument(rawConfig);
		const parsedConfig = v.safeParse(configSchema, config);

		if (!parsedConfig.success) {
			return {
				config: createDefaultConfigEditor(),
				loadIssues: toIssueList(parsedConfig.issues),
				configPath: CONFIG_PATH
			};
		}

		return {
			config: normalizeConfigDocument({
				...(schemaUrl ? { $schema: schemaUrl } : {}),
				...parsedConfig.output
			}),
			loadIssues: [] as string[],
			configPath: CONFIG_PATH
		};
	} catch (error) {
		return {
			config: createDefaultConfigEditor(),
			loadIssues: [error instanceof Error ? error.message : 'Unable to read config.json'],
			configPath: CONFIG_PATH
		};
	}
}

export const getEditableConfig = query(async () => {
	return readEditableConfig();
});

export const saveEditableConfig = command('unchecked', async (editorConfig: ConfigEditor) => {
	try {
		const configDocument = serializeConfigEditor(editorConfig);
		const { config, schemaUrl } = getConfigDocument(configDocument);
		const parsedConfig = v.safeParse(configSchema, config);

		if (!parsedConfig.success) {
			return {
				ok: false as const,
				message: 'Config validation failed.',
				issues: toIssueList(parsedConfig.issues)
			};
		}

		const nextConfig = {
			...(schemaUrl ? { $schema: schemaUrl } : {}),
			...parsedConfig.output
		};

		await fs.writeFile(CONFIG_PATH, `${JSON.stringify(nextConfig, null, '\t')}\n`);

		return {
			ok: true as const,
			message: 'Config saved.',
			savedAt: new Date().toISOString(),
			config: normalizeConfigDocument(nextConfig)
		};
	} catch (error) {
		return {
			ok: false as const,
			message: 'Unable to save config.',
			issues: [error instanceof Error ? error.message : 'Unknown save error']
		};
	}
});
