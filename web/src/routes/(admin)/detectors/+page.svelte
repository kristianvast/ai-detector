<script lang="ts">
	import {
		createDefaultChatEditor,
		createDefaultConfigEditor,
		createDefaultDetectorEditor,
		createDefaultDiskEditor,
		createDefaultVlmEditor,
		createDefaultWebhookEditor,
		type ConfigEditor,
		type DetectorEditor
	} from '$lib/config-editor';
	import ConfidenceEditor from '$lib/components/detectors/confidence-editor.svelte';
	import { Alert, AlertDescription, AlertTitle } from '$lib/components/ui/alert/index.js';
	import { Button } from '$lib/components/ui/button/index.js';
	import * as Card from '$lib/components/ui/card/index.js';
	import { Checkbox } from '$lib/components/ui/checkbox/index.js';
	import { Input } from '$lib/components/ui/input/index.js';
	import * as NativeSelect from '$lib/components/ui/native-select/index.js';
	import { Textarea } from '$lib/components/ui/textarea/index.js';
	import { getEditableConfig, saveEditableConfig } from '$lib/remote/config.remote';

	const configQuery = getEditableConfig();

	let editor = $state<ConfigEditor>(createDefaultConfigEditor());
	let configPath = $state('');
	let loadIssues = $state<string[]>([]);
	let isReady = $state(false);
	let saveState = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveMessage = $state('');
	let saveIssues = $state<string[]>([]);
	let lastSavedPayload = $state(JSON.stringify(createDefaultConfigEditor()));

	const payload = $derived(JSON.stringify(editor));
	const hasChanges = $derived(payload !== lastSavedPayload);
	const detectorCount = $derived(editor.detectors.length);
	const sourceCount = $derived(
		editor.detectors.reduce(
			(total, detector) =>
				total +
				detector.detection.sourceText
					.split('\n')
					.map((entry) => entry.trim())
					.filter(Boolean).length,
			0
		)
	);

	$effect(() => {
		const current = configQuery.current;
		if (!current) return;

		if (!isReady || !hasChanges) {
			editor = current.config;
			configPath = current.configPath;
			loadIssues = current.loadIssues;
			lastSavedPayload = JSON.stringify(current.config);
			isReady = true;
		}
	});

	function resetEditor() {
		const current = configQuery.current;
		if (!current) return;

		editor = current.config;
		lastSavedPayload = JSON.stringify(current.config);
		saveState = 'idle';
		saveMessage = '';
		saveIssues = [];
	}

	function addDetector() {
		editor.detectors.push(createDefaultDetectorEditor());
	}

	function removeDetector(index: number) {
		if (editor.detectors.length === 1) return;
		editor.detectors.splice(index, 1);
	}

	function addVlm(detector: DetectorEditor) {
		detector.vlms.push(createDefaultVlmEditor());
	}

	function addDisk(detector: DetectorEditor) {
		detector.disks.push(createDefaultDiskEditor());
	}

	function addTelegram(detector: DetectorEditor) {
		detector.telegrams.push(createDefaultChatEditor());
	}

	function addWebhook(detector: DetectorEditor) {
		detector.webhooks.push(createDefaultWebhookEditor());
	}

	function removeArrayItem<T>(items: T[], index: number) {
		items.splice(index, 1);
	}

	async function saveConfig() {
		saveState = 'saving';
		saveMessage = '';
		saveIssues = [];

		try {
			const result = await saveEditableConfig(editor);
			if (!result.ok) {
				saveState = 'error';
				saveMessage = result.message;
				saveIssues = result.issues;
				return;
			}

			editor = result.config;
			lastSavedPayload = JSON.stringify(result.config);
			saveState = 'saved';
			saveMessage = result.message;
			saveIssues = [];
		} catch (error) {
			saveState = 'error';
			saveMessage = error instanceof Error ? error.message : 'Unexpected save error.';
			saveIssues = [];
		}
	}
</script>

<svelte:head>
	<title>Detectors</title>
</svelte:head>

<section class="space-y-6">
	<header class="space-y-1">
		<h1 class="text-2xl font-semibold tracking-tight">Detectors</h1>
		<p class="text-sm text-muted-foreground">
			Edit <code>{configPath || 'config.json'}</code> with structured fields instead of raw JSON.
		</p>
	</header>

	{#if configQuery.error}
		<Alert variant="destructive">
			<AlertTitle>Could not load config</AlertTitle>
			<AlertDescription>{configQuery.error.message}</AlertDescription>
		</Alert>
	{/if}

	{#if loadIssues.length > 0}
		<Alert variant="destructive">
			<AlertTitle>Config file could not be fully parsed</AlertTitle>
			<AlertDescription>
				<ul class="list-disc space-y-1 ps-5 text-sm">
					{#each loadIssues as issue, index (index)}
						<li>{issue}</li>
					{/each}
				</ul>
			</AlertDescription>
		</Alert>
	{/if}

	{#if saveState === 'saved' || saveState === 'error'}
		<Alert variant={saveState === 'error' ? 'destructive' : 'default'}>
			<AlertTitle>{saveState === 'error' ? 'Save failed' : 'Config saved'}</AlertTitle>
			<AlertDescription>
				<p>{saveMessage}</p>
				{#if saveIssues.length > 0}
					<ul class="mt-2 list-disc space-y-1 ps-5 text-sm">
						{#each saveIssues as issue, index (index)}
							<li>{issue}</li>
						{/each}
					</ul>
				{/if}
			</AlertDescription>
		</Alert>
	{/if}

	<div class="grid gap-4 md:grid-cols-3">
		<Card.Card>
			<Card.CardHeader>
				<Card.CardTitle>Detectors</Card.CardTitle>
				<Card.CardDescription>Total configured detector blocks.</Card.CardDescription>
			</Card.CardHeader>
			<Card.CardContent class="text-3xl font-semibold">{detectorCount}</Card.CardContent>
		</Card.Card>
		<Card.Card>
			<Card.CardHeader>
				<Card.CardTitle>Sources</Card.CardTitle>
				<Card.CardDescription>Total non-empty source entries.</Card.CardDescription>
			</Card.CardHeader>
			<Card.CardContent class="text-3xl font-semibold">{sourceCount}</Card.CardContent>
		</Card.Card>
		<Card.Card>
			<Card.CardHeader>
				<Card.CardTitle>Status</Card.CardTitle>
				<Card.CardDescription>Current editor state.</Card.CardDescription>
			</Card.CardHeader>
			<Card.CardContent class="text-base font-medium">
				{#if configQuery.loading && !isReady}
					Loading...
				{:else if saveState === 'saving'}
					Saving...
				{:else if hasChanges}
					Unsaved changes
				{:else}
					In sync
				{/if}
			</Card.CardContent>
		</Card.Card>
	</div>

	{#if !isReady && configQuery.loading}
		<Card.Card>
			<Card.CardContent class="py-10 text-sm text-muted-foreground">
				Loading detector configuration...
			</Card.CardContent>
		</Card.Card>
	{:else}
		<div class="grid gap-6">
			<Card.Card>
				<Card.CardHeader>
					<Card.CardTitle>Runtime</Card.CardTitle>
					<Card.CardDescription>
						Global runtime settings that apply outside individual detector blocks.
					</Card.CardDescription>
				</Card.CardHeader>
				<Card.CardContent class="grid gap-6">
					<div class="grid gap-2">
						<p class="text-sm font-medium">Schema URL</p>
						<Input
							bind:value={editor.schemaUrl}
							placeholder="https://raw.githubusercontent.com/..."
						/>
					</div>

					<div class="grid gap-4 lg:grid-cols-2">
						<Card.Card>
							<Card.CardHeader>
								<Card.CardTitle class="text-base">ONNX</Card.CardTitle>
								<Card.CardDescription>Inference runtime defaults.</Card.CardDescription>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-4">
								<label class="flex items-center gap-2 text-sm font-medium">
									<Checkbox bind:checked={editor.onnxEnabled} />
									Enabled
								</label>

								{#if editor.onnxEnabled}
									<div class="grid gap-4 md:grid-cols-2">
										<div class="grid gap-2">
											<p class="text-sm font-medium">Provider</p>
											<Input bind:value={editor.onnx.provider} placeholder="CPUExecutionProvider" />
										</div>
										<div class="grid gap-2">
											<p class="text-sm font-medium">Opset</p>
											<Input type="number" min="1" bind:value={editor.onnx.opset} />
										</div>
									</div>
									<label class="flex items-center gap-2 text-sm font-medium">
										<Checkbox bind:checked={editor.onnx.winml} />
										Use WinML
									</label>
								{/if}
							</Card.CardContent>
						</Card.Card>

						<Card.Card>
							<Card.CardHeader>
								<Card.CardTitle class="text-base">Healthcheck</Card.CardTitle>
								<Card.CardDescription>External heartbeat endpoint.</Card.CardDescription>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-4">
								<label class="flex items-center gap-2 text-sm font-medium">
									<Checkbox bind:checked={editor.healthEnabled} />
									Enabled
								</label>

								{#if editor.healthEnabled}
									<div class="grid gap-4">
										<div class="grid gap-2">
											<p class="text-sm font-medium">URL</p>
											<Input bind:value={editor.health.url} placeholder="https://example.com/health" />
										</div>
										<div class="grid gap-4 md:grid-cols-3">
											<div class="grid gap-2">
												<p class="text-sm font-medium">Method</p>
												<NativeSelect.NativeSelect bind:value={editor.health.method}>
													{#each ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'] as method (method)}
														<NativeSelect.NativeSelectOption value={method}>
															{method}
														</NativeSelect.NativeSelectOption>
													{/each}
												</NativeSelect.NativeSelect>
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Interval (s)</p>
												<Input type="number" min="1" bind:value={editor.health.interval} />
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Timeout (s)</p>
												<Input type="number" min="1" bind:value={editor.health.timeout} />
											</div>
										</div>
										<div class="grid gap-4 md:grid-cols-2">
											<div class="grid gap-2">
												<p class="text-sm font-medium">Headers</p>
												<Textarea
													rows={4}
													bind:value={editor.health.headersText}
													placeholder="Authorization: Bearer token\nX-App: ai-detector"
												/>
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Body</p>
												<Textarea
													rows={4}
													bind:value={editor.health.body}
													placeholder="Optional request body"
												/>
											</div>
										</div>
									</div>
								{/if}
							</Card.CardContent>
						</Card.Card>
					</div>
				</Card.CardContent>
			</Card.Card>

			<div class="flex items-center justify-between gap-3">
				<div>
					<h2 class="text-xl font-semibold">Detector Blocks</h2>
					<p class="text-sm text-muted-foreground">
						Each detector can have its own sources, models and exporters.
					</p>
				</div>
				<Button type="button" variant="outline" onclick={addDetector}>Add detector</Button>
			</div>

			{#each editor.detectors as detector, detectorIndex (detectorIndex)}
				<Card.Card>
					<Card.CardHeader>
						<div class="flex items-start justify-between gap-4">
							<div>
								<Card.CardTitle>Detector {detectorIndex + 1}</Card.CardTitle>
								<Card.CardDescription>
									Sources, models and exporters for this detector.
								</Card.CardDescription>
							</div>
							<Button
								type="button"
								variant="outline"
								disabled={editor.detectors.length === 1}
								onclick={() => removeDetector(detectorIndex)}
							>
								Remove
							</Button>
						</div>
					</Card.CardHeader>
					<Card.CardContent class="grid gap-4">
						<Card.Card>
							<Card.CardHeader>
								<Card.CardTitle class="text-base">Detection</Card.CardTitle>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-4 md:grid-cols-[1.6fr_1fr_1fr]">
								<div class="grid gap-2 md:row-span-2">
									<p class="text-sm font-medium">Sources</p>
									<Textarea
										rows={5}
										bind:value={detector.detection.sourceText}
										placeholder="rtsp://camera-1\nrtsp://camera-2"
									/>
									<p class="text-xs text-muted-foreground">One source per line.</p>
								</div>
								<div class="grid gap-2">
									<p class="text-sm font-medium">Interval</p>
									<Input type="number" min="0" step="0.1" bind:value={detector.detection.interval} />
								</div>
								<div class="grid gap-2">
									<p class="text-sm font-medium">Frame retention</p>
									<Input type="number" min="0" bind:value={detector.detection.frameRetention} />
								</div>
							</Card.CardContent>
						</Card.Card>

						<Card.Card>
							<Card.CardHeader>
								<Card.CardTitle class="text-base">YOLO</Card.CardTitle>
								<Card.CardDescription>Primary detection model.</Card.CardDescription>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-4">
								<label class="flex items-center gap-2 text-sm font-medium">
									<Checkbox bind:checked={detector.yoloEnabled} />
									Enabled
								</label>

								{#if detector.yoloEnabled}
									<div class="grid gap-4">
										<div class="grid gap-2">
											<p class="text-sm font-medium">Model</p>
											<Input bind:value={detector.yolo.model} placeholder="https://.../model.pt" />
										</div>
										<div class="grid gap-4 xl:grid-cols-2">
											<ConfidenceEditor
												label="Confidence"
												description="Use a single threshold or per-label overrides."
												bind:value={detector.yolo.confidence}
											/>
											<ConfidenceEditor
												label="Cooldown"
												description="Optional cooldown after a detection."
												bind:value={detector.yolo.cooldown}
											/>
										</div>
										<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
											<div class="grid gap-2">
												<p class="text-sm font-medium">Time max</p>
												<Input type="number" min="0" bind:value={detector.yolo.timeMax} />
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Timeout</p>
												<Input type="number" min="0" bind:value={detector.yolo.timeout} />
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Trailing time</p>
												<Input
													type="number"
													min="0"
													bind:value={detector.yolo.includeTrailingTime}
												/>
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Frames min</p>
												<Input type="number" min="0" bind:value={detector.yolo.framesMin} />
											</div>
											<div class="grid gap-2">
												<p class="text-sm font-medium">Image size</p>
												<Input type="number" min="1" bind:value={detector.yolo.imgsz} />
											</div>
										</div>
										<div class="grid gap-2 md:max-w-xs">
											<p class="text-sm font-medium">Strategy</p>
											<NativeSelect.NativeSelect bind:value={detector.yolo.strategy}>
												{#each ['LATEST', 'ALL'] as strategy (strategy)}
													<NativeSelect.NativeSelectOption value={strategy}>
														{strategy}
													</NativeSelect.NativeSelectOption>
												{/each}
											</NativeSelect.NativeSelect>
										</div>
									</div>
								{/if}
							</Card.CardContent>
						</Card.Card>

						<Card.Card>
							<Card.CardHeader>
								<div class="flex items-start justify-between gap-4">
									<div>
										<Card.CardTitle class="text-base">Vision-language models</Card.CardTitle>
										<Card.CardDescription>Optional prompt-based validation layer.</Card.CardDescription>
									</div>
									<Button type="button" variant="outline" onclick={() => addVlm(detector)}>
										Add VLM
									</Button>
								</div>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-4">
								{#each detector.vlms as vlm, vlmIndex (vlmIndex)}
									<Card.Card>
										<Card.CardHeader>
											<div class="flex items-start justify-between gap-4">
												<Card.CardTitle class="text-sm">VLM {vlmIndex + 1}</Card.CardTitle>
												<Button
													type="button"
													variant="outline"
													onclick={() => removeArrayItem(detector.vlms, vlmIndex)}
												>
													Remove
												</Button>
											</div>
										</Card.CardHeader>
										<Card.CardContent class="grid gap-4">
											<div class="grid gap-2">
												<p class="text-sm font-medium">Prompt</p>
												<Textarea rows={3} bind:value={vlm.prompt} />
											</div>
											<div class="grid gap-4 md:grid-cols-2">
												<div class="grid gap-2">
													<p class="text-sm font-medium">Models</p>
													<Textarea
														rows={4}
														bind:value={vlm.modelText}
														placeholder="gemini/model-a\ngemini/model-b"
													/>
												</div>
												<div class="grid gap-4">
													<div class="grid gap-2">
														<p class="text-sm font-medium">Key</p>
														<Input bind:value={vlm.key} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">URL</p>
														<Input bind:value={vlm.url} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Strategy</p>
														<NativeSelect.NativeSelect bind:value={vlm.strategy}>
															{#each ['VIDEO', 'IMAGE'] as strategy (strategy)}
																<NativeSelect.NativeSelectOption value={strategy}>
																	{strategy}
																</NativeSelect.NativeSelectOption>
															{/each}
														</NativeSelect.NativeSelect>
													</div>
												</div>
											</div>
										</Card.CardContent>
									</Card.Card>
								{:else}
									<p class="text-sm text-muted-foreground">No VLM configured for this detector.</p>
								{/each}
							</Card.CardContent>
						</Card.Card>

						<Card.Card>
							<Card.CardHeader>
								<Card.CardTitle class="text-base">Exporters</Card.CardTitle>
								<Card.CardDescription>Where validated detections should go.</Card.CardDescription>
							</Card.CardHeader>
							<Card.CardContent class="grid gap-6">
								<section class="grid gap-4">
									<div class="flex items-start justify-between gap-4">
										<div>
											<h3 class="font-medium">Disk</h3>
											<p class="text-sm text-muted-foreground">Write clips to local storage.</p>
										</div>
										<Button type="button" variant="outline" onclick={() => addDisk(detector)}>
											Add disk exporter
										</Button>
									</div>

									{#each detector.disks as disk, diskIndex (diskIndex)}
										<Card.Card>
											<Card.CardHeader>
												<div class="flex items-start justify-between gap-4">
													<Card.CardTitle class="text-sm">Disk exporter {diskIndex + 1}</Card.CardTitle>
													<Button
														type="button"
														variant="outline"
														onclick={() => removeArrayItem(detector.disks, diskIndex)}
													>
														Remove
													</Button>
												</div>
											</Card.CardHeader>
											<Card.CardContent class="grid gap-4">
												<div class="grid gap-4 md:grid-cols-2">
													<div class="grid gap-2">
														<p class="text-sm font-medium">Directory</p>
														<Input bind:value={disk.directory} placeholder="mounts" />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Strategy</p>
														<NativeSelect.NativeSelect bind:value={disk.strategy}>
															{#each ['BEST', 'ALL'] as strategy (strategy)}
																<NativeSelect.NativeSelectOption value={strategy}>
																	{strategy}
																</NativeSelect.NativeSelectOption>
															{/each}
														</NativeSelect.NativeSelect>
													</div>
												</div>
												<ConfidenceEditor
													label="Confidence"
													description="Optional confidence override for disk exports."
													bind:value={disk.confidence}
												/>
												<label class="flex items-center gap-2 text-sm font-medium">
													<Checkbox bind:checked={disk.exportRejected} />
													Export rejected detections
												</label>
											</Card.CardContent>
										</Card.Card>
									{:else}
										<p class="text-sm text-muted-foreground">No disk exporters configured.</p>
									{/each}
								</section>

								<section class="grid gap-4">
									<div class="flex items-start justify-between gap-4">
										<div>
											<h3 class="font-medium">Telegram</h3>
											<p class="text-sm text-muted-foreground">Send alerts to Telegram chats.</p>
										</div>
										<Button type="button" variant="outline" onclick={() => addTelegram(detector)}>
											Add Telegram exporter
										</Button>
									</div>

									{#each detector.telegrams as telegram, telegramIndex (telegramIndex)}
										<Card.Card>
											<Card.CardHeader>
												<div class="flex items-start justify-between gap-4">
													<Card.CardTitle class="text-sm">
														Telegram exporter {telegramIndex + 1}
													</Card.CardTitle>
													<Button
														type="button"
														variant="outline"
														onclick={() => removeArrayItem(detector.telegrams, telegramIndex)}
													>
														Remove
													</Button>
												</div>
											</Card.CardHeader>
											<Card.CardContent class="grid gap-4">
												<div class="grid gap-4 md:grid-cols-2">
													<div class="grid gap-2">
														<p class="text-sm font-medium">Token</p>
														<Input bind:value={telegram.token} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Chat</p>
														<Input bind:value={telegram.chat} />
													</div>
												</div>
												<ConfidenceEditor
													label="Confidence"
													description="Optional confidence override for Telegram alerts."
													bind:value={telegram.confidence}
												/>
												<div class="grid gap-4 md:grid-cols-3">
													<div class="grid gap-2">
														<p class="text-sm font-medium">Alert every</p>
														<Input type="number" min="1" bind:value={telegram.alertEvery} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Video width</p>
														<Input type="number" min="1" bind:value={telegram.videoWidth} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Video CRF</p>
														<Input type="number" min="0" bind:value={telegram.videoCrf} />
													</div>
												</div>
												<div class="grid gap-3 md:grid-cols-4">
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={telegram.exportRejected} />
														Export rejected
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={telegram.includePlot} />
														Include plot
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={telegram.includeCrop} />
														Include crop
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={telegram.includeVideo} />
														Include video
													</label>
												</div>
											</Card.CardContent>
										</Card.Card>
									{:else}
										<p class="text-sm text-muted-foreground">No Telegram exporters configured.</p>
									{/each}
								</section>

								<section class="grid gap-4">
									<div class="flex items-start justify-between gap-4">
										<div>
											<h3 class="font-medium">Webhook</h3>
											<p class="text-sm text-muted-foreground">Push detections to external endpoints.</p>
										</div>
										<Button type="button" variant="outline" onclick={() => addWebhook(detector)}>
											Add webhook exporter
										</Button>
									</div>

									{#each detector.webhooks as webhook, webhookIndex (webhookIndex)}
										<Card.Card>
											<Card.CardHeader>
												<div class="flex items-start justify-between gap-4">
													<Card.CardTitle class="text-sm">
														Webhook exporter {webhookIndex + 1}
													</Card.CardTitle>
													<Button
														type="button"
														variant="outline"
														onclick={() => removeArrayItem(detector.webhooks, webhookIndex)}
													>
														Remove
													</Button>
												</div>
											</Card.CardHeader>
											<Card.CardContent class="grid gap-4">
												<div class="grid gap-4 md:grid-cols-2">
													<div class="grid gap-2">
														<p class="text-sm font-medium">URL</p>
														<Input bind:value={webhook.url} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Token</p>
														<Input bind:value={webhook.token} />
													</div>
												</div>
												<ConfidenceEditor
													label="Confidence"
													description="Optional confidence override for webhook exports."
													bind:value={webhook.confidence}
												/>
												<div class="grid gap-4 md:grid-cols-4">
													<div class="grid gap-2">
														<p class="text-sm font-medium">Data type</p>
														<NativeSelect.NativeSelect bind:value={webhook.dataType}>
															{#each ['binary', 'base64'] as dataType (dataType)}
																<NativeSelect.NativeSelectOption value={dataType}>
																	{dataType}
																</NativeSelect.NativeSelectOption>
															{/each}
														</NativeSelect.NativeSelect>
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Data max</p>
														<Input type="number" min="1" bind:value={webhook.dataMax} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Video width</p>
														<Input type="number" min="1" bind:value={webhook.videoWidth} />
													</div>
													<div class="grid gap-2">
														<p class="text-sm font-medium">Video CRF</p>
														<Input type="number" min="0" bind:value={webhook.videoCrf} />
													</div>
												</div>
												<div class="grid gap-3 md:grid-cols-4">
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={webhook.exportRejected} />
														Export rejected
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={webhook.includePlot} />
														Include plot
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={webhook.includeCrop} />
														Include crop
													</label>
													<label class="flex items-center gap-2 text-sm font-medium">
														<Checkbox bind:checked={webhook.includeVideo} />
														Include video
													</label>
												</div>
											</Card.CardContent>
										</Card.Card>
									{:else}
										<p class="text-sm text-muted-foreground">No webhook exporters configured.</p>
									{/each}
								</section>
							</Card.CardContent>
						</Card.Card>
					</Card.CardContent>
				</Card.Card>
			{/each}

			<div class="flex items-center justify-between gap-3">
				<div class="text-sm text-muted-foreground">
					{#if hasChanges}
						You have unsaved changes.
					{:else}
						Everything matches the current config file.
					{/if}
				</div>
				<div class="flex items-center gap-2">
					<Button type="button" variant="outline" onclick={resetEditor} disabled={!hasChanges}>
						Reset
					</Button>
					<Button
						type="button"
						onclick={() => void saveConfig()}
						disabled={saveState === 'saving' || !hasChanges}
					>
						{saveState === 'saving' ? 'Saving...' : 'Save config'}
					</Button>
				</div>
			</div>
		</div>
	{/if}
</section>
