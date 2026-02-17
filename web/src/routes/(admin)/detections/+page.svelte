<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import { getDetections, getTypes } from '$lib/remote/detections.remote';
	import { STAGES, type Metadata, type Stage } from '$lib/schema';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import DetectionCard from './detection-card.svelte';

	const type = $derived(page.url.searchParams.get('type') || undefined);
	const stage = $derived((page.url.searchParams.get('stage') as Stage | null) || undefined);
	const types = $derived(await getTypes());

	const detections = $derived(getDetections({ type, stage }));
	const detectionsByDay = $derived.by(async () => {
		const dayDetections = new Map<string, Array<Metadata>>();
		for (const detection of await detections) {
			const day = String(detection.timestamp).split('T')[0];
			if (!dayDetections.has(day)) {
				dayDetections.set(day, []);
			}
			dayDetections.set(day, [...(dayDetections.get(day) ?? []), detection]);
		}
		return Array.from(dayDetections.entries());
	});

	function capitalize(value: string) {
		return value.charAt(0).toUpperCase() + value.slice(1);
	}

	async function updateSearchParams(type?: string, stage?: string) {
		const searchParams = new URLSearchParams(page.url.searchParams);

		if (type) {
			searchParams.set('type', type);
		} else {
			searchParams.delete('type');
		}

		if (stage) {
			searchParams.set('stage', stage);
		} else {
			searchParams.delete('stage');
		}

		const search = searchParams.toString();
		const nextUrl = search ? `${page.url.pathname}?${search}` : page.url.pathname;
		const currentUrl = `${page.url.pathname}${page.url.search}`;

		if (nextUrl !== currentUrl) {
			await goto(nextUrl, {
				replaceState: true,
				noScroll: true,
				keepFocus: true,
				invalidateAll: false
			});
		}
	}
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Detections</h1>
		<p class="text-sm text-muted-foreground">
			Review detections grouped by day and quickly play each clip.
		</p>
	</header>

	<div class="flex flex-col gap-2">
		{#if types.length > 0}
			<div class="flex flex-wrap gap-2">
				{#each [undefined, ...types] as t}
					<Button
						type="button"
						size="sm"
						variant={t === type ? 'default' : 'outline'}
						aria-pressed={t === type}
						onclick={() => updateSearchParams(t, stage || undefined)}
					>
						{t ? capitalize(t) : 'All categories'}
					</Button>
				{/each}
			</div>
		{/if}
		{#if STAGES.length > 0}
			<div class="flex flex-wrap gap-2">
				{#each [undefined, ...STAGES] as s}
					<Button
						type="button"
						size="sm"
						variant={s === stage ? 'default' : 'outline'}
						aria-pressed={s === stage}
						onclick={() => updateSearchParams(type || undefined, s)}
					>
						{s ? capitalize(s) : 'All stages'}
					</Button>
				{/each}
			</div>
		{/if}
	</div>

	{#await detectionsByDay}
		<h2 class="text-sm font-semibold text-muted-foreground">Loading detections...</h2>
	{:then detectionsByDay}
		{#if detectionsByDay.length === 0}
			<p class="text-sm font-semibold text-muted-foreground">No detections found.</p>
		{:else}
			<div class="space-y-8">
				{#each detectionsByDay as dayGroup (dayGroup[0])}
					<section class="space-y-3">
						<div class="flex items-center gap-2">
							<h2 class="text-sm font-semibold text-muted-foreground">
								{Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(
									new Date(dayGroup[0])
								)}
							</h2>
							<Badge variant="outline">{dayGroup[1].length}</Badge>
						</div>
						<div class="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
							{#each dayGroup[1] as entry (String(entry.timestamp))}
								<DetectionCard {entry} />
							{/each}
						</div>
					</section>
				{/each}
			</div>
		{/if}
	{/await}
</section>
