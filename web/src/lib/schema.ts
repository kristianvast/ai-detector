export const STAGES = ['approved', 'rejected', 'unvalidated'] as const;
export type Stage = (typeof STAGES)[number];

export const DEFAULT_SCHEMA_URL = 'https://raw.githubusercontent.com/ESchouten/ai-detector/main/config/config.schema.json';

export interface DetectorConfig {
    detection: {
        source: string | string[];
        [key: string]: unknown;
    };
    exporters?: {
        telegram?: TelegramConfig | TelegramConfig[];
        [key: string]: unknown;
    };
    [key: string]: unknown;
}

export interface Config {
    [key: string]: unknown;
    detectors: DetectorConfig[];
}

export interface AppConfig {
    streams: StreamConfig[];
    telegrams: TelegramConfig[];
}

export interface TelegramConfig {
    name: string;
    token: string;
    chat: string;
}

export interface StreamConfig {
    label?: string;
    source: string;
}
