import logging
import os
import sys

import torch  # noqa: F401
from aidetector.utils.winml import WinML

IS_AVAILABLE = False
LOGGER = logging.getLogger(__name__)


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
    override = _read_env_bool("AIDETECTOR_WINDOWSML_AUTO_INSTALL_EP")
    if override is not None:
        return override

    if _read_env_bool("GITHUB_ACTIONS") is True:
        return False
    if _read_env_bool("CI") is True:
        return False

    return True


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


def setup_ort() -> bool:
    global IS_AVAILABLE

    try:
        import onnxruntime as ort

        if IS_AVAILABLE:
            return True

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

        def _configure_winml_ep_devices(session_options):
            if session_options is None:
                session_options = ort.SessionOptions()

            ep_devices = ort.get_ep_devices()
            selected_devices = [
                ep_device for ep_device in ep_devices if ep_device.ep_name in registered_winml_providers
            ]

            devices_by_provider: dict[str, list] = {}
            for ep_device in selected_devices:
                devices_by_provider.setdefault(ep_device.ep_name, []).append(ep_device)

            for provider_name, provider_devices in devices_by_provider.items():
                session_options.add_provider_for_devices(provider_devices, {})

            LOGGER.info(
                "Configured WinML EP devices for session: %s",
                [ep_device.ep_name for ep_device in selected_devices],
            )
            return session_options

        def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
            # if "DmlExecutionProvider" == providers[0]:
            #     if sess_options is None:
            #         sess_options = ort.SessionOptions()
            #     sess_options.enable_mem_pattern = False
            #     sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            if registered_winml_providers:
                if sess_options is None:
                    sess_options = ort.SessionOptions()

                ep_devices = ort.get_ep_devices()
                selected_devices = [
                    ep_device for ep_device in ep_devices if ep_device.ep_name in registered_winml_providers
                ]

                if selected_devices:
                    devices_by_provider: dict[str, list] = {}
                    for ep_device in selected_devices:
                        devices_by_provider.setdefault(ep_device.ep_name, []).append(ep_device)

                    for provider_name, provider_devices in devices_by_provider.items():
                        sess_options.add_provider_for_devices(provider_devices, {})

                    LOGGER.info(
                        "Configured WinML EP devices for session: %s",
                        [ep_device.ep_name for ep_device in selected_devices],
                    )
                    LOGGER.info("ORT default providers available: %s", ort.get_available_providers())
                    return _InferenceSession(path_or_bytes, sess_options=sess_options, **kwargs)

            providers = ort.get_available_providers()
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
