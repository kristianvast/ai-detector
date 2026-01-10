import logging
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
    Detection,
    DetectionConfig,
    DetectorConfig,
    DiskConfig,
    ImageSet,
    VLMConfig,
    WebhookConfig,
    YoloConfig,
)
from aidetector.detections import Detections
from aidetector.exporters.disk import DiskExporter
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.telegram import TelegramExporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.validator import Validator
from aidetector.video import image_to_bytes


class Detector:
    logger = logging.getLogger(__name__)
    detection: DetectionConfig
    sources: list[str]
    yolo_config: YoloConfig | None = None
    validator: Validator
    exporters: list[Exporter]
    running: bool = True
    export_executor: ThreadPoolExecutor

    def __init__(
        self,
        detection: DetectionConfig,
        yolo_config: YoloConfig | None,
        validator: Validator,
        exporters: list[Exporter],
    ):
        self.detection = detection
        self.yolo_config = yolo_config
        self.validator = validator
        self.exporters = exporters
        self.export_executor = ThreadPoolExecutor()
        self.sources = [detection.source] if isinstance(detection.source, str) else detection.source

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

    def _generate_frames(self, source: str):
        last_yield_time = datetime.min
        if self.yolo_config:
            self.yolo = YOLO(self.yolo_config.model, task="detect")
            results = self.yolo.predict(
                source=source,
                conf=self.yolo_config.confidence,
                stream=True,
            )
            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                if result.boxes is not None and len(result.boxes) > 0:
                    last_yield_time = datetime.now()
                    best_box = max(result.boxes, key=lambda x: x.conf.item())  # type: ignore
                    x1, y1, x2, y2 = map(int, best_box.xyxy[0])
                    crop = result.orig_img[y1:y2, x1:x2]
                    yield Detection(
                        datetime.now(),
                        ImageSet(image_to_bytes(result.orig_img), image_to_bytes(result.plot()), image_to_bytes(crop)),
                        best_box.conf.item(),
                    )
        else:
            is_file = source.lower().endswith(tuple(IMG_FORMATS.union(VID_FORMATS)))
            is_stream = source.isnumeric() or not is_file

            results = LoadStreams(source) if is_stream else LoadImagesAndVideos(source)

            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detection.interval:
                    continue

                _, imgs, _ = result
                last_yield_time = datetime.now()
                yield Detection(datetime.now(), ImageSet(image_to_bytes(imgs), None, None), 0)

    def start(self):
        threads = []
        for source in self.sources:
            detections = Detections.from_config(self.yolo_config)

            def runner():
                for detection in self._generate_frames(source):
                    detections.add(detection)
                    self._try_export(detections)
                    detections.filter()
                self.export_executor.shutdown(wait=True)
                self.running = False

            thread = Thread(target=runner)
            thread.start()
            threads.append(thread)

            def timeout_poller():
                self._try_export(detections)
                if self.running:
                    sleep(1)
                    timeout_poller()

            self.export_executor.submit(timeout_poller)

        return threads

    def _try_export(self, detections: Detections):
        now: datetime = datetime.now()
        if not detections.get() or len(detections.get()) < (self.yolo_config.frames_min if self.yolo_config else 0):
            return

        time_collecting = (now - detections.first().date).total_seconds()
        timeout = (now - detections.last().date).total_seconds()
        time_collecting_exceeded = time_collecting > (self.yolo_config.time_max if self.yolo_config else 0)
        timeout_exceeded = timeout > (self.yolo_config.timeout if self.yolo_config and self.yolo_config.timeout else 0)

        if not time_collecting_exceeded and not timeout_exceeded:
            return

        self.logger.info(
            f"Exporting collection with {detections.length()} detections over {time_collecting} seconds with max confidence {detections.best().confidence}"
        )
        best_detection = detections.best()
        detections_copy = detections.get()

        def runner():
            is_validated = self.validator.validate(best_detection)
            if is_validated is False:
                self.logger.info("VLM made no detection, skipping export")
                return

            validated = is_validated is True

            for exporter in self.exporters:
                try:
                    exporter.export(best_detection, detections_copy, validated=validated)
                except Exception:
                    self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

        self.export_executor.submit(runner)

        detections.clear()
