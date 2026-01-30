"""DirectML execution provider setup for ONNX on Windows."""

import sys


def setup_directml():
    """Patch onnxruntime to use DirectML execution provider on Windows."""
    if sys.platform != "win32":
        return

    try:
        import onnxruntime as ort

        if "DmlExecutionProvider" not in ort.get_available_providers():
            return

        _InferenceSession = ort.InferenceSession

        def InferenceSession(*args, providers=None, **kwargs):
            # Use DirectML if no providers explicitly specified
            if providers is None:
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            return _InferenceSession(*args, providers=providers, **kwargs)

        ort.InferenceSession = InferenceSession

    except ImportError:
        import logging

        logging.getLogger(__name__).warning(
            "onnxruntime not installed or improper installation (conflict between gpu/directml?)"
        )
