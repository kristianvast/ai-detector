<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import { deleteDetector, saveDetector } from '$lib/remote/detector.remote';

	let indexString = $state(page.url.searchParams.get('index') ?? '');
	let index = $derived(indexString ? parseInt(indexString) : undefined);
	let label = $state(page.url.searchParams.get('label') ?? '');
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Add Detector</h1>
		<p class="text-sm text-muted-foreground">Add a new detector.</p>
	</header>

	<div class="flex justify-between gap-6">
		<form {...saveDetector} class="flex w-lg flex-col gap-2">
			<Input type="hidden" name="index" value={index} />
			<Label for="label">Label</Label>
			<Input id="label" name="label" bind:value={label} placeholder="e.g. Groupchat X" />
			<div class="flex gap-2">
				{#if index !== undefined}
					<Button
						onclick={() => deleteDetector({ index }).then(() => goto(resolve('/detectors')))}
						variant="destructive"
						class="flex-1">Delete</Button
					>
				{/if}
				<Button type="submit" class="flex-1">Save</Button>
			</div>
		</form>
	</div>
</section>
