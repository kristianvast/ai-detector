import { command, form, query } from '$app/server';
import { getConfig, saveConfig } from './config.remote';
import type { StreamConfig } from '$lib/schema';
import * as v from 'valibot';
import { redirect } from '@sveltejs/kit';

export const getStreams = query(async () => {
	const { config, app } = await getConfig();
	const detectorSources = config.detectors.flatMap((detector) => Array.isArray(detector.detection.source) ? detector.detection.source : [detector.detection.source])
	const detectorStreams = detectorSources.filter((source) => source.trim().match(/rtsps?:\/\//i))
	const allStreams = [...new Set([...app.streams, ...detectorStreams.map((source) => ({ source } as StreamConfig))])];
	const uniqueStreams = allStreams.filter((stream, index) => allStreams.findIndex((s) => s.source === stream.source) === index);

	return uniqueStreams.map((stream, index) => ({
		source: stream.source,
		label: stream.label ?? 'Stream ' + (index + 1),
	}));
});

export const saveStream = form(
	v.object({
		original: v.optional(v.string()),
		label: v.string(),
		source: v.string(),
	}),
	async ({ source, label, original }) => {
		const { config, app } = await getConfig();
		let found = false;
		app.streams.forEach((stream) => {
			if (stream.source === original) {
				stream.label = label;
				stream.source = source;
				found = true;
			}
		});
		if (!found) {
			app.streams.push({ source, label });
		}
		config.detectors.forEach((detector) => {
			if (Array.isArray(detector.detection.source)) {
				detector.detection.source = detector.detection.source.map((s) => s === original ? source : s);
			} else {
				if (detector.detection.source === original) {
					detector.detection.source = source;
				}
			}
		});
		await saveConfig({ config, app });
		redirect(302, '/live');
	})

export const deleteStream = command(
	v.object({
		source: v.string(),
	}),
	async ({ source }) => {
		const { config, app } = await getConfig();
		app.streams = app.streams.filter((stream) => stream.source !== source);
		config.detectors.forEach((detector) => {
			if (Array.isArray(detector.detection.source)) {
				detector.detection.source = detector.detection.source.filter((s) => s !== source);
			} else {
				if (detector.detection.source === source) {
					detector.detection.source = '';
				}
			}
		});
		await saveConfig({ config, app });
	})