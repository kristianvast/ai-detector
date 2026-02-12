import logging
from threading import Thread
from time import sleep

import requests
from typing_extensions import Self

from aidetector.utils.config import HealthcheckConfig

logger = logging.getLogger(__name__)


class Healthcheck:
    url: str
    method: str
    interval: int
    headers: dict[str, str] | None
    body: str | None
    timeout: int
    running: bool

    def __init__(
        self,
        url: str,
        method: str,
        interval: int,
        headers: dict[str, str] | None,
        body: str | None,
        timeout: int,
    ):
        self.url = url
        self.method = method
        self.interval = interval
        self.headers = headers
        self.body = body
        self.timeout = timeout
        self.running = True

    @classmethod
    def from_config(cls, config: HealthcheckConfig) -> Self:
        return cls(
            config.url,
            config.method,
            config.interval,
            config.headers,
            config.body,
            config.timeout,
        )

    def start(self) -> Thread:
        thread = Thread(target=self._check, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        self.running = False

    def _check(self) -> None:
        logger.info(
            "Starting healthcheck pinger (method=%s, interval=%ss, url=%s)",
            self.method,
            self.interval,
            self.url,
        )
        while self.running:
            try:
                response = requests.request(
                    self.method,
                    self.url,
                    headers=self.headers,
                    data=self.body,
                    timeout=self.timeout,
                )
                if response.status_code >= 400:
                    logger.warning("Healthcheck ping returned %s", response.status_code)
            except requests.RequestException:
                logger.exception("Healthcheck ping failed")
            sleep(self.interval)
