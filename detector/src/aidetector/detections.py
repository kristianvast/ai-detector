from datetime import datetime
from typing import List, Self

from aidetector.config import Detection, YoloConfig
from aidetector.video import generate_mp4


class Detections:
    time_max: int
    _detections: List[Detection] = []

    def __init__(self, time_max: int):
        self.time_max = time_max

    @classmethod
    def from_config(cls, config: YoloConfig | None = None) -> Self:
        return cls(config.time_max if config else 0)

    def add(self, detection: Detection):
        self._detections.append(detection)

    def get(self):
        return self._detections

    def best(self):
        return max(self.get(), key=lambda x: x.confidence)

    def first(self):
        return self.get()[0]

    def last(self):
        return self.get()[-1]

    def length(self):
        return len(self.get())

    def clear(self):
        self._detections = []

    def video(self):
        return generate_mp4(self._detections)

    def filter(self):
        self._detections = [d for d in self._detections if (datetime.now() - d.date).total_seconds() <= self.time_max]
