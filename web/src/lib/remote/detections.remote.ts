import fs from 'node:fs/promises';
import path from 'node:path';
import { query } from '$app/server';
import * as v from 'valibot';
import { STAGES, type Metadata, type Stage } from '$lib/schema';
import { DETECTIONS_DIR } from '$lib/server/shared-paths';

async function listFolders(directoryPath: string): Promise<string[]> {
	try {
		const entries = await fs.readdir(directoryPath, { withFileTypes: true });
		return entries
			.filter((entry) => entry.isDirectory())
			.map((entry) => entry.name)
			.sort((a, b) => a.localeCompare(b));
	} catch {
		return [];
	}
}

async function readDetection(type: string, stage: Stage, timestamp: string): Promise<Metadata> {
	const metadataPath = path.join(DETECTIONS_DIR, type, stage, timestamp, 'metadata.json');
	const metadata = JSON.parse(await fs.readFile(metadataPath, 'utf8')) as Metadata;
	metadata.type = type;
	return metadata;
}

function toEpoch(value: unknown): number {
	if (value instanceof Date) {
		return value.getTime();
	}
	if (typeof value === 'string') {
		const normalized = value.replace(
			/^(\d{4}-\d{2}-\d{2})T(\d{2})-(\d{2})-(\d{2})(\.\d+)?$/,
			'$1T$2:$3:$4$5'
		);
		const parsed = Date.parse(normalized);
		return Number.isFinite(parsed) ? parsed : 0;
	}
	return 0;
}

export const getTypes = query(async () => {
	return listFolders(DETECTIONS_DIR);
});

export const getDetections = query(
	v.object({
		type: v.optional(v.string()),
		stage: v.optional(v.picklist(STAGES))
	}),
	async ({ type, stage }) => {
		const types = type ? [type] : await listFolders(DETECTIONS_DIR);
		const stages = stage ? [stage] : STAGES;

		const entries: Metadata[] = [];
		for (const type of types) {
			for (const stage of stages) {
				const stagePath = path.join(DETECTIONS_DIR, type, stage);
				const timestamps = await listFolders(stagePath);
				for (const timestamp of timestamps) {
					entries.push(await readDetection(type, stage, timestamp));
				}
			}
		}

		return entries.sort(
			(a, b) =>
				toEpoch((b as { timestamp?: unknown }).timestamp) -
				toEpoch((a as { timestamp?: unknown }).timestamp)
		);
	}
);
