import base64
import logging
from typing import Literal, Self

import cv2
import numpy as np
import requests

from aidetector.config import (
    Config,
    Detection,
    DetectorConfig,
    WebhookConfig,
    get_timestamped_filename,
)
from aidetector.exporters.exporter import Exporter
from aidetector.video import generate_mp4


class WebhookExporter(Exporter[WebhookConfig]):
    url: str
    token: str | None
    data_type: Literal["binary", "base64"]
    include_video: bool
    include_plot: bool
    include_crop: bool
    video_width: int | None
    video_crf: int
    logger = logging.getLogger(__name__)

    def __init__(
        self,
        url: str,
        token: str | None,
        confidence: float,
        data_type: Literal["binary", "base64"],
        data_max: int | None,
        include_video: bool,
        include_plot: bool,
        include_crop: bool,
        video_width: int | None,
        video_crf: int = 28,
        export_rejected: bool = False,
    ):
        super().__init__(
            confidence,
            export_rejected,
            url,
            token,
            data_type,
            data_max,
            include_video,
            include_plot,
            include_crop,
            video_width,
            video_crf,
        )
        self.confidence = confidence
        self.url = url
        self.token = token
        self.data_type = data_type
        self.data_max = data_max
        self.include_video = include_video
        self.include_plot = include_plot
        self.include_crop = include_crop
        self.video_width = video_width
        self.video_crf = video_crf
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: WebhookConfig) -> Self:
        return cls(
            exporter.url,
            exporter.token,
            confidence=exporter.confidence or (detector.yolo.confidence if detector.yolo else 0),
            data_type=exporter.data_type,
            data_max=exporter.data_max,
            include_video=exporter.include_video,
            include_plot=exporter.include_plot,
            include_crop=exporter.include_crop,
            video_width=exporter.video_width,
            video_crf=exporter.video_crf,
            export_rejected=exporter.export_rejected,
        )

    def get_file(self, detection: Detection, detections: list[Detection]):
        if self.data_type == "base64":
            return None
        files = {}
        if self.include_plot:
            files["photo"] = (
                get_timestamped_filename(detection),
                detection.images.plot or detection.images.jpg,
                "image/jpeg",
            )
        if self.include_crop and detection.images.crop:
            files["crop"] = (
                f"{get_timestamped_filename(detection).replace('.jpg', '_crop.jpg')}",
                detection.images.crop,
                "image/jpeg",
            )
        if self.include_video:
            video = generate_mp4(detections, width=self.video_width, crf=self.video_crf)
            if video:
                files["video"] = (
                    f"{get_timestamped_filename(detection).replace('.jpg', '.mp4')}",
                    video,
                    "video/mp4",
                )
        return files

    def get_payload(
        self, best_detection: Detection, detections: list[Detection], validated: bool | None
    ) -> dict[str, str | bytes]:
        data: dict = {
            "confidence": best_detection.confidence,
            "timestamp": best_detection.date.isoformat(),
            "duration": (detections[-1].date - detections[0].date).total_seconds(),
            "validated": validated,
        }
        if self.data_type == "base64":
            if self.include_plot:
                data["photo"] = base64.b64encode(best_detection.images.jpg).decode("utf-8")
            if self.include_crop and best_detection.images.crop:
                data["crop"] = base64.b64encode(best_detection.images.crop).decode("utf-8")
            if self.include_video:
                video = generate_mp4(detections, width=self.video_width, crf=self.video_crf)
                if video:
                    data["video"] = base64.b64encode(video).decode("utf-8")
        return data

    def get_headers(self):
        if self.token is None:
            return {}
        return {
            "Authorization": self.token,
        }

    def filtered_export(self, best_detection: Detection, detections: list[Detection], validated: bool | None):
        try:
            self.logger.info(f"Sending photo to webhook with confidence {best_detection.confidence}")
            headers = self.get_headers()

            jpg = best_detection.images.jpg
            new_detection = Detection(best_detection.date, best_detection.images, best_detection.confidence)

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

                    success, encoded_img = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), quality])  # type: ignore
                    if success:
                        jpg = encoded_img.tobytes()

                if len(jpg) > self.data_max:
                    self.logger.warning(
                        f"Could not compress image to under {self.data_max} bytes. Current size: {len(jpg)}"
                    )
                new_detection.images.jpg = jpg
                new_detection.images.crop = None
                new_detection.images.plot = None

            files = self.get_file(new_detection, detections)
            payload = self.get_payload(new_detection, detections, validated)

            if self.data_type == "base64":
                response = requests.post(self.url, headers=headers, json=payload)
            else:
                response = requests.post(self.url, headers=headers, data=payload, files=files)

            if response.status_code != 200:
                self.logger.error(f"Failed to send photo to webhook: {response.text}")
        except Exception as e:
            self.logger.error(f"Error sending photo to webhook: {e}")
