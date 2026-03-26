<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as NativeSelect from '$lib/components/ui/native-select';
	import { Textarea } from '$lib/components/ui/textarea';
	import {
		deleteDetector,
		getDetector,
		getDetectorPreset,
		getDetectorPresets,
		saveDetector
	} from '$lib/remote/detector.remote';

	const EMPTY_DETECTOR = {
		detection: {
			source: ['']
		},
		yolo: {
			model: '',
			confidence: 0.8
		},
		exporters: {}
	};

	const originalLabel = page.url.searchParams.get('label') ?? '';
	const isEditing = originalLabel.length > 0;
	const detectorPresets = await getDetectorPresets();
	const initialDetector = isEditing ? await getDetector({ label: originalLabel }) : undefined;
	const initialDetectorJson = JSON.stringify(initialDetector?.detector ?? EMPTY_DETECTOR, null, 2);

	let label = $state(originalLabel);
	let detectorJson = $state(initialDetectorJson);

	async function handlePresetChange(event: Event) {
		const file = (event.currentTarget as HTMLSelectElement).value;
		detectorJson = file
			? JSON.stringify(await getDetectorPreset({ file }), null, 2)
			: initialDetectorJson;
	}
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">
			{isEditing ? 'Edit Detector' : 'Add Detector'}
		</h1>
		<p class="text-sm text-muted-foreground">Configure a detector.</p>
	</header>

	<form {...saveDetector} class="flex max-w-2xl flex-col gap-2">
		<Input type="hidden" name="original" value={originalLabel} />

		<Label for="preset">Preset</Label>
		<NativeSelect.Root id="preset" class="w-full" onchange={handlePresetChange}>
			<option value="">Custom</option>
			{#each detectorPresets as presetFile (presetFile)}
				<option value={presetFile}>
					{presetFile
						.replace(/\.json$/i, '')
						.split('-')
						.filter(Boolean)
						.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
						.join(' ')}
				</option>
			{/each}
		</NativeSelect.Root>

		<Label for="label">Label</Label>
		<Input id="label" name="label" bind:value={label} placeholder="e.g. Detector X" />

		<Label for="detector">Detector Config</Label>
		<Textarea
			id="detector"
			name="detector"
			bind:value={detectorJson}
			class="min-h-96 font-mono text-sm"
			spellcheck={false}
		/>

		<div class="flex gap-2">
			{#if isEditing}
				<Button
					onclick={async () => {
						await deleteDetector({ label: originalLabel });
						await goto(resolve('/detectors'));
					}}
					variant="destructive"
					class="flex-1">Delete</Button
				>
			{/if}
			<Button type="submit" class="flex-1">Save</Button>
		</div>
	</form>
</section>
