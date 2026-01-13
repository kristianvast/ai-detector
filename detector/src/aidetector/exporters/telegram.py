import json
from typing import Self

from aidetector.config import ChatConfig, Config, Detection, DetectorConfig
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.video import generate_mp4


class TelegramExporter(WebhookExporter, Exporter[ChatConfig]):
    chat: str
    alert_every: int
    alert_count: int = 0
    video_width: int | None

    def __init__(
        self, token: str, chat: str, confidence: float, alert_every: int, include_video: bool, video_width: int | None
    ):
        url = f"https://api.telegram.org/bot{token}/sendMediaGroup"
        super().__init__(url, token, confidence, "binary", None, include_video, video_width)
        self.chat = chat
        self.alert_every = alert_every
        self.include_video = include_video
        self.video_width = video_width

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: ChatConfig) -> Self:  # ty:ignore[invalid-method-override]
        return cls(
            exporter.token,
            exporter.chat,
            confidence=exporter.confidence or (detector.yolo.confidence if detector.yolo else 0),
            alert_every=exporter.alert_every,
            include_video=exporter.include_video if exporter.include_video is None else True,
            video_width=exporter.video_width,
        )

    def get_payload(self, best_detection: Detection, detections: list[Detection], validated: bool):
        self.alert_count += 1
        media = [
            {
                "type": "photo",
                "media": "attach://photo",
                "caption": f"{int(best_detection.confidence * 100)}%{' ✅' if validated else ''}\n{round((detections[-1].date - detections[0].date).total_seconds())} second(s)\n👍 / 👎",
            }
        ]
        if best_detection.images.crop:
            media.append(
                {
                    "type": "photo",
                    "media": "attach://crop",
                }
            )

        if self.include_video:
            video = generate_mp4(detections, width=self.video_width)
            if video:
                media.append(
                    {
                        "type": "video",
                        "media": "attach://video",
                    }
                )

        return {
            "chat_id": self.chat,
            "disable_notification": self.alert_count % self.alert_every != 0,
            "media": json.dumps(media),
        }
