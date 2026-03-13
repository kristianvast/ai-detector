import { getRtspStreamsFromConfig } from '$lib/server/live-streams';
import { query } from '$app/server';

export const getStreams = query(async () => {
	const streams = await getRtspStreamsFromConfig();
	return streams.map(({ id, label, displaySource }) => ({
		id,
		label,
		source: displaySource
	}));
});
