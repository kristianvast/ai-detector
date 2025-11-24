from typing import Self

from aidetector.config import ChatConfig, Config, Detection, DetectorConfig
from aidetector.exporters.webhook import WebhookExporter


class TelegramExporter(WebhookExporter):
    chat: str

    def __init__(self, token: str, chat: str, confidence: float):
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        super().__init__(url, token, confidence, "binary", 0)
        self.chat = chat

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: ChatConfig) -> Self:
        return cls(
            exporter.token,
            exporter.chat,
            confidence=exporter.confidence or detector.detection.confidence,
        )

    def get_payload(self, detections: list[Detection]):
        return {
            "chat_id": self.chat,
            "caption": "👍 / 👎",
        }
