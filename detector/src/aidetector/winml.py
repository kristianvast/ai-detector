"""WinML execution provider setup for ONNX on Windows."""

import sys


def setup_winml():
    """Patch onnxruntime to use WinML execution provider on Windows."""
    if sys.platform != "win32":
        return

    try:
        import onnxruntime as ort

        _InferenceSession = ort.InferenceSession

        def InferenceSession(*args, providers=None, **kwargs):
            # Use WinML if no providers explicitly specified
            if providers is None:
                providers = ["WinMLExecutionProvider", "CPUExecutionProvider"]
            return _InferenceSession(*args, providers=providers, **kwargs)

        ort.InferenceSession = InferenceSession

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("onnxruntime not installed or improper installation")
