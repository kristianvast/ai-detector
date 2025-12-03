import base64
import logging
import tempfile
from datetime import datetime
from threading import Thread
from typing import Self

import cv2
from huggingface_hub.file_download import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_chat_format import (
    Qwen3VLChatHandler,  # <--- Use correct handler for Qwen
)
from ultralytics import YOLO
from ultralytics.data.utils import IMG_FORMATS, VID_FORMATS
from ultralytics.engine.results import Results

from aidetector.config import ChatConfig, Config, Detection, DetectionConfig, DetectorConfig, DiskConfig, WebhookConfig
from aidetector.exporters.disk import DiskExporter
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.telegram import TelegramExporter
from aidetector.exporters.webhook import WebhookExporter


class Detector:
    logger = logging.getLogger(__name__)
    detections: list[Detection] = []

    def get_or_download_model():
        repo_id = "unsloth/Qwen3-VL-30B-A3B-Instruct-GGUF"

        # 1. Define specific filenames
        # This 18GB file fits your 32GB Mac (Q4_K_M)
        model_filename = "Qwen3-VL-30B-A3B-Instruct-Q4_K_M.gguf"

        # The vision adapter (The "Eyes") - Standard name in Unsloth repo
        mmproj_filename = "mmproj-F16.gguf"

        print(f"⬇️  Checking model files from {repo_id}...")

        # Download or get cached path for the Vision Projector
        mmproj_path = hf_hub_download(repo_id=repo_id, filename=mmproj_filename)

        # Download or get cached path for the Main Model
        model_path = hf_hub_download(repo_id=repo_id, filename=model_filename)

        print(f"✅ Files ready:\n  - Model: {model_path}\n  - Projector: {mmproj_path}")
        return model_path, mmproj_path

    # --- Main Detection Logic ---

    # 1. Get paths (Download happens here if needed)
    model_path, mmproj_path = get_or_download_model()

    # 2. Set up the Vision Handler (Qwen2VL/3VL specific)
    chat_handler = Qwen3VLChatHandler(clip_model_path=mmproj_path)

    # 3. Load the Model into Memory (Metal/GPU)
    print("🚀 Loading model into memory...")
    llm = Llama(
        model_path=model_path,
        chat_handler=chat_handler,
        n_ctx=4096,  # Context size (don't go too high on 32GB RAM)
        n_gpu_layers=-1,  # -1 = Offload EVERYTHING to your M2 Max GPU
        verbose=False,  # Set to True if you want to see the layer loading logs
    )

    def __init__(
        self,
        model: str,
        sources: list[str],
        config: DetectionConfig,
        exporters: list[Exporter],
    ):
        self.config = config
        self.exporters = exporters
        self.logger.info(f"Loading model from {model}")
        self.model = YOLO(model, task="detect")

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

        return cls(detector.model, detector.sources, detector.detection, exporters)

    def start(self):
        def runner():
            results = self.model.predict(
                source=self.source,
                conf=self.config.confidence,
                stream=True,
            )
            for result in results:
                self._add_detection(result)
                self._try_export()
                self._filter_detections()

        Thread(target=runner).start()

    def _filter_detections(self):
        self.detections = [
            d for d in self.detections if (datetime.now() - d.date).total_seconds() <= self.config.time_max
        ]

    def _add_detection(self, result: Results):
        if result.boxes is not None and len(result.boxes) > 0:
            confidence = max(box.conf.item() for box in result.boxes)
            success, jpg = cv2.imencode(".jpg", result.orig_img)
            if not success:
                return

            self.detections.append(Detection(date=datetime.now(), jpg=jpg.tobytes(), confidence=confidence))

    def _try_export(self):
        now: datetime = datetime.now()
        if not self.detections or len(self.detections) < self.config.frames_min:
            return

        time_collecting = (now - self.detections[0].date).total_seconds()
        timeout = (now - self.detections[-1].date).total_seconds()

        if (time_collecting < self.config.time_max) and (
            self.config.timeout is None or (timeout < self.config.timeout)
        ):
            return

        self.logger.info(
            f"Exporting collection with {len(self.detections)} detections over {time_collecting} seconds with max confidence {max(d.confidence for d in self.detections)}"
        )
        sorted_detections = sorted(self.detections, key=lambda d: d.confidence, reverse=True)

        image_url = f"data:image/jpeg;base64,{base64.b64encode(sorted_detections[0].jpg).decode('utf-8')}"
        prompt = "In this image, do you see cows that are mounting each other?"
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = self.llm.create_chat_completion(messages=messages, max_tokens=128)
        output = response["choices"][0]["message"]["content"]
        self.logger.info(f"VLM Response: {output}")

        def runner():
            for exporter in self.exporters:
                try:
                    exporter.export(sorted_detections)
                except Exception:
                    self.logger.exception(f"Exporter {exporter.__class__.__name__} failed")

        Thread(target=runner, daemon=True).start()

        self.detections = []
