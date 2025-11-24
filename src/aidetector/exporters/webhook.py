import base64
from typing import Literal, Self

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
            files = self.get_file(detections[0])
            payload = self.get_payload(detections[0])
            if files is None:
                response = requests.post(self.url, headers=headers, json=payload)
            else:
                response = requests.post(self.url, headers=headers, data=payload, files=files)
            if response.status_code != 200:
                self.logger.error(f"Failed to send photo to webhook: {response.text}")
        except Exception as e:
            self.logger.error(f"Error sending photo to webhook: {e}")
