import os
from pathlib import Path
from typing import Self

from aidetector.config import (
    Config,
    Detection,
    DetectorConfig,
    DiskConfig,
    get_date_path,
    get_timestamped_filename,
)
from aidetector.exporters.exporter import Exporter
from aidetector.video import generate_mp4


class DiskExporter(Exporter[DiskConfig]):
    directory: Path

    def __init__(self, directory: Path, confidence: float, export_rejected: bool = True):
        super().__init__(confidence, export_rejected, directory)
        self.directory = Path(os.path.join("detections", directory))
        os.makedirs(self.directory, exist_ok=True)

    @classmethod
    def from_config(cls, config: Config, detector: DetectorConfig, exporter: DiskConfig) -> Self:
        return cls(
            exporter.directory,
            exporter.confidence or (detector.yolo.confidence if detector.yolo else 0),
            exporter.export_rejected,
        )

    def filtered_export(self, best_detection: Detection, detections: list[Detection], validated: bool | None):
        self.logger.info(f"Saving {len(detections)} photos to disk")
        timestamp = get_date_path(best_detection, "seconds")
        subfolder = "approved" if validated else "rejected" if validated is False else ""
        timestamped_directory = os.path.join(self.directory, subfolder, timestamp)
        os.makedirs(timestamped_directory, exist_ok=True)
        for result in detections:
            image_name = get_timestamped_filename(result)
            image_path = os.path.join(timestamped_directory, image_name)
            with open(image_path, "wb") as f:
                f.write(result.images.jpg)
        if best_detection:
            image_path = os.path.join(timestamped_directory, "best.jpg")
            with open(image_path, "wb") as f:
                f.write(best_detection.images.plot or best_detection.images.jpg)
        video = generate_mp4(detections)
        if video:
            video_path = os.path.join(timestamped_directory, "video.mp4")
            with open(video_path, "wb") as f:
                f.write(video)
