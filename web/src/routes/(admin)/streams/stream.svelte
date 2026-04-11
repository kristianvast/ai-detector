<script lang="ts">
	import { goto } from '$app/navigation';
	import CardOverlay from '$lib/components/card-overlay.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { resolve } from '$app/paths';
	import { Spinner } from '$lib/components/ui/spinner';
	import { onMount } from 'svelte';

	type Props = {
		label: string;
		source: string;
		showLoading?: boolean;
		hideOverlay?: boolean;
		disableLink?: boolean;
	};

	let {
		label,
		source,
		showLoading = false,
		hideOverlay = false,
		disableLink = false
	}: Props = $props();
	let img: HTMLImageElement;
	let loading = $state(true);
	let ready = $state(false);
	const streamUrl = $derived(`/streams/${encodeURIComponent(source)}`);
	let timeoutId: ReturnType<typeof setTimeout> | null = null;

	function start() {
		ready = true;
		timeoutId = setTimeout(stop, 10_000);
	}

	function stop() {
		ready = false;
		loading = false;
		if (img) {
			img.removeAttribute('src');
		}
		if (timeoutId) {
			clearTimeout(timeoutId);
			timeoutId = null;
		}
	}

	onMount(() => {
		if (document.readyState === 'complete') start();
		else window.addEventListener('load', start, { once: true });

		return () => {
			stop();
		};
	});
</script>

{#if showLoading && loading}
	<Spinner class="size-8" />
{/if}
<CardOverlay overlay={hideOverlay ? undefined : overlay}>
	<button
		class="relative block aspect-video w-full cursor-pointer bg-black"
		onclick={disableLink
			? undefined
			: () =>
					goto(
						resolve(
							`/streams/add?source=${encodeURIComponent(source)}&label=${encodeURIComponent(label)}`
						)
					)}
	>
		{#if ready}
			<img
				bind:this={img}
				src={streamUrl}
				alt={`${label} live feed`}
				class="block h-full w-full object-contain"
				loading="lazy"
				decoding="async"
				onload={() => {
					loading = false;
					clearTimeout(timeoutId!);
					timeoutId = null;
				}}
				onerror={stop}
			/>
		{/if}
	</button>
</CardOverlay>

{#snippet overlay()}
	<div class="flex flex-wrap items-center gap-2 text-xs">
		<Badge variant="secondary" class="bg-black/50 text-white">{label}</Badge>
		<Badge variant="secondary" class="bg-black/50 text-white">{source}</Badge>
	</div>
{/snippet}
