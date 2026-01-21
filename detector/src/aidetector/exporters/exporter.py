import logging
from abc import ABC, abstractmethod
from typing import Generic, Self, TypeVar

from aidetector.config import Config, Detection, DetectorConfig, ExporterConfig

T = TypeVar("T", bound=ExporterConfig)


class Exporter(ABC, Generic[T]):
    logger = logging.getLogger(__name__)
    confidence: float
    export_rejected: bool

    def __init__(self, confidence: float, export_rejected: bool = False, *args):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initializing with args={args}")
        self.confidence = confidence
        self.export_rejected = export_rejected

    @classmethod
    @abstractmethod
    def from_config(cls: Self, config: Config, detector: DetectorConfig, exporter: T) -> Self:
        pass

    def export(self, best_detection: Detection, detections: list[Detection], validated: bool | None):
        if best_detection.confidence < self.confidence:
            self.logger.info("Best detection does not meet the minimum confidence threshold")
            return
        if validated is False and not self.export_rejected:
            self.logger.info("Best detection is rejected and export_rejected is False")
            return
        self.filtered_export(best_detection, detections, validated)

    @abstractmethod
    def filtered_export(self, best_detection: Detection, detections: list[Detection], validated: bool | None):
        pass
