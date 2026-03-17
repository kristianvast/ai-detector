import logging
import time

from aidetector.utils.onnx import setup_ort

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


logger = logging.getLogger(__name__)
_RESTART_DELAY_SECONDS = 5


def start() -> None:
    from aidetector.utils.config import config

    logger.info(f"Starting application with config: {config}")
    setup_ort(config)
    from aidetector.detection.manager import Manager

    manager = Manager.from_config(config)
    threads = manager.start()
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        manager.stop()


def main():
    while True:
        try:
            start()
            return
        except KeyboardInterrupt:
            logger.info("Shutdown requested")
            return
        except Exception:
            logger.exception(
                "Application crashed, restarting in %ss", _RESTART_DELAY_SECONDS
            )
            time.sleep(_RESTART_DELAY_SECONDS)


if __name__ == "__main__":
    main()
