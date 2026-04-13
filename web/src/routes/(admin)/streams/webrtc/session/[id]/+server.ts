import { type RequestHandler } from '@sveltejs/kit';
import { destroyPreviewSession } from '$lib/server/webrtc-preview';

export const DELETE: RequestHandler = async ({ params }) => {
	await destroyPreviewSession(params.id);
	return new Response(null, { status: 204 });
};
