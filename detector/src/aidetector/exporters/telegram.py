from typing import Self

from aidetector.config import ChatConfig, Config, Detection, DetectorConfig
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.webhook import WebhookExporter


class TelegramExporter(WebhookExporter, Exporter[ChatConfig]):
    chat: str
    alert_every: int
    alert_count: int = 0

    def __init__(self, token: str, chat: str, confidence: float, alert_every: int):
        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        super().__init__(url, token, confidence, "binary", None)
        self.chat = chat
        self.alert_every = alert_every

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: ChatConfig) -> Self:  # ty:ignore[invalid-method-override]
        return cls(
            exporter.token,
            exporter.chat,
            confidence=exporter.confidence or (detector.yolo.confidence if detector.yolo else 0),
            alert_every=exporter.alert_every,
        )

    def get_payload(self, best_detection: Detection, detections: list[Detection], validated: bool):
        self.alert_count += 1
        return {
            "chat_id": self.chat,
            "caption": f"{int(best_detection.confidence * 100)}%{' ✅' if validated else ''}\n{round((detections[-1].date - detections[0].date).total_seconds())} second(s)\n👍 / 👎",
            "disable_notification": self.alert_count % self.alert_every != 0,
        }
