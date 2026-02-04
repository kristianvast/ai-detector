import logging
import os
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Thread
from time import sleep
from typing import Any, cast

from numpy import ndarray
from typing_extensions import Self
from ultralytics import YOLO
from ultralytics.data.loaders import LoadImagesAndVideos
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
from aidetector.streaming import StreamBatcher
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
        if yolo_config is not None:
            self.yolo = YOLO(yolo_config.model, task="detect")

        self.validator = validator
        self.exporters = exporters
        self.running = True
        self.export_executor = ThreadPoolExecutor()
        self.last_frame_time = datetime.min

        self.source = [detection.source] if isinstance(detection.source, str) else detection.source
        is_file = self.source[0].lower().endswith(tuple(IMG_FORMATS.union(VID_FORMATS)))
        self.is_stream = self.source[0].isnumeric() or not is_file

        if not self.is_stream:
            os_fd, src = tempfile.mkstemp(suffix=".txt", text=True)
            os.close(os_fd)
            with open(src, "w", encoding="utf-8") as f:
                f.write("\n".join(self.source))
            self.source = src

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
        if self.is_stream:
            batcher = StreamBatcher(cast(list[str], self.source))
            for batch in batcher:
                if not self.running:
                    batcher.stop()
                    break

                self._handle_frame_batch(batch)
            return

        if self.yolo and self.yolo_config:
            results = self.yolo.predict(
                source=self.source,
                conf=self.yolo_config.confidence,
                stream=True,
            )
            for result in results:
                self._handle_yolo_result(result.path, result)
            return

        results = LoadImagesAndVideos(self.source)
        self._handle_frame_batch({sources[0]: imgs[0] for sources, imgs, _ in results})

    def _handle_yolo_result(self, source: str, result):
        if result.boxes is None or len(result.boxes) == 0:
            return

        best_box = max(result.boxes, key=lambda x: x.conf.item())
        x1, y1, x2, y2 = map(int, best_box.xyxy[0])
        self._process(
            source,
            Detection(
                datetime.now(),
                ImageSet(result.orig_img, result.plot(), Crop(x1, y1, x2, y2)),
                best_box.conf.item(),
            ),
        )

    def _handle_frame_batch(self, batch: dict[str, ndarray]):
        if (datetime.now() - self.last_frame_time).total_seconds() < self.detection.interval:
            return
        self.last_frame_time = datetime.now()

        if self.yolo and self.yolo_config:
            results = self.yolo.predict(
                source=list(batch.values()),
                conf=self.yolo_config.confidence,
                stream=False,
            )
            for source, result in zip(batch.keys(), results):
                self._handle_yolo_result(source, result)
            return

        for source, frame in batch.items():
            self._process(source, Detection(datetime.now(), ImageSet(frame, None, None), 0))

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
            self._generate_frames()
            self.running = False
            self.export_executor.shutdown(wait=True)

        Thread(target=monitor_timeouts, daemon=True).start()
        thread = Thread(target=frame_producer)
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
