import base64
import json
import logging
import tempfile
from datetime import datetime
from threading import Thread
from typing import Self

import cv2
from llama_cpp import (
    ChatCompletionRequestMessage,
    ChatCompletionRequestMessageContentPartImage,
    ChatCompletionRequestMessageContentPartText,
    ChatCompletionRequestResponseFormat,
    ChatCompletionRequestUserMessage,
    Llama,
)
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


class Detector:
    logger = logging.getLogger(__name__)
    detections: list[Detection] = []

    detector_config: DetectionConfig
    yolo: YOLO | None = None
    vlm_config: VLMConfig | None = None
    llama: Llama | None = None

    exporters: list[Exporter]

    def __init__(
        self,
        sources: list[str],
        yolo: YoloConfig | None,
        vlm: VLMConfig | None,
        llama: Llama | None,
        exporters: list[Exporter],
    ):
        if yolo is not None:
            self.yolo = YOLO(yolo.model, task="detect")

        self.vlm_config = vlm

        detector_config = yolo or vlm
        if detector_config is None:
            raise ValueError("No detector")
        self.detector_config = detector_config
        self.exporters = exporters
        self.llama = llama

        is_file = sources[0].lower().endswith(tuple(IMG_FORMATS.union(VID_FORMATS)))
        is_stream = sources[0].isnumeric() or not is_file

        self.source = tempfile.mkstemp(suffix=".streams" if is_stream else ".txt", text=True)[1]
        with open(self.source, "w", encoding="utf-8") as f:
            f.write("\n".join(sources))

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, llama: Llama | None = None) -> Self:
        exporters: list[Exporter] = []
        if detector.exporters is not None:
            telegram_obj: list[ChatConfig] | ChatConfig = detector.exporters.telegram or []
            telegram_list: list[ChatConfig] = [
                x for x in (telegram_obj if isinstance(telegram_obj, list) else [telegram_obj]) if x is not None
            ]
            for telegram_exporter in telegram_list:
                exporters.append(TelegramExporter.from_config(config, detector, telegram_exporter))

            webhook_obj: list[WebhookConfig] | WebhookConfig = detector.exporters.webhook or []
            webhook_list: list[WebhookConfig] = [
                x for x in (webhook_obj if isinstance(webhook_obj, list) else [webhook_obj]) if x is not None
            ]
            for webhook_exporter in webhook_list:
                exporters.append(WebhookExporter.from_config(config, detector, webhook_exporter))

            disk_obj: list[DiskConfig] | DiskConfig = detector.exporters.disk or []
            disk_list: list[DiskConfig] = [
                x for x in (disk_obj if isinstance(disk_obj, list) else [disk_obj]) if x is not None
            ]
            for disk_exporter in disk_list:
                exporters.append(DiskExporter.from_config(config, detector, disk_exporter))

        return cls(detector.sources, detector.yolo, detector.vlm, llama, exporters)

    def _generate_frames(self):
        last_yield_time = datetime.min
        if self.yolo:
            results = self.yolo.predict(
                source=self.source,
                conf=self.detector_config.confidence,
                stream=True,
            )
            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detector_config.interval:
                    continue

                if result.boxes is not None and len(result.boxes) > 0:
                    last_yield_time = datetime.now()
                    yield [result.orig_img], max(box.conf.item() for box in result.boxes)
        else:
            is_stream = self.source.endswith(".streams")

            results = LoadStreams(self.source) if is_stream else LoadImagesAndVideos(self.source)

            for result in results:
                if (datetime.now() - last_yield_time).total_seconds() < self.detector_config.interval:
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

        Thread(target=runner).start()

    def _filter_detections(self):
        self.detections = [
            d for d in self.detections if (datetime.now() - d.date).total_seconds() <= self.detector_config.time_max
        ]

    def _add_detection(self, imgs, confidence: float):
        for img in imgs:
            success, jpg = cv2.imencode(".jpg", img)
            if not success:
                return

            self.detections.append(Detection(date=datetime.now(), jpg=jpg.tobytes(), confidence=confidence))

    def _try_export(self):
        now: datetime = datetime.now()
        if not self.detections or len(self.detections) < self.detector_config.frames_min:
            return

        time_collecting = (now - self.detections[0].date).total_seconds()
        timeout = (now - self.detections[-1].date).total_seconds()

        if (time_collecting < self.detector_config.time_max) and (
            self.detector_config.timeout is None or (timeout < self.detector_config.timeout)
        ):
            return

        self.logger.info(
            f"Exporting collection with {len(self.detections)} detections over {time_collecting} seconds with max confidence {max(d.confidence for d in self.detections)}"
        )
        sorted_detections = sorted(self.detections, key=lambda d: d.confidence, reverse=True)

        def runner():
            if not self._try_vlm(sorted_detections[0]):
                self.logger.info("VLM made no detection, skipping export")
                return

            for exporter in self.exporters:
                try:
                    exporter.export(sorted_detections)
                except Exception:
                    self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

        Thread(target=runner).start()

        self.detections = []

    def _try_vlm(self, detection: Detection) -> bool:
        if self.llama is None or self.vlm_config is None:
            return True

        image_url = f"data:image/jpeg;base64,{base64.b64encode(detection.jpg).decode('utf-8')}"
        prompt = self.vlm_config.prompt
        messages: list[ChatCompletionRequestMessage] = [
            ChatCompletionRequestUserMessage(
                role="user",
                content=[
                    ChatCompletionRequestMessageContentPartImage(type="image_url", image_url={"url": image_url}),
                    ChatCompletionRequestMessageContentPartText(type="text", text=prompt),
                ],
            )
        ]

        json_schema: ChatCompletionRequestResponseFormat = {
            "type": "json_object",
            "schema": {
                "type": "object",
                "properties": {
                    "detected": {"type": "boolean"},
                    "confidence": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["detected", "confidence"],
            },
        }

        response = self.llama.create_chat_completion(messages=messages, max_tokens=128, response_format=json_schema)
        output = json.loads(response["choices"][0]["message"]["content"])
        self.logger.info(f"VLM detected {output}")
        if output["confidence"] < self.vlm_config.confidence:
            return False
        return output["detected"]
