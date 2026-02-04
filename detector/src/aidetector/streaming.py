import logging
from threading import Condition, Thread

from numpy import ndarray
from ultralytics.data.loaders import LoadStreams

logger = logging.getLogger(__name__)


class StreamBatcher:
    running: bool
    threads: list[Thread]
    latest: dict[str, ndarray]
    counts: dict[str, int]
    loaders: list[LoadStreams]
    active_sources: list[str]
    condition: Condition

    def __init__(self, sources: list[str]):
        self.running = True
        self.sources = sources
        self.loaders: list[LoadStreams] = []
        self.latest: dict[str, ndarray] = {}
        self.counts: dict[str, int] = {}
        self.threads: list[Thread] = []
        self.active_sources: list[str] = []
        self.condition = Condition()

        for source in self.sources:
            try:
                loader: LoadStreams = LoadStreams(source)
            except Exception:
                logger.exception("Failed to open stream source %s", source)
                continue
            self.loaders.append(loader)
            self.active_sources.append(source)

        if not self.loaders:
            raise ValueError("No active stream sources")

        def run_loader(source: str, loader: LoadStreams):
            for _, imgs, _ in loader:
                if imgs is None:
                    continue
                with self.condition:
                    self.latest[source] = imgs[0]
                    self.counts[source] = self.counts.get(source, 0) + 1
                    self.condition.notify()

        for source, loader in zip(self.sources, self.loaders):
            thread = Thread(target=run_loader, args=(source, loader), daemon=True)
            thread.start()
            self.threads.append(thread)

    def clear(self) -> None:
        self.latest.clear()
        self.counts.clear()

    def stop(self) -> None:
        self.running = False
        with self.condition:
            self.condition.notify_all()
        for loader in self.loaders:
            try:
                loader.close()
            except Exception:
                logger.debug("Failed to close stream loader", exc_info=True)
        self.loaders = []
        for thread in self.threads:
            thread.join()
        self.threads = []

    def is_ready(self) -> bool:
        return len(self.latest) == len(self.active_sources) or any(count >= 2 for count in self.counts.values())

    def __iter__(self):
        while self.running:
            with self.condition:
                while not self.is_ready():
                    self.condition.wait()
                snapshot = dict(self.latest)
                self.clear()
            if snapshot:
                yield snapshot
