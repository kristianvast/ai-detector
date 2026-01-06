import logging
from abc import ABC, abstractmethod
from typing import Generic, Self, TypeVar

from aidetector.config import Config, Detection, DetectorConfig, ExporterConfig

T = TypeVar("T", bound=ExporterConfig)


class Exporter(ABC, Generic[T]):
    logger = logging.getLogger(__name__)
    confidence: float

    def __init__(self, confidence: float, *args):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initializing with args={args}")
        self.confidence = confidence

    @classmethod
    @abstractmethod
    def from_config(
        cls: Self, config: Config, detector: DetectorConfig, exporter: T
    ) -> Self:
        pass

    def export(self, detections: list[Detection], validated: bool):
        sorted_detections = sorted(detections, key=lambda d: d.confidence, reverse=True)
        filtered_detections = [
            d for d in sorted_detections if d.confidence >= self.confidence
        ]
        if not filtered_detections:
            self.logger.info("No detections meet the minimum confidence threshold")
            return
        self.filtered_export(filtered_detections, validated)

    @abstractmethod
    def filtered_export(self, sorted_detections: list[Detection], validated: bool):
        pass
