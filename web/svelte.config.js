// import adapter from '@sveltejs/adapter-node';
import adapter from '@jesterkit/exe-sveltekit';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	// Consult https://svelte.dev/docs/kit/integrations
	// for more information about preprocessors
	preprocess: vitePreprocess(),
	compilerOptions: {
		experimental: {
			async: true
		}
	},
	kit: {
		adapter: adapter({
			binaryName: 'ai-detector-web',
			target: 'windows-x64-baseline'
		}),
		experimental: {
			remoteFunctions: true
		}
	}
};

export default config;
