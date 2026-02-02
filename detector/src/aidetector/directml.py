import logging
import sys

IS_AVAILABLE = False
_DML_PROVIDER = "DmlExecutionProvider"
LOGGER = logging.getLogger(__name__)


def _directml_available(ort) -> bool:
    try:
        return _DML_PROVIDER in ort.get_available_providers()
    except Exception:
        return False


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


def setup_directml() -> bool:
    global IS_AVAILABLE
    if sys.platform != "win32":
        return False

    if IS_AVAILABLE:
        return True

    try:
        import onnxruntime as ort
    except ImportError:
        LOGGER.warning("onnxruntime not installed or improper installation")
        return False

    if not _directml_available(ort):
        return False

    _InferenceSession = ort.InferenceSession

    def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
        if not providers:
            providers = [_DML_PROVIDER, "CPUExecutionProvider"]
        elif _DML_PROVIDER not in providers:
            providers = [_DML_PROVIDER] + list(providers)

        if sess_options is None:
            sess_options = ort.SessionOptions()

        sess_options.enable_mem_pattern = False
        sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

        LOGGER.info("ORT providers available: %s", ort.get_available_providers())
        LOGGER.info("ORT providers selected: %s", providers)

        return _InferenceSession(path_or_bytes, sess_options, providers, **kwargs)

    ort.InferenceSession = InferenceSession
    _patch_ultralytics_requirements()
    IS_AVAILABLE = True
    return True
