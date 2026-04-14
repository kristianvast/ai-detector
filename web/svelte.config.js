import nodeAdapter from '@sveltejs/adapter-node';
import exeAdapter from '@jesterkit/exe-sveltekit';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

const buildTarget = process.env.AI_DETECTOR_WEB_TARGET?.trim().toLowerCase();
const adapter =
	buildTarget === 'docker'
		? nodeAdapter()
		: exeAdapter({
				binaryName: 'ai-detector-web',
				target: 'windows-x64-baseline'
			});

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
		adapter,
		experimental: {
			remoteFunctions: true
		}
	}
};

export default config;
