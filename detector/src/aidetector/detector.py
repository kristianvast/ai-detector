import logging
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Thread
from time import sleep
from typing import Self

from ultralytics import YOLO
from ultralytics.data.loaders import LoadImagesAndVideos, LoadStreams
from ultralytics.data.utils import IMG_FORMATS, VID_FORMATS

from aidetector.config import (
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
)
from aidetector.exporters.disk import DiskExporter
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.telegram import TelegramExporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.validator import Validator


class Detector:
    logger = logging.getLogger(__name__)
    detections: defaultdict[str, list[Detection]]
    detection: DetectionConfig
    yolo: YOLO | None
    yolo_config: YoloConfig | None
    validator: Validator
    exporters: list[Exporter]
    running: bool
    export_executor: ThreadPoolExecutor

    def __init__(
        self,
        detection: DetectionConfig,
        yolo_config: YoloConfig | None,
        validator: Validator,
        exporters: list[Exporter],
        override_source: str | None = None,
    ):
        self.detections = defaultdict(list)
        self.detection = detection
        self.yolo_config = yolo_config
        if yolo_config is not None:
            self.yolo = YOLO(yolo_config.model, task="detect")

        self.validator = validator
        self.exporters = exporters
        self.running = True
        self.export_executor = ThreadPoolExecutor()

        sources = (
            [override_source]
            if override_source
            else [detection.source]
            if isinstance(detection.source, str)
            else detection.source
        )
        is_file = sources[0].lower().endswith(tuple(IMG_FORMATS.union(VID_FORMATS)))
        is_stream = sources[0].isnumeric() or not is_file

        self.source = tempfile.mkstemp(suffix=".streams" if is_stream else ".txt", text=True)[1]
        with open(self.source, "w", encoding="utf-8") as f:
            f.write("\n".join(sources))

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig) -> list[Self]:
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

        return (
            [cls(detector.detection, detector.yolo, validator, exporters)]
            if detector.detection.batch
            else [
                cls(detector.detection, detector.yolo, validator, exporters, override_source=source)
                for source in detector.detection.source
            ]
        )

    def _generate_frames(self):
        last_yield_time = datetime.min
        if self.yolo and self.yolo_config:
            results = self.yolo.predict(
                source=self.source,
                conf=self.yolo_config.confidence,
                stream=True,
                # device="cpu" if directml.IS_AVAILABLE else None,
            )
            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                if result.boxes is not None and len(result.boxes) > 0:
                    last_yield_time = datetime.now()
                    best_box = max(result.boxes, key=lambda x: x.conf.item())  # type: ignore
                    x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                    self._process(
                        result.path,
                        Detection(
                            datetime.now(),
                            ImageSet(result.orig_img, result.plot(), Crop(x1, y1, x2, y2)),
                            best_box.conf.item(),
                        ),
                    )

        else:
            is_stream = self.source.endswith(".streams")

            results = LoadStreams(self.source) if is_stream else LoadImagesAndVideos(self.source)

            for sources, imgs, _ in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                last_yield_time = datetime.now()
                for source, img in zip(sources, imgs):
                    self._process(source, Detection(datetime.now(), ImageSet(img, None, None), 0))

    def start(self):
        def timeout_poller():
            while self.running:
                try:
                    self.logger.info("Polling for timeouts")
                    for source in self.detections:
                        self._process(source)
                except Exception:
                    self.logger.exception("Error in timeout poller")
                sleep(1)

        def runner():
            self._generate_frames()
            self.running = False
            self.export_executor.shutdown(wait=True)

        self.export_executor.submit(timeout_poller)
        thread = Thread(target=runner)
        thread.start()
        return thread

    def _process(self, source: str, detection: Detection | None = None):
        if self._exceeded_timeout(source):
            self._export(source)

        if detection:
            self.detections[source].append(detection)

        if self._exceeded_time(source):
            self._export(source)

    def _export(self, source: str):
        detections = self.detections[source]
        if self._has_min_detections(source):
            self.logger.info(
                f"Finished collecting with {len(detections)} detections over {(datetime.now() - detections[0].date).total_seconds()} seconds with max confidence {max(d.confidence for d in detections)}"
            )
            best_detection = max(detections, key=lambda x: x.confidence)

            def runner():
                validated = self.validator.validate(best_detection, detections)
                for exporter in self.exporters:
                    try:
                        exporter.export(best_detection, detections, validated)
                    except Exception:
                        self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

            self.export_executor.submit(runner)
        self.detections[source] = []

    def _has_min_detections(self, source: str) -> bool:
        return len(self.detections[source]) >= (self.yolo_config.frames_min if self.yolo_config else 0)

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
