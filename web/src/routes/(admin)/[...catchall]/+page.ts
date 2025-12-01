import { error } from '@sveltejs/kit';

export function load() {
	return error(404, 'Page not found');
}