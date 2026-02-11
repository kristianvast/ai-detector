import logging

from aidetector.utils.config import config
from aidetector.detection.manager import Manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info(f"Starting application with config: {config}")
    manager = Manager.from_config(config)
    threads = manager.start()
    try:
        for thread in threads:
            thread.join()
    except KeyboardInterrupt:
        logger.info("Shutdown requested")
    finally:
        manager.stop()


if __name__ == "__main__":
    main()
