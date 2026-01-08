import logging
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Thread
from typing import Self

import cv2
from ultralytics import YOLO
from ultralytics.data.loaders import LoadImagesAndVideos, LoadStreams
from ultralytics.data.utils import IMG_FORMATS, VID_FORMATS

from aidetector.config import (
    ChatConfig,
    Config,
    Detection,
    DetectionConfig,
    DetectorConfig,
    DiskConfig,
    VLMConfig,
    WebhookConfig,
    YoloConfig,
)
from aidetector.exporters.disk import DiskExporter
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.telegram import TelegramExporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.validator import Validator


class Detector:
    logger = logging.getLogger(__name__)
    detections: list[Detection] = []
    detection: DetectionConfig
    yolo: YOLO | None = None
    yolo_config: YoloConfig | None = None
    validator: Validator
    exporters: list[Exporter]

    def __init__(
        self,
        detection: DetectionConfig,
        yolo_config: YoloConfig | None,
        validator: Validator,
        exporters: list[Exporter],
    ):
        self.detection = detection
        self.yolo_config = yolo_config
        if yolo_config is not None:
            self.yolo = YOLO(yolo_config.model, task="detect")

        self.validator = validator
        self.exporters = exporters
        self.export_executor = ThreadPoolExecutor()

        sources = [detection.source] if isinstance(detection.source, str) else detection.source
        is_file = sources[0].lower().endswith(tuple(IMG_FORMATS.union(VID_FORMATS)))
        is_stream = sources[0].isnumeric() or not is_file

        self.source = tempfile.mkstemp(suffix=".streams" if is_stream else ".txt", text=True)[1]
        with open(self.source, "w", encoding="utf-8") as f:
            f.write("\n".join(sources))

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig) -> Self:
        exporters: list[Exporter] = []
        if detector.exporters is not None:
            telegram_obj: list[ChatConfig] | ChatConfig = detector.exporters.telegram or []
            telegram_list: list[ChatConfig] = [telegram_obj] if isinstance(telegram_obj, ChatConfig) else telegram_obj
            for telegram_exporter in telegram_list:
                exporters.append(TelegramExporter.from_config(config, detector, telegram_exporter))

            webhook_obj: list[WebhookConfig] | WebhookConfig = detector.exporters.webhook or []
            webhook_list: list[WebhookConfig] = [webhook_obj] if isinstance(webhook_obj, WebhookConfig) else webhook_obj
            for webhook_exporter in webhook_list:
                exporters.append(WebhookExporter.from_config(config, detector, webhook_exporter))

            disk_obj: list[DiskConfig] | DiskConfig = detector.exporters.disk or []
            disk_list: list[DiskConfig] = [disk_obj] if isinstance(disk_obj, DiskConfig) else disk_obj
            for disk_exporter in disk_list:
                exporters.append(DiskExporter.from_config(config, detector, disk_exporter))

        validator = Validator.from_config([detector.vlm] if isinstance(detector.vlm, VLMConfig) else detector.vlm or [])

        return cls(detector.detection, detector.yolo, validator, exporters)

    def _generate_frames(self):
        last_yield_time = datetime.min
        if self.yolo and self.yolo_config:
            results = self.yolo.predict(
                source=self.source,
                conf=self.yolo_config.confidence,
                stream=True,
            )
            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                if result.boxes is not None and len(result.boxes) > 0:
                    last_yield_time = datetime.now()
                    yield (
                        [result.orig_img],
                        max(box.conf.item() for box in result.boxes),
                    )
        else:
            is_stream = self.source.endswith(".streams")

            results = LoadStreams(self.source) if is_stream else LoadImagesAndVideos(self.source)

            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                _, imgs, _ = result
                last_yield_time = datetime.now()
                yield imgs, 0

    def start(self):
        def runner():
            for imgs, confidence in self._generate_frames():
                self._add_detection(imgs, confidence)
                self._try_export()
                self._filter_detections()
            self.export_executor.shutdown(wait=True)

        thread = Thread(target=runner)
        thread.start()
        return thread

    def _filter_detections(self):
        self.detections = [
            d
            for d in self.detections
            if (datetime.now() - d.date).total_seconds() <= (self.yolo_config.time_max if self.yolo_config else 0)
        ]

    def _add_detection(self, imgs, confidence: float):
        for img in imgs:
            success, jpg = cv2.imencode(".jpg", img)
            if not success:
                return

            self.detections.append(Detection(date=datetime.now(), jpg=jpg.tobytes(), confidence=confidence))

    def _try_export(self):
        now: datetime = datetime.now()
        if not self.detections or len(self.detections) < (self.yolo_config.time_max if self.yolo_config else 0):
            return

        time_collecting = (now - self.detections[0].date).total_seconds()
        timeout = (now - self.detections[-1].date).total_seconds()

        if (time_collecting < (self.yolo_config.time_max if self.yolo_config else 0)) and (
            (self.yolo_config.time_max if self.yolo_config else 0) is None
            or (timeout < (self.yolo_config.time_max if self.yolo_config else 0))
        ):
            return

        self.logger.info(
            f"Exporting collection with {len(self.detections)} detections over {time_collecting} seconds with max confidence {max(d.confidence for d in self.detections)}"
        )
        sorted_detections = sorted(self.detections, key=lambda d: d.confidence, reverse=True)

        def runner():
            is_validated = self.validator.validate(sorted_detections[0])
            if is_validated is False:
                self.logger.info("VLM made no detection, skipping export")
                return

            validated = is_validated is True

            for exporter in self.exporters:
                try:
                    exporter.export(sorted_detections, validated=validated)
                except Exception:
                    self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

        self.export_executor.submit(runner)

        self.detections = []
