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
<CardOverlay overlay={hideOverlay ? undefined : overlay}>
	<button
		class="relative block aspect-video w-full cursor-pointer bg-black"
		onclick={disableLink
			? undefined
			: () =>
					goto(
						resolve(
							`/stream/add?source=${encodeURIComponent(source)}&label=${encodeURIComponent(label)}`
						)
					)}
	>
		<img
			bind:this={img}
			src={`/stream/${encodeURIComponent(source)}`}
			alt={`${label} live feed`}
			class="block h-full w-full object-contain"
			loading="eager"
			decoding="async"
			onload={() => (loading = false)}
			onerror={() => (loading = false)}
		/>
	</button>
</CardOverlay>

{#snippet overlay()}
	<div class="flex flex-wrap items-center gap-2 text-xs">
		<Badge variant="secondary" class="bg-black/50 text-white">{label}</Badge>
		<Badge variant="secondary" class="bg-black/50 text-white">{source}</Badge>
	</div>
{/snippet}
