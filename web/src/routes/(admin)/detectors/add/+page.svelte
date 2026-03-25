<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { deleteDetector, getDetector, saveDetector } from '$lib/remote/detector.remote';

	let originalLabel = $state(page.url.searchParams.get('label') ?? '');
	let detector = $state(originalLabel ? await getDetector({ label: originalLabel }) : undefined);
	let data = $state(detector.detector);
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Add Detector</h1>
		<p class="text-sm text-muted-foreground">Add a new detector.</p>
	</header>

	<div class="flex justify-between gap-6">
		<form {...saveDetector} class="flex w-lg flex-col gap-2">
			<Input type="hidden" name="original" value={originalLabel} />
			<Label for="label">Label</Label>
			<Input id="label" name="label" placeholder="e.g. Detector X" />
			<Label for="model">Model</Label>
			<Input id="model" name="model" bind:value={data.yolo.model} placeholder="e.g. yolov11n.pt" />
			<Label for="confidence">Confidence</Label>
			<Input
				id="confidence"
				name="confidence"
				bind:value={data.yolo.confidence}
				placeholder="e.g. 0.5"
			/>
			<div class="flex gap-2">
				{#if originalLabel}
					<Button
						onclick={() =>
							deleteDetector({ label: originalLabel }).then(() => goto(resolve('/detectors')))}
						variant="destructive"
						class="flex-1">Delete</Button
					>
				{/if}
				<Button type="submit" class="flex-1">Save</Button>
			</div>
		</form>
	</div>
</section>
