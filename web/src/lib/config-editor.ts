import type {
	ChatConfig,
	Config,
	DiskConfig,
	HealthcheckConfig,
	OnnxConfig,
	VlmConfig,
	WebhookConfig,
	YoloConfig
} from '$lib/schema';

export const DEFAULT_SCHEMA_URL =
	'https://raw.githubusercontent.com/ESchouten/ai-detector/main/config/config.schema.json';

type ConfidenceValue = number | Record<string, number> | null | undefined;
type Arrayable<T> = T | T[] | null | undefined;
type StringListValue = string | string[] | null | undefined;

export interface ConfidenceEditor {
	mode: 'none' | 'single' | 'map';
	numberValue: number;
	mapText: string;
}

export interface DetectionEditor {
	sourceText: string;
	interval: number;
	frameRetention: number;
}

export interface YoloEditor {
	model: string;
	confidence: ConfidenceEditor;
	timeMax: number;
	timeout: number;
	cooldown: ConfidenceEditor;
	includeTrailingTime: number;
	framesMin: number | undefined;
	imgsz: number;
	strategy: 'LATEST' | 'ALL';
}

export interface VlmEditor {
	prompt: string;
	modelText: string;
	key: string;
	url: string;
	strategy: 'IMAGE' | 'VIDEO';
}

export interface DiskEditor {
	confidence: ConfidenceEditor;
	exportRejected: boolean;
	directory: string;
	strategy: 'ALL' | 'BEST';
}

export interface ChatEditor {
	token: string;
	chat: string;
	confidence: ConfidenceEditor;
	exportRejected: boolean;
	alertEvery: number;
	includePlot: boolean;
	includeCrop: boolean;
	includeVideo: boolean;
	videoWidth: number | undefined;
	videoCrf: number;
}

export interface WebhookEditor {
	url: string;
	confidence: ConfidenceEditor;
	exportRejected: boolean;
	token: string;
	dataType: 'binary' | 'base64';
	dataMax: number | undefined;
	includePlot: boolean;
	includeCrop: boolean;
	includeVideo: boolean;
	videoWidth: number | undefined;
	videoCrf: number;
}

export interface OnnxEditor {
	provider: string;
	winml: boolean;
	opset: number;
}

export interface HealthEditor {
	url: string;
	method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' | 'HEAD';
	interval: number;
	timeout: number;
	headersText: string;
	body: string;
}

export interface DetectorEditor {
	detection: DetectionEditor;
	yoloEnabled: boolean;
	yolo: YoloEditor;
	vlms: VlmEditor[];
	disks: DiskEditor[];
	telegrams: ChatEditor[];
	webhooks: WebhookEditor[];
}

export interface ConfigEditor {
	schemaUrl: string;
	detectors: DetectorEditor[];
	onnxEnabled: boolean;
	onnx: OnnxEditor;
	healthEnabled: boolean;
	health: HealthEditor;
}

export type ConfigDocument = Config & { $schema?: string };

function linesToText(value: StringListValue): string {
	if (Array.isArray(value)) {
		return value.join('\n');
	}

	return value ?? '';
}

function textToStringList(value: string): string | string[] {
	const entries = value
		.split('\n')
		.map((entry) => entry.trim())
		.filter(Boolean);

	if (entries.length <= 1) {
		return entries[0] ?? '';
	}

	return entries;
}

function normalizeConfidence(value: ConfidenceValue): ConfidenceEditor {
	if (value == null) {
		return {
			mode: 'none',
			numberValue: 0,
			mapText: ''
		};
	}

	if (typeof value === 'number') {
		return {
			mode: 'single',
			numberValue: value,
			mapText: ''
		};
	}

	const mapText = Object.entries(value)
		.map(([label, confidence]) => `${label}=${confidence}`)
		.join('\n');

	return {
		mode: 'map',
		numberValue: 0,
		mapText
	};
}

function parseNumericMap(text: string): Record<string, number> {
	const entries = text
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean);

	const output: Record<string, number> = {};

	for (const entry of entries) {
		const separatorIndex = entry.includes('=') ? entry.indexOf('=') : entry.indexOf(':');
		if (separatorIndex === -1) continue;

		const key = entry.slice(0, separatorIndex).trim();
		const rawValue = entry.slice(separatorIndex + 1).trim();
		const value = Number(rawValue);

		if (!key || Number.isNaN(value)) continue;
		output[key] = value;
	}

	return output;
}

function serializeConfidence(editor: ConfidenceEditor): number | Record<string, number> | null {
	if (editor.mode === 'none') {
		return null;
	}

	if (editor.mode === 'single') {
		return editor.numberValue;
	}

	const parsed = parseNumericMap(editor.mapText);
	return Object.keys(parsed).length > 0 ? parsed : null;
}

function normalizeArray<T>(value: Arrayable<T>): T[] {
	if (value == null) {
		return [];
	}

	return Array.isArray(value) ? value : [value];
}

function serializeArrayable<T>(value: T[]): T | T[] | null {
	if (value.length === 0) {
		return null;
	}

	return value.length === 1 ? value[0] : value;
}

function headersToText(headers: Record<string, string> | null | undefined): string {
	if (!headers) {
		return '';
	}

	return Object.entries(headers)
		.map(([key, value]) => `${key}: ${value}`)
		.join('\n');
}

function textToHeaders(text: string): Record<string, string> | null {
	const entries = text
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean);

	if (entries.length === 0) {
		return null;
	}

	const headers: Record<string, string> = {};
	for (const entry of entries) {
		const separatorIndex = entry.indexOf(':');
		if (separatorIndex === -1) continue;

		const key = entry.slice(0, separatorIndex).trim();
		const value = entry.slice(separatorIndex + 1).trim();
		if (!key) continue;
		headers[key] = value;
	}

	return Object.keys(headers).length > 0 ? headers : null;
}

function emptyToNull(value: string): string | null {
	const trimmed = value.trim();
	return trimmed.length > 0 ? trimmed : null;
}

export function createDefaultYoloEditor(): YoloEditor {
	return {
		model: '',
		confidence: normalizeConfidence(0),
		timeMax: 60,
		timeout: 5,
		cooldown: normalizeConfidence(0),
		includeTrailingTime: 1,
		framesMin: undefined,
		imgsz: 640,
		strategy: 'LATEST'
	};
}

export function createDefaultVlmEditor(): VlmEditor {
	return {
		prompt: '',
		modelText: '',
		key: '',
		url: '',
		strategy: 'VIDEO'
	};
}

export function createDefaultDiskEditor(): DiskEditor {
	return {
		confidence: normalizeConfidence(null),
		exportRejected: true,
		directory: '',
		strategy: 'BEST'
	};
}

export function createDefaultChatEditor(): ChatEditor {
	return {
		token: '',
		chat: '',
		confidence: normalizeConfidence(null),
		exportRejected: false,
		alertEvery: 1,
		includePlot: false,
		includeCrop: false,
		includeVideo: true,
		videoWidth: 1280,
		videoCrf: 28
	};
}

export function createDefaultWebhookEditor(): WebhookEditor {
	return {
		url: '',
		confidence: normalizeConfidence(null),
		exportRejected: false,
		token: '',
		dataType: 'binary',
		dataMax: undefined,
		includePlot: false,
		includeCrop: true,
		includeVideo: false,
		videoWidth: 1280,
		videoCrf: 28
	};
}

export function createDefaultDetectorEditor(): DetectorEditor {
	return {
		detection: {
			sourceText: '',
			interval: 0,
			frameRetention: 30
		},
		yoloEnabled: false,
		yolo: createDefaultYoloEditor(),
		vlms: [],
		disks: [],
		telegrams: [],
		webhooks: []
	};
}

export function createDefaultConfigEditor(): ConfigEditor {
	return {
		schemaUrl: DEFAULT_SCHEMA_URL,
		detectors: [createDefaultDetectorEditor()],
		onnxEnabled: false,
		onnx: {
			provider: '',
			winml: true,
			opset: 20
		},
		healthEnabled: false,
		health: {
			url: '',
			method: 'GET',
			interval: 60,
			timeout: 5,
			headersText: '',
			body: ''
		}
	};
}

function normalizeYolo(value: YoloConfig): YoloEditor {
	return {
		model: value.model,
		confidence: normalizeConfidence(value.confidence),
		timeMax: value.time_max,
		timeout: value.timeout,
		cooldown: normalizeConfidence(value.cooldown),
		includeTrailingTime: value.include_trailing_time,
		framesMin: value.frames_min,
		imgsz: value.imgsz,
		strategy: value.strategy
	};
}

function normalizeVlm(value: VlmConfig): VlmEditor {
	return {
		prompt: value.prompt,
		modelText: linesToText(value.model),
		key: value.key ?? '',
		url: value.url ?? '',
		strategy: value.strategy
	};
}

function normalizeDisk(value: DiskConfig): DiskEditor {
	return {
		confidence: normalizeConfidence(value.confidence),
		exportRejected: value.export_rejected,
		directory: value.directory ?? '',
		strategy: value.strategy
	};
}

function normalizeChat(value: ChatConfig): ChatEditor {
	return {
		token: value.token,
		chat: value.chat,
		confidence: normalizeConfidence(value.confidence),
		exportRejected: value.export_rejected,
		alertEvery: value.alert_every,
		includePlot: value.include_plot,
		includeCrop: value.include_crop,
		includeVideo: value.include_video,
		videoWidth: value.video_width ?? undefined,
		videoCrf: value.video_crf
	};
}

function normalizeWebhook(value: WebhookConfig): WebhookEditor {
	return {
		url: value.url,
		confidence: normalizeConfidence(value.confidence),
		exportRejected: value.export_rejected,
		token: value.token ?? '',
		dataType: value.data_type,
		dataMax: value.data_max ?? undefined,
		includePlot: value.include_plot,
		includeCrop: value.include_crop,
		includeVideo: value.include_video,
		videoWidth: value.video_width ?? undefined,
		videoCrf: value.video_crf
	};
}

export function normalizeConfigDocument(value: ConfigDocument): ConfigEditor {
	const defaults = createDefaultConfigEditor();

	return {
		schemaUrl: value.$schema ?? defaults.schemaUrl,
		detectors:
			value.detectors.length > 0
				? value.detectors.map((detector) => ({
						detection: {
							sourceText: linesToText(detector.detection.source),
							interval: detector.detection.interval,
							frameRetention: detector.detection.frame_retention
						},
						yoloEnabled: detector.yolo != null,
						yolo: detector.yolo ? normalizeYolo(detector.yolo) : createDefaultYoloEditor(),
						vlms: normalizeArray(detector.vlm).map(normalizeVlm),
						disks: normalizeArray(detector.exporters?.disk).map(normalizeDisk),
						telegrams: normalizeArray(detector.exporters?.telegram).map(normalizeChat),
						webhooks: normalizeArray(detector.exporters?.webhook).map(normalizeWebhook)
					}))
				: defaults.detectors,
		onnxEnabled: value.onnx != null,
		onnx: value.onnx
			? {
					provider: value.onnx.provider ?? '',
					winml: value.onnx.winml,
					opset: value.onnx.opset
				}
			: defaults.onnx,
		healthEnabled: value.health != null,
		health: value.health
			? {
					url: value.health.url,
					method: value.health.method,
					interval: value.health.interval,
					timeout: value.health.timeout,
					headersText: headersToText(value.health.headers),
					body: value.health.body ?? ''
				}
			: defaults.health
	};
}

function serializeYolo(editor: YoloEditor): YoloConfig {
	return {
		model: editor.model.trim(),
		confidence: serializeConfidence(editor.confidence) ?? 0,
		time_max: editor.timeMax,
		timeout: editor.timeout,
		cooldown: serializeConfidence(editor.cooldown) ?? 0,
		include_trailing_time: editor.includeTrailingTime,
		frames_min: editor.framesMin,
		imgsz: editor.imgsz,
		strategy: editor.strategy
	};
}

function serializeVlm(editor: VlmEditor): VlmConfig {
	return {
		prompt: editor.prompt.trim(),
		model: textToStringList(editor.modelText),
		key: emptyToNull(editor.key),
		url: emptyToNull(editor.url),
		strategy: editor.strategy
	};
}

function serializeDisk(editor: DiskEditor): DiskConfig {
	return {
		confidence: serializeConfidence(editor.confidence),
		export_rejected: editor.exportRejected,
		directory: emptyToNull(editor.directory),
		strategy: editor.strategy
	};
}

function serializeChat(editor: ChatEditor): ChatConfig {
	return {
		token: editor.token.trim(),
		chat: editor.chat.trim(),
		confidence: serializeConfidence(editor.confidence),
		export_rejected: editor.exportRejected,
		alert_every: editor.alertEvery,
		include_plot: editor.includePlot,
		include_crop: editor.includeCrop,
		include_video: editor.includeVideo,
		video_width: editor.videoWidth ?? null,
		video_crf: editor.videoCrf
	};
}

function serializeWebhook(editor: WebhookEditor): WebhookConfig {
	return {
		url: editor.url.trim(),
		confidence: serializeConfidence(editor.confidence),
		export_rejected: editor.exportRejected,
		token: emptyToNull(editor.token),
		data_type: editor.dataType,
		data_max: editor.dataMax ?? null,
		include_plot: editor.includePlot,
		include_crop: editor.includeCrop,
		include_video: editor.includeVideo,
		video_width: editor.videoWidth ?? null,
		video_crf: editor.videoCrf
	};
}

export function serializeConfigEditor(editor: ConfigEditor): ConfigDocument {
	const config: ConfigDocument = {
		detectors: editor.detectors.map((detector) => {
			const disks = detector.disks.map(serializeDisk);
			const telegrams = detector.telegrams.map(serializeChat);
			const webhooks = detector.webhooks.map(serializeWebhook);

			return {
				detection: {
					source: textToStringList(detector.detection.sourceText),
					interval: detector.detection.interval,
					frame_retention: detector.detection.frameRetention
				},
				yolo: detector.yoloEnabled ? serializeYolo(detector.yolo) : null,
				vlm: serializeArrayable(detector.vlms.map(serializeVlm)),
				exporters:
					disks.length > 0 || telegrams.length > 0 || webhooks.length > 0
						? {
								disk: serializeArrayable(disks),
								telegram: serializeArrayable(telegrams),
								webhook: serializeArrayable(webhooks)
							}
						: null
			};
		}),
		onnx: editor.onnxEnabled
			? {
					provider: emptyToNull(editor.onnx.provider),
					winml: editor.onnx.winml,
					opset: editor.onnx.opset
				}
			: undefined,
		health: editor.healthEnabled
			? {
					url: editor.health.url.trim(),
					method: editor.health.method,
					interval: editor.health.interval,
					timeout: editor.health.timeout,
					headers: textToHeaders(editor.health.headersText),
					body: emptyToNull(editor.health.body)
				}
			: null
	};

	if (editor.schemaUrl.trim()) {
		config.$schema = editor.schemaUrl.trim();
	}

	return config;
}

export function getConfigDocument(value: unknown): { config: unknown; schemaUrl?: string } {
	if (typeof value !== 'object' || value === null || Array.isArray(value)) {
		return { config: value };
	}

	const { $schema, ...config } = value as Record<string, unknown>;

	return {
		config,
		schemaUrl: typeof $schema === 'string' ? $schema : undefined
	};
}

