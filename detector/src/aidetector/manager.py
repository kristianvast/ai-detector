from typing import Self

from aidetector.config import Config
from aidetector.detector import Detector


class Manager:
    detectors: list[Detector]

    def __init__(self, detectors: list[Detector]):
        self.detectors = detectors

    @classmethod
    def from_config(cls, config: Config) -> Self:
        return cls([Detector.from_config(config, detector) for detector in config.detectors])

    def start(self):
        return [thread for detector in self.detectors for thread in detector.start()]
