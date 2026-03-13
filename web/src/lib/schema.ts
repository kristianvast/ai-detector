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

export const STAGES = ['approved', 'rejected', 'unvalidated'] as const;
export type Stage = (typeof STAGES)[number];
