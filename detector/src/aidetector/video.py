import logging
import tempfile
from typing import IO

import cv2
import numpy as np

from aidetector.config import Detection

logger = logging.getLogger(__name__)


def generate_mp4(detections: list[Detection]) -> bytes | None:
    if not detections:
        return None

    try:
        # Decode the first image to get dimensions
        nparr = np.frombuffer(detections[0].plot, np.uint8)
        first_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        height, width, layers = first_frame.shape

        # Create a temp file for the video
        temp_video: IO = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        temp_video_path = temp_video.name
        temp_video.close()

        fps = 30
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

        start_time = detections[0].date

        for i, detection in enumerate(detections):
            # Calculate duration until next frame
            current_time = detection.date
            if i < len(detections) - 1:
                next_time = detections[i + 1].date
                duration = (next_time - current_time).total_seconds()
            else:
                # Last frame, give it a default short duration (e.g. 1 sec or same as prev)
                duration = 1.0

            nparr = np.frombuffer(detection.plot, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Write frames repeatedly to match real-time duration
            num_frames = max(1, int(duration * fps))
            for _ in range(num_frames):
                video.write(frame)

        video.release()

        with open(temp_video_path, "rb") as f:
            video_bytes = f.read()

        return video_bytes

    except Exception:
        logger.exception("Failed to generate MP4")
        return None
