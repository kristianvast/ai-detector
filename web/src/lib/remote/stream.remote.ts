import { query } from '$app/server';
import { getConfig } from './config.remote';

export const getStreams = query(async () => {
	const config = await getConfig();
	const streams = config.app?.streams ?? []
	const detectorSources = config.detectors.flatMap((detector) => Array.isArray(detector.detection.source) ? detector.detection.source : [detector.detection.source])
	const detectorStreams = detectorSources.filter((source) => source.trim().match(/rtsps?:\/\//i))
	const allStreams = [...new Set([...streams, ...detectorStreams.map((source) => ({ source } as StreamConfig))])];

	return allStreams.map((stream, index) => ({
		id: index,
		source: stream.source,
		label: stream.label ?? "Stream " + (index + 1),
	}));
});
