import logging

import onnxruntime as ort

IS_AVAILABLE = False
LOGGER = logging.getLogger(__name__)


def _patch_ultralytics_requirements() -> None:
    try:
        from ultralytics.utils import checks
    except ImportError:
        return

    _original_check_requirements = checks.check_requirements

    def _check_requirements(requirements=(), **kwargs):
        def should_skip(requirement: str) -> bool:
            return "onnxruntime-gpu" in requirement or "onnxruntime" in requirement or "onnx" in requirement

        if isinstance(requirements, (list, tuple)):
            requirements = [r for r in requirements if not should_skip(r)]
        elif isinstance(requirements, str) and should_skip(requirements):
            return True

        return _original_check_requirements(requirements=requirements, **kwargs)

    checks.check_requirements = _check_requirements


def setup_ort() -> bool:
    global IS_AVAILABLE
    # if sys.platform != "win32":
    #     return False

    if IS_AVAILABLE:
        return True

    _InferenceSession = ort.InferenceSession

    def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
        providers = ort.get_available_providers()

        LOGGER.info("ORT providers available: %s", ort.get_available_providers())
        LOGGER.info("ORT providers selected: %s", providers)

        return _InferenceSession(path_or_bytes, sess_options, providers, **kwargs)

    ort.InferenceSession = InferenceSession
    _patch_ultralytics_requirements()
    IS_AVAILABLE = True
    return True
