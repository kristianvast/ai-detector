import logging
import os
import subprocess
import tempfile

import cv2
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from aidetector.config import Detection

logger = logging.getLogger(__name__)


def generate_mp4(detections: list[Detection], width: int | None, crf: int) -> bytes | None:
    if not detections:
        return None

    try:
        # 1. Calculate FPS
        # (Your existing logic: implies these are time-lapse frames)
        median_duration = np.median(
            [(d.date - detections[i - 1].date).total_seconds() for i, d in enumerate(detections) if i > 0] or 1
        )
        fps = 1 / median_duration if median_duration > 0 else 1

        # 2. Get dimensions from first frame
        # We need the source dimensions to tell FFmpeg what size the raw input stream is
        nparr = np.frombuffer(detections[0].images.plot or detections[0].images.jpg, np.uint8)
        first_frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        h, w, _ = first_frame.shape

        # 3. Setup FFmpeg command
        # We write to a unique temp file because MP4 atoms are tricky to stream directly to stdout
        # without using fragmented MP4s (which have lower player compatibility).
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:
            output_path = temp_out.name

        ffmpeg_exe = get_ffmpeg_exe()

        # Build the scaling filter string
        # "scale=1280:-2" means: set width to 1280, calc height automatically
        # AND ensure height is divisible by 2 (required for H.264).
        vf_scale = f"scale={width}:-2" if width and width < w else "null"

        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "rawvideo",  # Input format is raw pixels
            "-vcodec",
            "rawvideo",
            "-s",
            f"{w}x{h}",  # Input resolution (Source)
            "-pix_fmt",
            "bgr24",  # OpenCV uses BGR, not RGB
            "-r",
            str(fps),  # Input Framerate
            "-i",
            "-",  # Read from Stdin
            "-c:v",
            "libx264",  # Encoder
            "-crf",
            str(crf),  # Quality
            "-preset",
            "fast",  # Encoding speed
            "-vf",
            vf_scale,  # Apply scaling here (safer than python)
            "-pix_fmt",
            "yuv420p",  # Essential for QuickTime/Web compatibility
            "-an",  # No audio
            output_path,
        ]

        # 4. Open Subprocess
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # 5. Feed frames
        if process.stdin is None:
            logger.error("Failed to open stdin pipe to FFmpeg")
            return None

        for detection in detections:
            nparr = np.frombuffer(detection.images.plot or detection.images.jpg, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Sanity check: ensure frame size matches the stream setup
            if frame.shape[0] != h or frame.shape[1] != w:
                frame = cv2.resize(frame, (w, h))

            try:
                process.stdin.write(frame.tobytes())
            except BrokenPipeError:
                logger.error("FFmpeg process died unexpectedly.")
                break

        # 6. Finish Encoding
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return None

        # 7. Read bytes and cleanup
        with open(output_path, "rb") as f:
            video_bytes = f.read()

        os.remove(output_path)
        return video_bytes

    except Exception:
        logger.exception("Failed to generate MP4")
        return None


def image_to_bytes(image: np.ndarray) -> bytes:
    success, jpg = cv2.imencode(".jpg", image)

    if not success:
        raise ValueError("Failed to encode image")

    return jpg.tobytes()
