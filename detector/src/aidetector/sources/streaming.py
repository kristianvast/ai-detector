import logging
from threading import Condition, Thread
from time import sleep

from ultralytics.data.loaders import LoadStreams

from .collector import FrameCollector

logger = logging.getLogger(__name__)


class StreamBatcher:
    running: bool
    threads: list[Thread]
    collector: FrameCollector
    loaders: list[LoadStreams]
    active_sources: list[str]
    missing_sources: set[str]
    condition: Condition

    def __init__(self, sources: list[str], retention: int = 1):
        logger.info("Initializing StreamBatcher with %d sources", len(sources))
        self.running = True
        self.sources = sources
        self.loaders: list[LoadStreams] = []
        self.collector = FrameCollector(retention)
        self.threads: list[Thread] = []
        self.active_sources: list[str] = []
        self.missing_sources: set[str] = set()
        self.condition = Condition()

        for source in self.sources:
            logger.debug("Opening stream source %s", source)
            try:
                loader: LoadStreams = LoadStreams(source)
            except Exception:
                logger.exception("Failed to open stream source %s", source)
                continue
            self.loaders.append(loader)
            self.active_sources.append(source)
            logger.info("Opened stream source %s", source)

        if not self.loaders:
            raise ValueError("No active stream sources")

        inactive_count = len(self.sources) - len(self.active_sources)
        if inactive_count:
            logger.warning("Skipped %d inactive stream sources", inactive_count)

        def run_loader(index: int, source: str, loader: LoadStreams):
            logger.debug("Stream loader started for %s", source)
            current_loader = loader
            while self.running:
                try:
                    for _, imgs, _ in current_loader:
                        if not self.running:
                            break
                        if imgs is None:
                            continue
                        with self.condition:
                            self.collector.add(source, imgs[0])
                            logger.debug(
                                "Received frame %d from %s",
                                self.collector.frames[source],
                                source,
                            )
                            self.condition.notify()
                except Exception:
                    if self.running:
                        logger.exception("Stream loader crashed for %s", source)
                finally:
                    try:
                        current_loader.close()
                    except Exception:
                        logger.debug("Failed to close stream loader", exc_info=True)

                if self.running:
                    logger.warning("Stream loader ended for %s, reconnecting", source)
                    try:
                        current_loader = LoadStreams(source)
                        self.loaders[index] = current_loader
                        logger.info("Reconnected stream source %s", source)
                    except Exception:
                        logger.exception("Failed to reconnect stream source %s", source)
                        sleep(1)
            logger.info("Stream loader finished for %s", source)

        for index, (source, loader) in enumerate(zip(self.active_sources, self.loaders)):
            logger.debug("Starting stream loader thread for %s", source)
            thread = Thread(target=run_loader, args=(index, source, loader), daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop(self) -> None:
        logger.info("Stopping StreamBatcher with %d active sources", len(self.active_sources))
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
        logger.info("StreamBatcher stopped")

    def is_ready(self) -> bool:
        return len(self.collector.frames) == len(self.active_sources) or any(
            count >= 2 for count in self.collector.counts().values()
        )

    def log_missing(self, present_sources: set[str]):
        new_missing = set(self.active_sources) - present_sources
        intersect = new_missing & self.missing_sources
        if intersect:
            logger.warning("Missing frames from sources: %s", sorted(intersect))
        self.missing_sources = new_missing

    def __iter__(self):
        logger.debug("StreamBatcher iterator started")
        while self.running:
            with self.condition:
                while not self.is_ready():
                    self.condition.wait()
                snapshot = dict(self.collector.frames)
                self.collector.clear()
            if snapshot:
                logger.debug(
                    "Yielding batch with %d frames from %d sources",
                    len(snapshot),
                    len(self.active_sources),
                )
                self.log_missing(set(snapshot.keys()))
                yield snapshot
        logger.debug("StreamBatcher iterator stopped")


ultralytics_logger = logging.getLogger("ultralytics")


class _SuppressLoadStreamsFilter(logging.Filter):
    filter_messages = [
        "Waiting for stream ",
        " (no detections), ",
        " postprocess per image at shape (",
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if not message:
            return False
        return not any(part in message for part in self.filter_messages)


ultralytics_logger.addFilter(_SuppressLoadStreamsFilter())
