import logging
from collections.abc import Iterator
from threading import Thread

from numpy import ndarray
from ultralytics.data.loaders import LoadStreams

logger = logging.getLogger(__name__)


class StreamBatcher:
    latest: dict[str, ndarray]
    counts: dict[str, int]
    active_sources: list[str]

    def __init__(self, sources: list[str]):
        self.sources = sources
        self._loaders: list[LoadStreams] = []

    def stop(self) -> None:
        for loader in self._loaders:
            try:
                loader.close()
            except Exception:
                logger.debug("Failed to close stream loader", exc_info=True)
        self._loaders = []

    def __iter__(self):
        loaders: list[tuple[str, LoadStreams]] = []
        threads: list[Thread] = []
        self.latest.clear()
        self.counts.clear()
        self.active_sources = []
        ready: list[Iterator[tuple[str, ndarray]]] = []

        def run_loader(source: str, loader: LoadStreams):
            for _, imgs, _ in loader:
                if not imgs:
                    continue
                batch = self._ingest(source, imgs[0])
                if batch:
                    ready.append(batch)

        for source in self.sources:
            try:
                loader: LoadStreams = LoadStreams(source)
            except Exception:
                logger.exception("Failed to open stream source %s", source)
                continue
            loaders.append((source, loader))
            self._loaders.append(loader)

        active_sources = [source for source, _ in loaders]
        if not active_sources:
            return

        self.active_sources = active_sources
        self.counts = {source: 0 for source in active_sources}

        for source, loader in loaders:
            thread = Thread(target=run_loader, args=(source, loader), daemon=True)
            thread.start()
            threads.append(thread)

        try:
            while any(thread.is_alive() for thread in threads):
                if ready:
                    yield ready.pop(0)
        finally:
            self.stop()
            for thread in threads:
                thread.join(timeout=0.1)

    def _ingest(self, source: str, frame: ndarray) -> Iterator[tuple[str, ndarray]] | None:
        self.latest[source] = frame
        self.counts[source] = min(self.counts.get(source, 0) + 1, 2)
        ready_all = len(self.latest) == len(self.active_sources)
        ready_second = any(count >= 2 for count in self.counts.values())
        if not (ready_all or ready_second):
            return None
        batch_sources = [s for s in self.active_sources if s in self.latest]
        frames = [self.latest[s] for s in batch_sources]
        self.latest.clear()
        for s in self.counts:
            self.counts[s] = 0
        return zip(batch_sources, frames)
