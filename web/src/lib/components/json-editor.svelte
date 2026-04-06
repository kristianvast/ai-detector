<script lang="ts">
	import loader from '@monaco-editor/loader';
	import { onMount } from 'svelte';
	import type * as Monaco from 'monaco-editor';

	type MonacoModule = typeof import('monaco-editor');
	type DiagnosticMessage = {
		key: string;
		severity: 'error' | 'warning';
		message: string;
		startLineNumber: number;
		startColumn: number;
	};

	interface Props {
		value: string;
		hasErrors?: boolean;
		schema?: Record<string, unknown>;
		height?: number;
	}

	let {
		value = $bindable(),
		hasErrors = $bindable(false),
		schema,
		height = 600
	}: Props = $props();

	let monaco: MonacoModule | undefined;
	let editor: Monaco.editor.IStandaloneCodeEditor | undefined;
	let model: Monaco.editor.ITextModel | undefined;
	let markerListener: Monaco.IDisposable | undefined;
	let editorContainer: HTMLElement;
	let diagnostics = $state<DiagnosticMessage[]>([]);

	function syncDiagnostics() {
		const monacoInstance = monaco;
		const modelInstance = model;
		if (!monacoInstance || !modelInstance) {
			diagnostics = [];
			hasErrors = false;
			return;
		}

		const markers = monacoInstance.editor
			.getModelMarkers({ resource: modelInstance.uri })
			.filter(
				(marker) =>
					marker.severity === monacoInstance.MarkerSeverity.Error ||
					marker.severity === monacoInstance.MarkerSeverity.Warning
			)
			.sort(
				(left, right) =>
					right.severity - left.severity ||
					left.startLineNumber - right.startLineNumber ||
					left.startColumn - right.startColumn
			);

		diagnostics = markers.map((marker) => ({
			key: `${marker.severity}-${marker.startLineNumber}-${marker.startColumn}-${marker.message}`,
			severity: marker.severity === monacoInstance.MarkerSeverity.Error ? 'error' : 'warning',
			message: marker.message,
			startLineNumber: marker.startLineNumber,
			startColumn: marker.startColumn
		}));
		hasErrors = diagnostics.length > 0;
	}

	function configureDiagnostics(nextSchema: Record<string, unknown> | undefined) {
		const monacoInstance = monaco;
		const modelInstance = model;
		if (!monacoInstance || !modelInstance) {
			return;
		}

		const defaults = monacoInstance.json.jsonDefaults.diagnosticsOptions;
		monacoInstance.json.jsonDefaults.setDiagnosticsOptions({
			...defaults,
			validate: true,
			enableSchemaRequest: false,
			schemas: nextSchema
				? [
						{
							uri: `${modelInstance.uri.toString()}/schema`,
							fileMatch: [modelInstance.uri.toString()],
							schema: nextSchema
						}
					]
				: []
		});
	}

	onMount(() => {
		let disposed = false;
		let contentListener: Monaco.IDisposable | undefined;

		(async () => {
			const monacoEditor = await import('monaco-editor');
			if (disposed) {
				return;
			}

			loader.config({ monaco: monacoEditor });
			const monacoInstance = await loader.init();
			monaco = monacoInstance;

			if (disposed) {
				return;
			}

			const modelInstance = monacoInstance.editor.createModel(
				value,
				'json',
				monacoInstance.Uri.parse(`inmemory://json-editor/${crypto.randomUUID()}.json`)
			);
			model = modelInstance;

			editor = monacoInstance.editor.create(editorContainer, {
				model: modelInstance,
				automaticLayout: true,
				overviewRulerLanes: 0,
				overviewRulerBorder: false,
				wordWrap: 'on'
			});

			contentListener = modelInstance.onDidChangeContent(() => {
				value = modelInstance.getValue();
			});

			markerListener = monacoInstance.editor.onDidChangeMarkers((resources: readonly Monaco.Uri[]) => {
				const resource = modelInstance.uri.toString();
				if (resources.some((uri: Monaco.Uri) => uri.toString() === resource)) {
					syncDiagnostics();
				}
			});

			configureDiagnostics(schema);
			syncDiagnostics();
		})().catch((error) => {
			console.error('Failed to initialize Monaco editor', error);
		});

		return () => {
			disposed = true;
			contentListener?.dispose();
			markerListener?.dispose();
			editor?.dispose();
			model?.dispose();
			diagnostics = [];
			hasErrors = false;
		};
	});

	$effect(() => {
		const nextValue = value;
		const modelInstance = model;
		if (modelInstance && modelInstance.getValue() !== nextValue) {
			modelInstance.setValue(nextValue);
		}
	});

	$effect(() => {
		const nextSchema = schema;
		if (!monaco || !model) {
			return;
		}

		configureDiagnostics(nextSchema);
	});
</script>

<div class="space-y-2">
	<div class="editor-container" bind:this={editorContainer} style={`height: ${height}px`}></div>

	{#if diagnostics.length > 0}
		<div class="space-y-1">
			{#each diagnostics as diagnostic (diagnostic.key)}
				<p
					class:text-destructive={diagnostic.severity === 'error'}
					class="text-sm"
					class:text-amber-600={diagnostic.severity === 'warning'}
				>
					Line {diagnostic.startLineNumber}, column {diagnostic.startColumn}: {diagnostic.message}
				</p>
			{/each}
		</div>
	{/if}
</div>

<style>
	.editor-container {
		width: 100%;
		padding: 0;
		border-radius: 1rem;
	}
</style>
