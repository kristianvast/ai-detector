import base64
from dataclasses import replace
from typing import Literal, Self

import cv2
import numpy as np
import requests

from aidetector.config import Config, Detection, DetectorConfig, WebhookConfig, get_timestamped_filename
from aidetector.exporters.exporter import Exporter


class WebhookExporter(Exporter):
    url: str
    token: str | None
    data_type: Literal["binary", "base64"]
    data_max: int | None

    def __init__(
        self,
        url: str,
        token: str | None,
        confidence: float,
        data_type: Literal["binary", "base64"],
        data_max: int | None,
    ):
        super().__init__(confidence)
        self.url = url
        self.token = token
        self.data_type = data_type
        self.data_max = data_max

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: WebhookConfig) -> Self:
        return cls(
            exporter.url,
            exporter.token,
            confidence=exporter.confidence or detector.detection.confidence,
            data_type=exporter.data_type,
            data_max=exporter.data_max,
        )

    def get_file(self, detection: Detection):
        if self.data_type == "base64":
            return None
        return {
            "photo": (
                get_timestamped_filename(detection),
                detection.jpg,
                "image/jpeg",
            )
        }

    def get_payload(self, detection: Detection):
        data = {
            "confidence": detection.confidence,
            "timestamp": detection.date.isoformat(),
        }
        if self.data_type == "base64":
            data["photo"] = base64.b64encode(detection.jpg).decode("utf-8")
        return data

    def get_headers(self):
        if self.token is None:
            return {}
        return {
            "Authorization": self.token,
        }

    def filtered_export(self, detections: list[Detection]):
        try:
            self.logger.info(f"Sending photo to webhook with confidence {detections[0].confidence}")
            headers = self.get_headers()

            detection = detections[0]
            jpg = detection.jpg

            if self.data_max is not None and len(jpg) > self.data_max:
                self.logger.info(f"Detection size {len(jpg)} exceeds data_max {self.data_max}, compressing jpg")

                # Decode image
                nparr = np.frombuffer(jpg, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                quality = 90
                scale = 1.0

                while len(jpg) > self.data_max and (quality > 10 or scale > 0.1):
                    if quality > 10:
                        quality -= 10
                    else:
                        scale *= 0.9
                        width = int(img.shape[1] * scale)
                        height = int(img.shape[0] * scale)
                        img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)

                    success, encoded_img = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                    if success:
                        jpg = encoded_img.tobytes()

                if len(jpg) > self.data_max:
                    self.logger.warning(
                        f"Could not compress image to under {self.data_max} bytes. Current size: {len(jpg)}"
                    )

                detection = replace(detection, jpg=jpg)

            files = self.get_file(detection)
            payload = self.get_payload(detection)
            if files is None:
                response = requests.post(self.url, headers=headers, json=payload)
            else:
                response = requests.post(self.url, headers=headers, data=payload, files=files)
            if response.status_code != 200:
                self.logger.error(f"Failed to send photo to webhook: {response.text}")
        except Exception as e:
            self.logger.error(f"Error sending photo to webhook: {e}")
