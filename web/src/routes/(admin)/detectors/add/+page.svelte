<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { Button } from '$lib/components/ui/button';
	import JsonEditor from '$lib/components/json-editor.svelte';
	import type { DetectorConfig } from '$lib/schema';
	import { Input } from '$lib/components/ui/input';
	import { Label } from '$lib/components/ui/label';
	import * as NativeSelect from '$lib/components/ui/native-select';
	import {
		deleteDetector,
		getDetector,
		getDetectorPreset,
		getDetectorPresets,
		getDetectorSchema,
		saveDetector
	} from '$lib/remote/detector.remote';
	import { toast } from 'svelte-sonner';

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

	function mergeWithEmptyDetector(detector?: Partial<DetectorConfig>) {
		return {
			...EMPTY_DETECTOR,
			...detector,
			detection: {
				...EMPTY_DETECTOR.detection,
				...detector?.detection
			},
			yolo: {
				...EMPTY_DETECTOR.yolo,
				...detector?.yolo
			}
		};
	}

	const originalLabel = $state(page.url.searchParams.get('label') ?? '');
	const isEditing = $derived(!!originalLabel);
	const detectorPresets = $state(await getDetectorPresets());
	const detectorSchema = $state(await getDetectorSchema());
	const initialDetector = $derived(
		isEditing ? await getDetector({ label: originalLabel }) : undefined
	);
	const initialDetectorJson = $derived(
		JSON.stringify(mergeWithEmptyDetector(initialDetector?.detector), null, 2)
	);

	let label = $state(originalLabel);
	let detectorJson = $state(initialDetectorJson);
	let editorHasErrors = $state(false);

	async function handlePresetChange(event: Event) {
		const file = (event.currentTarget as HTMLSelectElement).value;
		if (!file) {
			detectorJson = initialDetectorJson;
			return;
		}

		const preset = await getDetectorPreset({ file });
		detectorJson = JSON.stringify(mergeWithEmptyDetector(preset), null, 2);
	}

	async function handleSave(event: SubmitEvent) {
		event.preventDefault();
		if (editorHasErrors) {
			return;
		}

		await saveDetector({
			original: originalLabel || undefined,
			detectorJson,
			meta: { label }
		});
		toast.success('Saved');
		await goto(resolve('/detectors'));
	}
</script>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">
			{isEditing ? 'Edit Detector' : 'Add Detector'}
		</h1>
		<p class="text-sm text-muted-foreground">Configure a detector.</p>
	</header>

	<form class="flex max-w-2xl flex-col gap-2" onsubmit={handleSave}>
		<Label for="label">Label</Label>
		<Input id="label" name="label" bind:value={label} placeholder="e.g. Detector X" />

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

		<Label>Detector Config</Label>
		<JsonEditor
			bind:value={detectorJson}
			bind:hasErrors={editorHasErrors}
			schema={detectorSchema}
			height={420}
		/>

		<div class="flex gap-2">
			{#if isEditing}
				<Button
					type="button"
					onclick={async () => {
						await deleteDetector({ label: originalLabel });
						await goto(resolve('/detectors'));
					}}
					variant="destructive"
					class="flex-1">Delete</Button
				>
			{/if}
			<Button type="submit" class="flex-1" disabled={editorHasErrors}>Save</Button>
		</div>
	</form>
</section>
