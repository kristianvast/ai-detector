import * as v from 'valibot';

export const metadataSchema = v.object({
	type: v.string(),
	timestamp: v.string(),
	validated: v.optional(v.nullable(v.boolean())),
	confidence: v.number(),
	confidences: v.record(v.string(), v.number()),
	detections: v.number(),
	start: v.string(),
	end: v.string(),
	duration: v.number(),
	crop: v.optional(
		v.object({
			x1: v.number(),
			y1: v.number(),
			x2: v.number(),
			y2: v.number()
		})
	)
});

export type Metadata = v.InferOutput<typeof metadataSchema>;

const confidenceByLabelSchema = v.record(v.string(), v.number());
const numericConfidenceSchema = v.union([v.number(), confidenceByLabelSchema]);
const nullableNumericConfidenceSchema = v.nullable(numericConfidenceSchema);
const stringArraySchema = v.array(v.string());
const stringOrStringArraySchema = v.union([v.string(), stringArraySchema]);
const stringHeadersSchema = v.record(v.string(), v.string());
const integerSchema = v.pipe(v.number(), v.integer());

export const chatConfigSchema = v.object({
	token: v.string(),
	chat: v.string(),
	confidence: v.optional(nullableNumericConfidenceSchema, null),
	export_rejected: v.optional(v.boolean(), false),
	alert_every: v.optional(integerSchema, 1),
	include_plot: v.optional(v.boolean(), false),
	include_crop: v.optional(v.boolean(), false),
	include_video: v.optional(v.boolean(), true),
	video_width: v.optional(v.nullable(integerSchema), 1280),
	video_crf: v.optional(integerSchema, 28)
});

export const detectionConfigSchema = v.object({
	source: stringOrStringArraySchema,
	interval: v.optional(v.number(), 0),
	frame_retention: v.optional(integerSchema, 30)
});

export const diskConfigSchema = v.object({
	confidence: v.optional(nullableNumericConfidenceSchema, null),
	export_rejected: v.optional(v.boolean(), true),
	directory: v.optional(v.nullable(v.string()), null),
	strategy: v.optional(v.picklist(['ALL', 'BEST']), 'BEST')
});

export const healthcheckConfigSchema = v.object({
	url: v.string(),
	method: v.optional(v.picklist(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD']), 'GET'),
	interval: v.optional(integerSchema, 60),
	timeout: v.optional(integerSchema, 5),
	headers: v.optional(v.nullable(stringHeadersSchema), null),
	body: v.optional(v.nullable(v.string()), null)
});

export const onnxConfigSchema = v.object({
	provider: v.optional(v.nullable(v.string()), null),
	winml: v.optional(v.boolean(), true),
	opset: v.optional(integerSchema, 20)
});

export const vlmConfigSchema = v.object({
	prompt: v.string(),
	model: stringOrStringArraySchema,
	key: v.optional(v.nullable(v.string()), null),
	url: v.optional(v.nullable(v.string()), null),
	strategy: v.optional(v.picklist(['IMAGE', 'VIDEO']), 'VIDEO')
});

export const webhookConfigSchema = v.object({
	url: v.string(),
	confidence: v.optional(nullableNumericConfidenceSchema, null),
	export_rejected: v.optional(v.boolean(), false),
	token: v.optional(v.nullable(v.string()), null),
	data_type: v.optional(v.picklist(['binary', 'base64']), 'binary'),
	data_max: v.optional(v.nullable(integerSchema), null),
	include_plot: v.optional(v.boolean(), false),
	include_crop: v.optional(v.boolean(), true),
	include_video: v.optional(v.boolean(), false),
	video_width: v.optional(v.nullable(integerSchema), 1280),
	video_crf: v.optional(integerSchema, 28)
});

export const yoloConfigSchema = v.object({
	model: v.string(),
	confidence: v.optional(numericConfidenceSchema, 0),
	time_max: v.optional(integerSchema, 60),
	timeout: v.optional(integerSchema, 5),
	cooldown: v.optional(numericConfidenceSchema, 0),
	include_trailing_time: v.optional(integerSchema, 1),
	frames_min: v.optional(integerSchema),
	imgsz: v.optional(integerSchema, 640),
	strategy: v.optional(v.picklist(['LATEST', 'ALL']), 'LATEST')
});

export const exportersConfigSchema = v.object({
	disk: v.optional(v.nullable(v.union([diskConfigSchema, v.array(diskConfigSchema)])), null),
	telegram: v.optional(v.nullable(v.union([chatConfigSchema, v.array(chatConfigSchema)])), null),
	webhook: v.optional(
		v.nullable(v.union([webhookConfigSchema, v.array(webhookConfigSchema)])),
		null
	)
});

export const detectorConfigSchema = v.object({
	detection: detectionConfigSchema,
	yolo: v.optional(v.nullable(yoloConfigSchema), null),
	vlm: v.optional(v.nullable(v.union([vlmConfigSchema, v.array(vlmConfigSchema)])), null),
	exporters: v.optional(v.nullable(exportersConfigSchema), null)
});

export const configSchema = v.object({
	detectors: v.array(detectorConfigSchema),
	onnx: v.optional(onnxConfigSchema),
	health: v.optional(v.nullable(healthcheckConfigSchema), null)
});

export type ChatConfig = v.InferOutput<typeof chatConfigSchema>;
export type DetectionConfig = v.InferOutput<typeof detectionConfigSchema>;
export type DiskConfig = v.InferOutput<typeof diskConfigSchema>;
export type ExportersConfig = v.InferOutput<typeof exportersConfigSchema>;
export type HealthcheckConfig = v.InferOutput<typeof healthcheckConfigSchema>;
export type OnnxConfig = v.InferOutput<typeof onnxConfigSchema>;
export type VlmConfig = v.InferOutput<typeof vlmConfigSchema>;
export type WebhookConfig = v.InferOutput<typeof webhookConfigSchema>;
export type YoloConfig = v.InferOutput<typeof yoloConfigSchema>;
export type DetectorConfig = v.InferOutput<typeof detectorConfigSchema>;
export type Config = v.InferOutput<typeof configSchema>;

export const STAGES = ['approved', 'rejected', 'unvalidated'] as const;
export type Stage = (typeof STAGES)[number];
