import json
from typing import Self

from aidetector.config import ChatConfig, Config, Detection, DetectorConfig
from aidetector.exporters.exporter import Exporter
from aidetector.exporters.webhook import WebhookExporter
from aidetector.video import generate_mp4


class TelegramExporter(WebhookExporter, Exporter[ChatConfig]):
    chat: str
    alert_every: int
    alert_count: int
    include_video: bool
    include_plot: bool
    include_crop: bool
    video_width: int | None
    video_crf: int

    def __init__(
        self,
        token: str,
        chat: str,
        confidence: float,
        alert_every: int,
        include_video: bool,
        include_plot: bool,
        include_crop: bool,
        video_width: int | None,
        video_crf: int = 28,
        export_rejected: bool = False,
    ):
        url = f"https://api.telegram.org/bot{token}/sendMediaGroup"
        super().__init__(
            url,
            token,
            confidence,
            "binary",
            None,
            include_video,
            include_plot,
            include_crop,
            video_width,
            video_crf,
            export_rejected,
        )
        self.chat = chat
        self.alert_every = alert_every
        self.include_video = include_video
        self.include_plot = include_plot
        self.include_crop = include_crop
        self.video_width = video_width
        self.video_crf = video_crf
        self.alert_count = 0

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: ChatConfig) -> Self:  # ty:ignore[invalid-method-override]
        return cls(
            exporter.token,
            exporter.chat,
            confidence=exporter.confidence or (detector.yolo.confidence if detector.yolo else 0),
            alert_every=exporter.alert_every,
            include_video=exporter.include_video,
            include_plot=exporter.include_plot,
            include_crop=exporter.include_crop,
            video_width=exporter.video_width,
            video_crf=exporter.video_crf,
            export_rejected=exporter.export_rejected,
        )

    def get_payload(self, best_detection: Detection, detections: list[Detection], validated: bool | None):
        self.alert_count += 1
        media = [
            {
                "type": "photo",
                "media": "attach://photo",
                "caption": f"{int(best_detection.confidence * 100)}%{' ✅' if validated else ' ❌' if validated is False else ''}\n{round((detections[-1].date - detections[0].date).total_seconds())} second(s)\n👍 / 👎",
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
            video = generate_mp4(detections, width=self.video_width, crf=self.video_crf)
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
