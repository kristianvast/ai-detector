"""WinML execution provider setup for ONNX on Windows."""

import sys

IS_AVAILABLE = False


def setup_winml() -> bool:
    """Patch onnxruntime to use WinML execution provider on Windows."""
    global IS_AVAILABLE
    if sys.platform != "win32":
        return False

    try:
        import onnxruntime as ort

        _InferenceSession = ort.InferenceSession

        def InferenceSession(*args, providers=None, **kwargs):
            # Force WinML execution provider usage even if CPU is requested (e.g. by Ultralytics with device='cpu')
            # This allows us to use the NPU/GPU via DirectML while bypassing Ultralytics' GPU checks
            providers = ["WinMLExecutionProvider", "CPUExecutionProvider"]
            return _InferenceSession(*args, providers=providers, **kwargs)

        ort.InferenceSession = InferenceSession
        IS_AVAILABLE = True
        return True

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("onnxruntime not installed or improper installation")
        return False
