import logging
import os
import subprocess
import tempfile

import cv2
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from aidetector.config import Crop, Detection

logger = logging.getLogger(__name__)


def generate_mp4(
    detections: list[Detection], width: int | None = None, crf: int = 0, crop: bool = True, plot: bool = True
) -> bytes | None:
    try:
        if not detections:
            return None

        frames: list[np.ndarray] = []
        if crop:
            crops = [d.images.crop for d in detections if d.images.crop is not None]
            if not crops:
                minX1 = min(crop.x1 for crop in crops)
                minY1 = min(crop.y1 for crop in crops)
                maxX2 = max(crop.x2 for crop in crops)
                maxY2 = max(crop.y2 for crop in crops)
                crop_region = Crop(minX1, minY1, maxX2, maxY2)
                frames = [f for d in detections if (f := get_crop(d, crop=crop_region)) is not None]
        
        if not frames:
            frames = [d.images.plot if plot and d.images.plot is not None else d.images.jpg for d in detections]

        # 1. Calculate FPS
        # (Your existing logic: implies these are time-lapse frames)
        median_duration = np.median(
            [(d.date - detections[i - 1].date).total_seconds() for i, d in enumerate(detections) if i > 0] or 1
        )
        fps = 1 / median_duration if median_duration > 0 else 1

        # 2. Get dimensions from first frame
        # We need the source dimensions to tell FFmpeg what size the raw input stream is
        h, w = frames[0].shape[:2]

        # 3. Setup FFmpeg command
        # We write to a unique temp file because MP4 atoms are tricky to stream directly to stdout
        # without using fragmented MP4s (which have lower player compatibility).
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_out:
            output_path = temp_out.name

        try:
            ffmpeg_exe = get_ffmpeg_exe()

            # Build the scaling filter string
            # Compute target width: use requested width or frame width, capped at frame width, and ensure even
            target_width = min(width, w) if width else w
            target_width = target_width // 2 * 2  # Ensure even (required for H.264)
            vf_scale = f"scale={target_width}:-2"

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

            for frame in frames:
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
                return None

            # 7. Read bytes
            with open(output_path, "rb") as f:
                video_bytes = f.read()

            return video_bytes

        finally:
            if os.path.exists(output_path):
                os.remove(output_path)

    except Exception:
        logger.exception("Failed to generate MP4")
        return None


def get_image(image: np.ndarray) -> bytes:
    success, jpg = cv2.imencode(".jpg", image)

    if not success:
        raise ValueError("Failed to encode image")

    return jpg.tobytes()


def get_crop(
    detection: Detection, crop: Crop | None = None, aspect_ratio: float | None = 16 / 9, padding: float = 0.1
) -> np.ndarray | None:
    crop = crop or detection.images.crop
    if crop is None:
        return None
    img = detection.images.plot if detection.images.plot is not None else detection.images.jpg
    h, w = img.shape[:2]
    box_w, box_h = (
        crop.x2 - crop.x1,
        crop.y2 - crop.y1,
    )
    pad_x, pad_y = int(box_w * padding), int(box_h * padding)
    x1, y1 = max(0, crop.x1 - pad_x), max(0, crop.y1 - pad_y)
    x2, y2 = min(w, crop.x2 + pad_x), min(h, crop.y2 + pad_y)
    if aspect_ratio:
        middle = (x1 + x2) // 2
        x1 = max(0, middle - int((box_h + pad_y) * aspect_ratio / 2))
        x2 = min(w, x1 + int((box_h + pad_y) * aspect_ratio))
    return img[y1:y2, x1:x2]
