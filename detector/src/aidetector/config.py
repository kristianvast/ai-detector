import json
import logging
from dataclasses import field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import requests
from pydantic import ValidationError
from pydantic.dataclasses import dataclass

from aidetector.version import REF_NAME

logger = logging.getLogger(__name__)

template_url = f"https://raw.githubusercontent.com/ESchouten/ai-detector/{REF_NAME}/config/config.template.json"
schema_url = f"https://raw.githubusercontent.com/ESchouten/ai-detector/{REF_NAME}/config/config.schema.json"


def get_template() -> Any | None:
    try:
        template = requests.get(template_url).json()
        template["$schema"] = schema_url
        return template
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch template from {template_url}: {e}")
        return None


@dataclass
class ImageSet:
    jpg: bytes
    plot: bytes | None
    crop: bytes | None


@dataclass
class Detection:
    date: datetime
    images: ImageSet
    confidence: float


def get_timestamped_filename(detection: Detection) -> str:
    rounded_confidence = round(detection.confidence, 3)
    timestamp = get_date_path(detection, "milliseconds")
    return f"{timestamp}_{rounded_confidence}.jpg"


def get_date_path(detection: Detection, timespec: Literal["seconds", "milliseconds"]) -> str:
    return detection.date.isoformat(timespec=timespec).replace(":", "-")


def _default_frames_min() -> int:
    try:
        import torch

        if torch.cuda.is_available():
            return 6
    except ImportError:
        pass
    return 3


@dataclass(kw_only=True)
class YoloConfig:
    model: str
    confidence: float = 0
    time_max: int = 60
    timeout: int = 5
    frames_min: int = field(default_factory=_default_frames_min)


@dataclass(kw_only=True)
class DetectionConfig:
    source: str | list[str]
    interval: int = 0
    batch: bool = False


@dataclass(kw_only=True)
class VLMConfig:
    prompt: str
    model: str | list[str]
    key: str | None = None
    url: str | None = None


@dataclass(kw_only=True)
class ExporterConfig:
    confidence: float | None = None
    export_rejected: bool = False


@dataclass(kw_only=True)
class ChatConfig(ExporterConfig):
    token: str
    chat: str
    alert_every: int = 1
    include_plot: bool = True
    include_crop: bool = True
    include_video: bool = True
    video_width: int | None = 1280
    video_crf: int = 28


@dataclass(kw_only=True)
class WebhookConfig(ExporterConfig):
    url: str
    token: str
    data_type: Literal["binary", "base64"] = "binary"
    data_max: int | None = None
    include_plot: bool = True
    include_crop: bool = False
    include_video: bool = False
    video_width: int | None = 1280
    video_crf: int = 28


@dataclass(kw_only=True)
class DiskConfig(ExporterConfig):
    directory: Path
    strategy: Literal["ALL", "BEST"] = "BEST"
    export_rejected: bool = True


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


def format_validation_errors(error: ValidationError) -> str:
    messages = []
    for err in error.errors():
        location = " -> ".join(str(loc) for loc in err["loc"])
        msg = err["msg"]
        messages.append(f"  • {location}: {msg}")
    return "\n".join(messages)


def load_config(config_path: Path = Path("config.json")) -> Config:
    if not config_path.exists():
        template = get_template()
        if template:
            with open(config_path, "w") as f:
                json.dump(template, f, indent=4)
            logger.warning(f"Created {config_path} from template. Please edit the configuration before running.")
            raise FileNotFoundError(f"Configure before running: {config_path}")
        else:
            logger.error(f"Configuration file not found: {config_path}")
            logger.error("Create a config.json file. See: https://github.com/ESchouten/ai-detector")
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

    try:
        with open(config_path) as f:
            config_json = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {config_path}: {e}")
        raise ValueError(f"Invalid JSON in {config_path}: {e}")

    if config_json is None:
        logger.error(f"Config file is empty: {config_path}")
        raise ValueError(f"Config file is empty: {config_path}")

    try:
        config_json["$schema"] = schema_url
        with open(config_path, "w") as f:
            json.dump(config_json, f, indent=4)
    except Exception as e:
        logger.warning(f"Failed to update schema in {config_path}: {e}")

    try:
        return Config(**config_json)
    except ValidationError as e:
        logger.error(f"Configuration validation failed for {config_path}:")
        logger.error(format_validation_errors(e))
        raise ValueError(f"Configuration validation failed for {config_path}:\n{format_validation_errors(e)}")


config = load_config()
