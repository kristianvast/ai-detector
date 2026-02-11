from aidetector.utils.onnx import setup_ort

setup_ort()

import logging  # noqa: E402

from aidetector.detection.manager import Manager  # noqa: E402
from aidetector.utils.config import config  # noqa: E402

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
