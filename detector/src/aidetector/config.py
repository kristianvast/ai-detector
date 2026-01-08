import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic.dataclasses import dataclass


@dataclass
class Detection:
    date: datetime
    jpg: bytes
    confidence: float


def get_timestamped_filename(detection: Detection) -> str:
    rounded_confidence = round(detection.confidence, 3)
    timestamp = get_date_path(detection, "milliseconds")
    return f"{timestamp}_{rounded_confidence}.jpg"


def get_date_path(detection: Detection, timespec: Literal["seconds", "milliseconds"]) -> str:
    return detection.date.isoformat(timespec=timespec).replace(":", "-")


@dataclass(kw_only=True)
class YoloConfig:
    model: str
    confidence: float = 0
    time_max: int = 0
    timeout: int | None = None
    frames_min: int = 1


@dataclass(kw_only=True)
class DetectionConfig:
    source: str | list[str]
    interval: int = 0


@dataclass(kw_only=True)
class VLMConfig:
    prompt: str
    model: str | list[str]
    key: str | None = None
    url: str | None = None


@dataclass(kw_only=True)
class ExporterConfig:
    confidence: float | None = None


@dataclass(kw_only=True)
class ChatConfig(ExporterConfig):
    token: str
    chat: str


@dataclass(kw_only=True)
class WebhookConfig(ExporterConfig):
    url: str
    token: str
    data_type: Literal["binary", "base64"] = "binary"
    data_max: int | None = None


@dataclass(kw_only=True)
class DiskConfig(ExporterConfig):
    directory: Path


@dataclass
class ExportersConfig:
    disk: DiskConfig | list[DiskConfig] | None = None
    telegram: ChatConfig | list[ChatConfig] | None = None
    webhook: WebhookConfig | list[WebhookConfig] | None = None


@dataclass
class DetectorConfig:
    detection: DetectionConfig
    yolo: YoloConfig | None = None
    vlm: VLMConfig | list[VLMConfig] | None = None
    exporters: ExportersConfig | None = None


@dataclass
class Config:
    detectors: list[DetectorConfig]


config_json = json.load(open("config.json"))
if config_json is None:
    raise ValueError("Config file is empty or not found.")
config = Config(**config_json)
