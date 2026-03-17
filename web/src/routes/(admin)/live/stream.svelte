<script lang="ts">
	import { goto } from '$app/navigation';
	import CardOverlay from '$lib/components/card-overlay.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { resolve } from '$app/paths';
	import { Spinner } from '$lib/components/ui/spinner';

	type Props = {
		label: string;
		source: string;
		showLoading?: boolean;
	};

	let { label, source, showLoading = false }: Props = $props();
	let img: HTMLImageElement;
	let loading = $state(false);

	$effect(() => {
		loading = true;
		return () => {
			if (img) {
				img.src = '';
			}
		};
	});
</script>

{#if showLoading && loading}
	<Spinner class="size-8" />
{/if}
<CardOverlay>
	<button
		class="relative block aspect-video w-full cursor-pointer bg-black"
		onclick={() =>
			goto(
				resolve(`/live/add?source=${encodeURIComponent(source)}&label=${encodeURIComponent(label)}`)
			)}
	>
		<img
			bind:this={img}
			src={`/live/${encodeURIComponent(source)}`}
			alt={`${label} live feed`}
			class="block h-full w-full object-contain"
			loading="eager"
			decoding="async"
			onload={() => (loading = false)}
			onerror={() => (loading = false)}
		/>
	</button>

	{#snippet overlay()}
		<div class="flex flex-wrap items-center gap-2 text-xs">
			<Badge variant="secondary" class="bg-black/50 text-white">{label}</Badge>
			<Badge variant="secondary" class="bg-black/50 text-white">{source}</Badge>
		</div>
	{/snippet}
</CardOverlay>
