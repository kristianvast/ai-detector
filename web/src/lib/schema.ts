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

export interface TelegramConfig {
    token: string;
    chat: string;
}

export interface Config {
    [key: string]: unknown;
    detectors: DetectorConfig[];
}

export interface AppConfig {
    streams: StreamMeta[];
    telegrams: TelegramMeta[];
    detectors: DetectorMeta[];
}

export interface DetectorMeta {
    label: string;
    index: number;
}

export interface TelegramMeta extends TelegramConfig {
    label: string;
}

export interface StreamMeta {
    label?: string;
    source: string;
}
