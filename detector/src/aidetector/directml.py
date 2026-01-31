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

        # Monkeypatch ultralytics check_requirements to avoid auto-update loop
        # Ultralytics checks for 'onnxruntime' package, but we have 'onnxruntime-directml'
        # which provides the same module but different package metadata.
        try:
            from ultralytics.utils import checks

            _original_check_requirements = checks.check_requirements

            def _check_requirements(requirements=(), exclude=(), install=True, cmds=(), verbose=True):
                # Filter out 'onnxruntime' from requirements
                if isinstance(requirements, (list, tuple)):
                    requirements = [r for r in requirements if "onnxruntime" not in r]
                elif isinstance(requirements, str) and "onnxruntime" in requirements:
                    return True  # Skip check for onnxruntime

                return _original_check_requirements(requirements, exclude, install, cmds, verbose)

            checks.check_requirements = _check_requirements
        except ImportError:
            pass

        return True

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("onnxruntime not installed or improper installation")
        return False
