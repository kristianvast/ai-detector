import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from aidetector.utils.config import (
    Confidence,
    Config,
    Detection,
    DetectorConfig,
    ExporterConfig,
    confidence_matches,
)
from typing_extensions import Self

T = TypeVar("T", bound=ExporterConfig)


class Exporter(ABC, Generic[T]):
    logger = logging.getLogger(__name__)
    confidence: float | Confidence
    export_rejected: bool

    def __init__(
        self, confidence: float | Confidence = 0, export_rejected: bool = False, *args
    ):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initializing with args={args}")
        self.confidence = confidence
        self.export_rejected = export_rejected

    @classmethod
    @abstractmethod
    def from_config(
        cls: Self, config: Config, detector: DetectorConfig, exporter: T
    ) -> Self:
        pass

    def export(
        self,
        best_detection: Detection,
        detections: list[Detection],
        validated: bool | None,
    ):
        if not confidence_matches(best_detection.confidence, self.confidence):
            self.logger.info("Confidence does not match")
            return
        if validated is False and not self.export_rejected:
            self.logger.info("Best detection is rejected and export_rejected is False")
            return
        self.filtered_export(best_detection, detections, validated)

    @abstractmethod
    def filtered_export(
        self,
        best_detection: Detection,
        detections: list[Detection],
        validated: bool | None,
    ):
        pass
