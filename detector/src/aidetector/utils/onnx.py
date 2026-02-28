import json
import logging
import os
import sys
import tempfile
from pathlib import Path

import torch  # noqa: F401
from aidetector.utils.config import Config
from aidetector.utils.winml import WinML

IS_AVAILABLE = False
ACTIVE_ONNX_PROVIDER_NAMES: set[str] = set()
LOGGER = logging.getLogger(__name__)


def _nvtensorrtx_options(config: Config):
    input_name = "images"
    colors = 3
    yolo_detectors = [detector for detector in config.detectors if detector.yolo]
    if not yolo_detectors:
        return {}

    size_min = min(detector.yolo.imgsz for detector in yolo_detectors)
    size_max = max(detector.yolo.imgsz for detector in yolo_detectors)
    streams_max = max(len(detector.detection.source) for detector in yolo_detectors)
    streams_max = max(streams_max, 1)
    return {
        "nv_profile_min_shapes": f"{input_name}:1x{colors}x{size_min}x{size_min}",
        "nv_profile_opt_shapes": f"{input_name}:{streams_max}x{colors}x{size_max}x{size_max}",
        "nv_profile_max_shapes": f"{input_name}:{streams_max}x{colors}x{size_max}x{size_max}",
    }


def _read_env_bool(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _should_auto_install_windows_ml_ep() -> bool:
    no_auto_install = ["GITHUB_ACTIONS", "CI"]
    return not any(_read_env_bool(name) is True for name in no_auto_install)


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

    checks.check_requirements = _check_requirements  # ty: ignore[invalid-assignment]


def is_nvtensorrtx_active() -> bool:
    return "NvTensorRTRTXExecutionProvider" in ACTIVE_ONNX_PROVIDER_NAMES


def _openvino_options(provider_devices: list, precision_hint: str = "f16"):
    # selected_provider_devices = provider_devices[:1]
    device_type = "CPU"
    for ep_device in provider_devices:
        if str(ep_device.device.type).endswith("GPU"):
            # selected_provider_devices = [ep_device]
            device_type = "GPU"
            break

    if device_type != "GPU":
        precision_hint = "f32"

    config_dir = Path(tempfile.gettempdir()) / "ai-detector" / "openvino"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{device_type.lower()}-{precision_hint}.json"
    config_path.write_text(
        json.dumps({device_type: {"INFERENCE_PRECISION_HINT": precision_hint}}),
        encoding="utf-8",
    )
    return {
        "device_type": device_type,
        "load_config": str(config_path),
    }
    # , selected_provider_devices


def setup_ort(config: Config) -> bool:
    global IS_AVAILABLE, ACTIVE_ONNX_PROVIDER_NAMES

    try:
        import onnxruntime as ort

        if IS_AVAILABLE:
            return True

        LOGGER.info("Setup ORT")

        # if hasattr(ort, "preload_dlls"):
        #     ort.preload_dlls()
        registered_winml_providers: list[str] = []
        if _should_auto_install_windows_ml_ep() and sys.platform == "win32":
            LOGGER.info("Registering WinML execution provider...")
            try:
                registered_winml_providers = WinML().register_execution_providers_to_ort()
                LOGGER.info("Registered WinML providers: %s", registered_winml_providers)
            except Exception as e:
                LOGGER.warning("Failed to register WinML execution provider: %s", e)
        else:
            LOGGER.info("Not registering WinML execution provider.")

        _InferenceSession = ort.InferenceSession

        def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
            if registered_winml_providers:
                if sess_options is None:
                    sess_options = ort.SessionOptions()

                ep_devices = ort.get_ep_devices()
                selected_devices = [
                    ep_device for ep_device in ep_devices if ep_device.ep_name in registered_winml_providers
                ]

                LOGGER.info("Selected devices: %s", selected_devices)
                if selected_devices:
                    ACTIVE_ONNX_PROVIDER_NAMES = {ep_device.ep_name for ep_device in selected_devices}
                    provider_options_by_name = {
                        "NvTensorRTRTXExecutionProvider": _nvtensorrtx_options(config),
                        "OpenVINOExecutionProvider": _openvino_options(selected_devices),
                    }

                    devices_by_provider: dict[str, list] = {}
                    for ep_device in selected_devices:
                        devices_by_provider.setdefault(ep_device.ep_name, []).append(ep_device)

                    for provider_name, provider_devices in devices_by_provider.items():
                        provider_options = provider_options_by_name.get(provider_name, {})
                        selected_provider_devices = provider_devices
                        sess_options.add_provider_for_devices(selected_provider_devices, provider_options)

                    LOGGER.info(
                        "Configured WinML EP devices for session: %s",
                        [ep_device.ep_name for ep_device in selected_devices],
                    )

                    return _InferenceSession(path_or_bytes, sess_options=sess_options, **kwargs)

            providers = ort.get_available_providers()
            ACTIVE_ONNX_PROVIDER_NAMES = set(providers)
            LOGGER.info("ORT providers configured for session: %s", providers)
            return _InferenceSession(
                path_or_bytes,
                sess_options,
                providers,
                **kwargs,
            )

        ort.InferenceSession = InferenceSession  # ty: ignore[invalid-assignment]
        _patch_ultralytics_requirements()
        IS_AVAILABLE = True

    except ImportError:
        return False
    return True
