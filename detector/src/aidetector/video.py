import logging
import tempfile
from typing import IO

import cv2
import numpy as np

from aidetector.config import Detection

logger = logging.getLogger(__name__)


def image_to_bytes(image: np.ndarray) -> bytes:
    success, jpg = cv2.imencode(".jpg", image)
    if not success:
        raise ValueError("Failed to encode image")
    return jpg.tobytes()


def generate_mp4(detections: list[Detection], width: int | None = None) -> bytes | None:
    if not detections:
        return None

    try:
        median_duration = np.median(
            [(d.date - detections[i - 1].date).total_seconds() for i, d in enumerate(detections) if i > 0] or 1
        )

        # Decode the first image to get dimensions
        nparr = np.frombuffer(detections[0].images.plot or detections[0].images.jpg, np.uint8)
        first_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        height, src_width, layers = first_frame.shape

        if width and src_width > width:
            scale = width / src_width
            height = int(height * scale)
        else:
            width = src_width

        # Create a temp file for the video
        temp_video: IO = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_video_path = temp_video.name
        temp_video.close()

        fps = 1 / median_duration

        fourcc = cv2.VideoWriter_fourcc(*"avc1")
        video = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        for detection in detections:
            nparr = np.frombuffer(detection.images.plot or detection.images.jpg, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame.shape[1] != width:
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
            video.write(frame)

        video.release()

        with open(temp_video_path, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    except Exception:
        logger.exception("Failed to generate MP4")
        return None
