import sys

IS_AVAILABLE = False


def setup_directml() -> bool:
    global IS_AVAILABLE
    if sys.platform != "win32":
        return False

    try:
        import onnxruntime as ort

        _InferenceSession = ort.InferenceSession

        def InferenceSession(*args, providers=None, **kwargs):
            providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            return _InferenceSession(*args, providers=providers, **kwargs)

        ort.InferenceSession = InferenceSession
        IS_AVAILABLE = True
        return True

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("onnxruntime not installed or improper installation")
        return False
