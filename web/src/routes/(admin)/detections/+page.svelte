<script lang="ts">
	import { Badge } from '$lib/components/ui/badge';
	import { Button } from '$lib/components/ui/button';
	import * as Card from '$lib/components/ui/card';
	import { getDetections, getTypes } from '$lib/remote/detections.remote';
	import { STAGES, type Metadata, type Stage } from '$lib/schema';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { browser } from '$app/environment';

	const type = $derived(page.url.searchParams.get('type') || undefined);
	const stage = $derived((page.url.searchParams.get('stage') as Stage | null) || undefined);
	const types = getTypes();

	const detections = $derived(getDetections({type, stage}));
	const detectionsByDay = $derived.by(() => {
		const dayDetections = new Map<string, Array<Metadata>>();
		if (!detections.ready) {
			return [];
		}
		for (const detection of detections.current) {
			const day = String(detection.timestamp).split('T')[0];
			if (!dayDetections.has(day)) {
				dayDetections.set(day, []);
			}
			dayDetections.set(day, [...(dayDetections.get(day) ?? []), detection]);
		}
		return Array.from(dayDetections.entries());
	});

	const stageLabels = {
		approved: 'Approved',
		rejected: 'Rejected',
		unvalidated: 'Unvalidated'
	} as const;

	const stageBadgeVariants = {
		approved: 'default',
		rejected: 'destructive',
		unvalidated: 'secondary'
	} as const;

	const stageBadgeClasses = {
		approved: 'bg-emerald-600 text-white',
		rejected: '',
		unvalidated: 'bg-amber-500 text-black'
	} as const;

	const overlayBadgeClass = 'bg-black/50 text-white';

	function getResource(type: string, stage: Stage, timestamp: string, resource: string) {
		return `/detections/${type}/${stage}/${timestamp}/${resource}`;
	}

	function capitalize(value: string) {
		return value.charAt(0).toUpperCase() + value.slice(1);
	}
	
	async function updateSearchParams(
		type?: string,
		stage?: string
	) {
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
		<p class="text-sm text-muted-foreground">Review detections grouped by day and quickly play each clip.</p>
	</header>

	<div class="flex flex-wrap items-center gap-3">
		<div class="flex flex-wrap gap-2">
			{#if types.ready}
				{#each [undefined, ...types.current] as t}
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
			{/if}
		</div>

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
	</div>

	{#await detectionsByDay}
		<p>Loading detections...</p>
	{:then detectionsByDay} 
		<div class="space-y-8">
			{#each detectionsByDay as dayGroup (dayGroup[0])}
				<section class="space-y-3">
					<div class="flex items-center gap-2">
						<h2 class="text-sm font-semibold text-muted-foreground">{Intl.DateTimeFormat('en-US', {
							weekday: 'long',
							day: 'numeric',
							month: 'long'
						}).format(new Date(dayGroup[0]))}</h2>
						<Badge variant="outline">{dayGroup[1].length}</Badge>
					</div>
					<div class="flex flex-wrap gap-4">
						{#each dayGroup[1] as entry (String(entry.timestamp))}
							{@const resolvedStage = stage ?? (entry.validated === true ? 'approved' : entry.validated === false ? 'rejected' : 'unvalidated')}
							<Card.Root class="relative w-full max-w-104 gap-0 overflow-hidden py-0 sm:w-104">
								{#if entry.type}
									<video class="block h-auto w-full bg-black" controls preload="metadata">
										<source src={getResource(entry.type, resolvedStage, entry.timestamp, 'video.mp4')} type="video/mp4" />
										Your browser cannot play this video.
									</video>
								{:else}
									<img
										src={getResource(entry.type, resolvedStage, entry.timestamp, 'best.jpg')}
										alt="Detection snapshot"
										loading="lazy"
										class="block h-auto w-full"
									/>
								{/if}

								<div
									class="pointer-events-none absolute inset-x-0 top-0 z-10 bg-gradient-to-b from-black/80 via-black/45 to-transparent p-3 text-white"
								>
									<div class="flex flex-wrap items-center gap-2 text-xs">
										<Badge variant={stageBadgeVariants[resolvedStage]} class={stageBadgeClasses[resolvedStage]}>
											{stageLabels[resolvedStage]}
										</Badge>
										<Badge variant="secondary" class={overlayBadgeClass}>
											{capitalize(entry.type)}
										</Badge>
										<Badge variant="secondary" class={overlayBadgeClass}>
											Time: {entry.start.split('T')[1].split('.')[0]}
										</Badge>
										<Badge variant="secondary" class={overlayBadgeClass}>
											Duration: {entry.duration.toFixed(2)}s
										</Badge>
										<Badge variant="secondary" class={overlayBadgeClass}>
											Confidence: {(entry.confidence * 100).toFixed(1)}%
										</Badge>
									</div>
								</div>
							</Card.Root>
						{/each}
					</div>
				</section>
			{/each}
		</div>
	{/await}
</section>
