import { error, json, type RequestHandler } from '@sveltejs/kit';
import { createPreviewSession, PreviewSessionError } from '$lib/server/webrtc-preview';
import type { RTCSessionDescriptionInit } from 'werift';

type SessionRequestBody = {
	offer?: {
		type?: string;
		sdp?: string;
	};
	sources?: unknown;
};

export const POST: RequestHandler = async ({ request }) => {
	let body: SessionRequestBody;

	try {
		body = (await request.json()) as SessionRequestBody;
	} catch {
		throw error(400, 'Expected a JSON request body.');
	}

	try {
		const offerType: RTCSessionDescriptionInit['type'] =
			body.offer?.type === 'offer' ? 'offer' : 'answer';

		const session = await createPreviewSession({
			offer: {
				type: offerType,
				sdp: body.offer?.sdp ?? ''
			},
			sources: Array.isArray(body.sources)
				? body.sources.filter((value): value is string => typeof value === 'string')
				: [],
			requestUrl: new URL(request.url)
		});

		return json(session);
	} catch (value) {
		if (value instanceof PreviewSessionError) {
			throw error(value.status, value.message);
		}

		console.error('Failed to create WebRTC preview session', value);
		throw error(500, 'Failed to create WebRTC preview session.');
	}
};
