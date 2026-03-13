<script lang="ts">
	import { getStreams } from '$lib/remote/stream.remote';
	import Stream from './stream.svelte';

	const streams = await getStreams();
</script>

<header class="space-y-1">
	<h1 class="text-2xl font-semibold tracking-tight">Live streams</h1>
	<p class="text-sm text-muted-foreground">Live stream from your RTSP sources.</p>
</header>

<div class="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
	{#each streams as stream (stream.id)}
		<Stream id={stream.id} label={stream.label} source={stream.source} />
	{/each}
</div>
