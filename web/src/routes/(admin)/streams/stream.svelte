<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import CardOverlay from '$lib/components/card-overlay.svelte';
	import { Badge } from '$lib/components/ui/badge';
	import { Spinner } from '$lib/components/ui/spinner';
	import { subscribeToStreamPreview } from '$lib/streams/webrtc-preview-manager';
	import type { PreviewSnapshot } from '$lib/streams/webrtc-preview-types';
	import { onMount } from 'svelte';

	type Props = {
		label: string;
		source: string;
		showLoading?: boolean;
		hideOverlay?: boolean;
		disableLink?: boolean;
	};

	const CONNECTING_SNAPSHOT: PreviewSnapshot = { phase: 'connecting', mediaStream: null };

	let {
		label,
		source,
		showLoading = false,
		hideOverlay = false,
		disableLink = false
	}: Props = $props();

	let video: HTMLVideoElement | null = null;
	let unsubscribePreview: (() => void) | null = null;
	let mounted = false;
	let snapshot = $state<PreviewSnapshot>(CONNECTING_SNAPSHOT);
	let videoReady = $state(false);

	const loading = $derived(
		snapshot.phase === 'connecting' ||
			snapshot.phase === 'reconnecting' ||
			(snapshot.phase === 'live' && !videoReady)
	);
	const reconnecting = $derived(snapshot.phase === 'reconnecting');
	const unavailable = $derived(snapshot.phase === 'error');
	const errorMessage = $derived(snapshot.error ?? 'Live stream unavailable.');

	function resetPreview() {
		snapshot = CONNECTING_SNAPSHOT;
		videoReady = false;
	}

	function handleLoadedData() {
		videoReady = true;
	}

	function handlePlaying() {
		videoReady = true;
	}

	function handleVideoError() {
		videoReady = false;
		snapshot = {
			phase: 'error',
			mediaStream: null,
			error: snapshot.error ?? 'Live stream unavailable.'
		};
	}

	onMount(() => {
		mounted = true;

		return () => {
			mounted = false;
			unsubscribePreview?.();
			unsubscribePreview = null;

			if (video) {
				video.pause();
				video.srcObject = null;
			}
		};
	});

	$effect(() => {
		const element = video;
		const stream = snapshot.mediaStream;

		if (!element) {
			return;
		}

		if (element.srcObject === stream) {
			if (stream) {
				void element.play().catch(() => {});
			}
			return;
		}

		videoReady = false;
		element.pause();
		element.srcObject = stream;

		if (stream) {
			void element.play().catch(() => {});
		}
	});

	$effect(() => {
		if (!mounted) {
			return;
		}

		unsubscribePreview?.();
		resetPreview();
		unsubscribePreview = subscribeToStreamPreview(source, (nextSnapshot) => {
			snapshot = nextSnapshot;
			if (nextSnapshot.phase !== 'live') {
				videoReady = false;
			}
		});

		return () => {
			unsubscribePreview?.();
			unsubscribePreview = null;
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
		<video
			bind:this={video}
			muted
			playsinline
			autoplay
			class="block h-full w-full object-contain"
			onloadeddata={handleLoadedData}
			onplaying={handlePlaying}
			onerror={handleVideoError}
		></video>

		{#if unavailable}
			<div
				class="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-white/70"
			>
				{errorMessage}
			</div>
		{:else if reconnecting}
			<div
				class="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-white/60"
			>
				Reconnecting...
			</div>
		{:else if loading && !showLoading}
			<div
				class="absolute inset-0 flex items-center justify-center px-4 text-center text-xs text-white/60"
			>
				Connecting...
			</div>
		{/if}
	</button>
</CardOverlay>

{#snippet overlay()}
	<div class="flex flex-wrap items-center gap-2 text-xs">
		<Badge variant="secondary" class="bg-black/50 text-white">{label}</Badge>
		<Badge variant="secondary" class="bg-black/50 text-white">{source}</Badge>
	</div>
{/snippet}
