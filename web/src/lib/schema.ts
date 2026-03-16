export const STAGES = ['approved', 'rejected', 'unvalidated'] as const;
export type Stage = (typeof STAGES)[number];

export const DEFAULT_SCHEMA_URL = 'https://raw.githubusercontent.com/ESchouten/ai-detector/main/config/config.schema.json';

export interface DetectorConfig {
    detection: {
        source: string | string[];
        [key: string]: unknown;
    };
    [key: string]: unknown;
}

export interface Config {
    [key: string]: unknown;
    app?: AppConfig;
    detectors: DetectorConfig[];
}

export interface AppConfig {
    streams: StreamConfig[];
}

export interface StreamConfig {
    label?: string;
    source: string;
}
