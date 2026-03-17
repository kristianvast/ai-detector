<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { getStreams } from '$lib/remote/stream.remote';
	import Stream from './stream.svelte';
	import { Plus } from '@lucide/svelte';

	const streams = await getStreams();
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<div class="flex items-center justify-between">
			<h1 class="text-2xl font-semibold tracking-tight">Live streams</h1>
			<Button href="/live/add" variant="outline"><Plus /> Add stream</Button>
		</div>
		<p class="text-sm text-muted-foreground">Live stream from your RTSP sources.</p>
	</header>

	<div class="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
		{#each streams as stream (stream.source)}
			<Stream label={stream.label} source={stream.source} />
		{/each}
	</div>
</section>
