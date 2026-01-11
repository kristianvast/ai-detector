from typing import Self

from aidetector.config import Config
from aidetector.detector import Detector


class Manager:
    batch = False
    detectors: list[Detector]

    def __init__(self, detectors: list[Detector]):
        self.detectors = detectors

    @classmethod
    def from_config(cls, config: Config) -> Self:
        return cls([d for ds in [Detector.from_config(config, detector) for detector in config.detectors] for d in ds])

    def start(self):
        return [detector.start() for detector in self.detectors]
