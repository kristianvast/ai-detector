<script lang="ts">
	import { Input } from '$lib/components/ui/input/index.js';
	import * as NativeSelect from '$lib/components/ui/native-select/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import type { ConfidenceEditor } from '$lib/config-editor';

	interface Props {
		label: string;
		description?: string;
		value: ConfidenceEditor;
	}

	let { label, description, value = $bindable() }: Props = $props();
</script>

<div class="grid gap-3 rounded-lg border border-border/60 bg-background/80 p-4">
	<div class="space-y-1">
		<p class="text-sm font-medium">{label}</p>
		{#if description}
			<p class="text-xs text-muted-foreground">{description}</p>
		{/if}
	</div>

	<div class="grid gap-3 md:grid-cols-[12rem_1fr]">
		<NativeSelect.NativeSelect bind:value={value.mode}>
			<NativeSelect.NativeSelectOption value="none">Disabled</NativeSelect.NativeSelectOption>
			<NativeSelect.NativeSelectOption value="single">Single value</NativeSelect.NativeSelectOption>
			<NativeSelect.NativeSelectOption value="map">Per label</NativeSelect.NativeSelectOption>
		</NativeSelect.NativeSelect>

		{#if value.mode === 'single'}
			<Input type="number" min="0" step="0.01" bind:value={value.numberValue} />
		{:else if value.mode === 'map'}
			<Textarea
				rows={4}
				bind:value={value.mapText}
				placeholder="mounting=0.9\nstanding=0.5"
			/>
		{:else}
			<p class="rounded-md border border-dashed border-border/70 px-3 py-2 text-sm text-muted-foreground">
				No override. The runtime default will be used.
			</p>
		{/if}
	</div>
</div>
