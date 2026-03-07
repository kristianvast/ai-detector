import itertools
import json
import logging
import os
import sys
import tempfile
from dataclasses import field
from pathlib import Path

import torch  # noqa: F401
from aidetector.utils.config import Config
from aidetector.utils.winml import WinML
from pydantic.dataclasses import dataclass

LOGGER = logging.getLogger(__name__)


@dataclass
class OrtState:
    providers: list[str] = field(default_factory=list)
    is_available: bool = False


_STATE = OrtState()


def _should_auto_install_windows_ml_ep() -> bool:
    no_auto_install = ["GITHUB_ACTIONS", "CI"]
    return not any(_read_env_bool(name) is True for name in no_auto_install) and sys.platform == "win32"


def should_rect() -> bool:
    return _STATE.providers[0] != "NvTensorRTRTXExecutionProvider" if len(_STATE.providers) > 0 else True


def should_half() -> bool:
    return _STATE.providers[0] != "OpenVINOExecutionProvider" if len(_STATE.providers) > 0 else True


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


def setup_ort(config: Config) -> bool:
    try:
        import onnxruntime as ort

        if _STATE.is_available:
            return True

        LOGGER.info("Setup ORT")

        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()

        registered_winml_providers: list[str] = []
        if _should_auto_install_windows_ml_ep():
            LOGGER.info("Registering WinML execution provider...")
            try:
                registered_winml_providers = WinML().register_execution_providers_to_ort()
                LOGGER.info("Registered WinML providers: %s", registered_winml_providers)
            except Exception as e:
                LOGGER.warning("Failed to register WinML execution provider: %s", e)
        else:
            LOGGER.info("Not registering WinML execution provider.")

        _original_InferenceSession = ort.InferenceSession

        def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
            selected_devices = [
                ep_device for ep_device in ort.get_ep_devices() if ep_device.ep_name in registered_winml_providers
            ]
            if selected_devices:
                LOGGER.info("Selected devices: %s", selected_devices)
                if sess_options is None:
                    sess_options = ort.SessionOptions()

                devices = get_devices(config, selected_devices)

                _STATE.providers = [device.ep_name for device, _ in devices]

                for device, options in devices:
                    sess_options.add_provider_for_devices([device], options)

                LOGGER.info(
                    "Configured WinML EP devices for session: %s",
                    _STATE.providers,
                )

                return _original_InferenceSession(path_or_bytes, sess_options=sess_options, **kwargs)

            providers = ort.get_available_providers()
            _STATE.providers = providers
            LOGGER.info("ORT providers configured for session: %s", providers)
            return _original_InferenceSession(
                path_or_bytes,
                sess_options,
                providers,
                **kwargs,
            )

        ort.InferenceSession = InferenceSession  # ty: ignore[invalid-assignment]
        _patch_ultralytics_requirements()
        _STATE.is_available = True

    except Exception:
        return False
    return True


def get_device_options(config: Config, device) -> dict:
    if device.ep_name == "OpenVINOExecutionProvider":
        return _openvino_options(device)
    elif device.ep_name == "NvTensorRTRTXExecutionProvider":
        return _nvtensorrtx_options(config)
    return {}


def sort_devices_by_provider(devices: list) -> list:
    devices_by_provider: dict[str, list] = {
        provider_name: list(devices)
        for provider_name, devices in itertools.groupby(
            sorted(devices, key=lambda ep_device: ep_device.ep_name), key=lambda ep_device: ep_device.ep_name
        )
    }
    if "OpenVINOExecutionProvider" in devices_by_provider:
        for device in devices_by_provider.get("OpenVINOExecutionProvider", []):
            if str(device.device.type).endswith("GPU"):
                devices_by_provider["OpenVINOExecutionProvider"] = [device]
                break
        devices_by_provider["OpenVINOExecutionProvider"] = devices_by_provider["OpenVINOExecutionProvider"][:1]

    devices_minus_openvino = [d for d in devices_by_provider.items() if d[0] != "OpenVINOExecutionProvider"]
    sorted_devices = []
    for provider_name, devices in devices_minus_openvino:
        sorted_devices.extend(devices)

    if "OpenVINOExecutionProvider" in devices_by_provider:
        sorted_devices.extend(devices_by_provider["OpenVINOExecutionProvider"])
    return sorted_devices


def get_devices(config: Config, devices: list) -> list[tuple]:
    sorted_devices = sort_devices_by_provider(devices)
    device_options = [(device, get_device_options(config, device)) for device in sorted_devices]
    return device_options


def _nvtensorrtx_options(config: Config):
    input_name = "images"
    colors = 3
    yolo_detectors = [detector for detector in config.detectors if detector.yolo]
    if not yolo_detectors:
        return {}

    size_min = min(detector.yolo.imgsz for detector in yolo_detectors)
    size_max = max(detector.yolo.imgsz for detector in yolo_detectors)
    streams_max = max(
        [1]
        + [len(detector.detection.source) for detector in yolo_detectors if isinstance(detector.detection.source, list)]
    )
    streams_max = max(streams_max, 1)
    return {
        "nv_profile_min_shapes": f"{input_name}:1x{colors}x{size_min}x{size_min}",
        "nv_profile_opt_shapes": f"{input_name}:{streams_max}x{colors}x{size_max}x{size_max}",
        "nv_profile_max_shapes": f"{input_name}:{streams_max}x{colors}x{size_max}x{size_max}",
    }


def _openvino_options(device):
    device_type = "CPU"
    if str(device.device.type).endswith("GPU"):
        device_type = "GPU"
    precision_hint = "F32"

    config_dir = Path(tempfile.gettempdir()) / "ai-detector" / "openvino"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / f"{device_type.lower()}-{precision_hint}.json"
    config_path.write_text(
        json.dumps({device_type: {"INFERENCE_PRECISION_HINT": precision_hint}}),
        encoding="utf-8",
    )
    return {
        "load_config": str(config_path),
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
