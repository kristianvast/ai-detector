import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Thread
from time import sleep
from typing import Any, cast

from aidetector.detection.validator import Validator
from aidetector.exporters.disk import DiskExporter
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.telegram import TelegramExporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.sources.source import SourceProvider
from aidetector.utils.config import (
    ChatConfig,
    Config,
    Crop,
    Detection,
    DetectionConfig,
    DetectorConfig,
    DiskConfig,
    ImageSet,
    VLMConfig,
    WebhookConfig,
    YoloConfig,
    confidence_matches,
    max_confidence,
    min_confidence,
)
from numpy import ndarray
from typing_extensions import Self
from ultralytics import YOLO


class Detector:
    logger = logging.getLogger(__name__)
    detections: defaultdict[str, list[Detection]]
    detection: DetectionConfig
    yolo: YOLO | None
    yolo_config: YoloConfig | None
    yolo_class_confidences: dict[int, tuple[str, float]]
    source_provider: SourceProvider
    validator: Validator
    exporters: list[Exporter]
    running: bool
    export_executor: ThreadPoolExecutor
    last_frame_time: datetime

    def __init__(
        self,
        detection: DetectionConfig,
        yolo_config: YoloConfig | None,
        validator: Validator,
        exporters: list[Exporter],
    ):
        self.detections = defaultdict(list)
        self.detection = detection
        self.yolo_config = yolo_config
        self.yolo = None
        self.yolo_class_confidences = {}
        if yolo_config is not None:
            self.yolo = YOLO(yolo_config.model, task="detect")
            if not yolo_config.confidence:
                raise ValueError("yolo.confidence object cannot be empty")
            self.yolo_class_confidences = self._resolve_class_confidences(yolo_config.confidence)

        self.source_provider = SourceProvider(detection)
        self.validator = validator
        self.exporters = exporters
        self.running = True
        self.export_executor = ThreadPoolExecutor()
        self.last_frame_time = datetime.min

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig) -> list[Self]:
        exporters: list[Exporter] = []
        if detector.exporters is not None:
            config_exporter_map = {
                "telegram": (ChatConfig, TelegramExporter),
                "webhook": (WebhookConfig, WebhookExporter),
                "disk": (DiskConfig, DiskExporter),
            }

            for config_name, (config_cls, exporter_cls) in config_exporter_map.items():
                config_obj = getattr(detector.exporters, config_name, []) or []
                config_list = [config_obj] if isinstance(config_obj, config_cls) else config_obj
                for item in config_list:
                    exporters.append(exporter_cls.from_config(config, detector, cast(Any, item)))

        validator = Validator.from_config([detector.vlm] if isinstance(detector.vlm, VLMConfig) else detector.vlm or [])

        return [cls(detector.detection, detector.yolo, validator, exporters)]

    def _generate_frames(self):
        for batch in self.source_provider.iter_batches():
            if not self.running:
                return
            self._handle_frame_batch(batch)

    def _handle_frame_batch(self, batch: dict[str, list[tuple[datetime, ndarray]]]):
        if (datetime.now() - self.last_frame_time).total_seconds() < self.detection.interval:
            sleep_for = max(0, self.detection.interval - (datetime.now() - self.last_frame_time).total_seconds())
            self.logger.debug("Waiting for %f seconds before next detection", sleep_for)
            sleep(sleep_for)
            return
        self.last_frame_time = datetime.now()

        if self.yolo and self.yolo_config:
            results = self.yolo.predict(
                source=list(frames[-1][1] for frames in batch.values()),
                conf=min_confidence(self.yolo_config.confidence),
                stream=False,
                classes=list(self.yolo_class_confidences.keys()) or None,
                imgsz=self.yolo_config.imgsz,
            )
            for source, result in zip(batch.keys(), results):
                self._handle_yolo_result(source, result, batch[source])
            return

        for source, frames in batch.items():
            self._process(source, [Detection(frames[-1][0], ImageSet(frames[-1][1], None, None), 0)])

    def _handle_yolo_result(self, source: str, result, frames: list[tuple[datetime, ndarray]]):
        if self.yolo_config is None or result.boxes is None or len(result.boxes) == 0:
            return

        best_box = max(result.boxes, key=lambda x: x.conf.item())
        confidences: dict[str, float] = {}
        for box in result.boxes:
            class_id = int(box.cls.item())
            confidences[self.yolo_class_confidences[class_id][0]] = box.conf.item()

        if not confidence_matches(confidences, self.yolo_config.confidence):
            self.logger.debug("Confidence does not match")
            return

        x1, y1, x2, y2 = map(int, best_box.xyxy[0])

        detections = []
        for frames in frames[:-1]:
            detections.append(
                Detection(
                    frames[0],
                    ImageSet(frames[1], None, Crop(x1, y1, x2, y2)),
                    {},
                ),
            )
        detections.append(
            Detection(
                frames[-1][0],
                ImageSet(result.orig_img, result.plot(), Crop(x1, y1, x2, y2)),
                confidences,
            ),
        )
        self._process(source, detections)

    def start(self):
        def monitor_timeouts():
            self.logger.info("Starting timeout monitor")
            while self.running:
                self.logger.info("Checking for timeouts")
                try:
                    for source in list(self.detections.keys()):
                        self._process(source)
                except Exception:
                    self.logger.exception("Error in timeout monitor")
                sleep(1)

        def frame_producer():
            try:
                self._generate_frames()
            finally:
                self.running = False
                self.source_provider.close()
                self.export_executor.shutdown(wait=True)

        Thread(target=monitor_timeouts, daemon=True).start()
        thread = Thread(target=frame_producer)
        thread.start()
        return thread

    def _process(self, source: str, detections: list[Detection] | None = None):
        if self._exceeded_timeout(source):
            self._export(source)

        if detections:
            for detection in detections:
                self.detections[source].append(detection)

        if self._exceeded_time(source):
            self._export(source)

    def _resolve_class_confidences(self, confidence: float | dict[str, float]) -> dict[int, tuple[str, float]]:
        if not self.yolo:
            return {}

        class_confidences: dict[int, tuple[str, float]] = {
            class_id: (class_name, confidence[class_name] or 1 if isinstance(confidence, dict) else confidence)
            for class_id, class_name in self.yolo.names.items()
        }

        if isinstance(confidence, dict):
            for class_name, threshold in confidence.items():
                class_id = self.yolo.names.get(class_name)
                if class_id is None:
                    available_names = ", ".join(self.yolo.names[class_id] for class_id in sorted(self.yolo.names))
                    raise ValueError(
                        f"Unknown YOLO class name '{class_name}' in yolo.confidence. "
                        f"Available class names: {available_names}"
                    )

        return class_confidences

    def _export(self, source: str):
        detections = self.detections[source]
        if self._has_min_detections(source):
            best_detection = max(detections, key=lambda x: max_confidence(x.confidence))

            self.logger.info(
                "Finished collecting with %s detections over %s seconds with max confidence %s",
                len(detections),
                (datetime.now() - detections[0].date).total_seconds(),
                max_confidence(best_detection.confidence),
            )

            def export_task():
                validated = self.validator.validate(best_detection, detections)
                for exporter in self.exporters:
                    try:
                        exporter.export(best_detection, detections, validated)
                    except Exception:
                        self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

            self.export_executor.submit(export_task)
        self.detections[source] = []

    def _has_min_detections(self, source: str) -> bool:
        detections_with_confidence = [detection for detection in self.detections[source] if detection.confidence]
        return len(detections_with_confidence) >= (self.yolo_config.frames_min if self.yolo_config else 0)

    def _exceeded_time(self, source: str) -> bool:
        detections = self.detections[source]
        if not detections:
            return False
        now = datetime.now()
        time_collecting = (now - detections[0].date).total_seconds()
        time_collecting_exceeded = time_collecting > (self.yolo_config.time_max if self.yolo_config else 0)
        return time_collecting_exceeded

    def _exceeded_timeout(self, source: str) -> bool:
        detections = self.detections[source]
        if not detections:
            return False
        now = datetime.now()
        timeout = (now - detections[-1].date).total_seconds()
        return timeout > self.yolo_config.timeout if self.yolo_config and self.yolo_config.timeout else False
