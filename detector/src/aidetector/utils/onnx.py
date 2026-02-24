import logging
import os
from importlib import metadata
from pathlib import Path

import torch  # noqa: F401

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


def _remove_winrt_runtime_msvcp_dll() -> None:
    try:
        site_packages_path = Path(str(metadata.distribution("winrt-runtime").locate_file("")))
    except metadata.PackageNotFoundError:
        return
    except Exception as e:
        LOGGER.debug("Unable to locate winrt-runtime package location: %s", e)
        return

    dll_path = site_packages_path / "winrt" / "msvcp140.dll"
    if not dll_path.exists():
        return

    try:
        dll_path.unlink()
        LOGGER.info("Removed conflicting DLL from winrt-runtime: %s", dll_path)
    except Exception as e:
        LOGGER.debug("Failed removing %s: %s", dll_path, e)


def _ensure_windows_ml_execution_providers(ort) -> None:
    if os.name != "nt":
        return

    auto_install = _should_auto_install_windows_ml_ep()
    if not auto_install:
        LOGGER.info(
            "Windows ML EP auto-install is disabled. "
            "Set AIDETECTOR_WINDOWSML_AUTO_INSTALL_EP=1 to enable."
        )

    if not hasattr(ort, "register_execution_provider_library"):
        LOGGER.debug("ONNX Runtime build does not expose register_execution_provider_library().")
        return

    try:
        _remove_winrt_runtime_msvcp_dll()
        import winui3.microsoft.windows.ai.machinelearning as winml
        from winui3.microsoft.windows.applicationmodel.dynamicdependency.bootstrap import (
            InitializeOptions,
            initialize,
        )
    except ImportError:
        LOGGER.debug("Windows ML execution provider APIs are not installed.")
        return
    except Exception as e:
        LOGGER.warning("Failed to initialize Windows ML APIs: %s", e)
        return

    try:
        with initialize(options=InitializeOptions.ON_NO_MATCH_SHOW_UI):
            catalog = winml.ExecutionProviderCatalog.get_default()
            providers = list(catalog.find_all_providers())

            if not providers:
                LOGGER.info("No Windows ML execution providers available for this device.")
                return

            for provider in providers:
                state = provider.ready_state
                if state in (
                    winml.ExecutionProviderReadyState.NOT_PRESENT,
                    winml.ExecutionProviderReadyState.NOT_READY,
                ):
                    if not auto_install:
                        LOGGER.info(
                            "Skipping EP download/install for %s (state=%s).",
                            provider.name,
                            state,
                        )
                        continue

                    operation = provider.ensure_ready_async()
                    provider_name = provider.name

                    # Listen to progress callback
                    def on_progress(_async_info, progress_info):
                        # progress_info is out of 100, convert to 0-1 range
                        normalized_progress = progress_info / 100.0

                        # Display the progress to the user
                        LOGGER.info(
                            "Windows ML EP install progress for %s: %.0f%%",
                            provider_name,
                            normalized_progress * 100,
                        )

                    try:
                        operation.progress = on_progress
                    except Exception as e:
                        LOGGER.debug(
                            "Could not attach progress callback for provider %s: %s",
                            provider_name,
                            e,
                        )

                    result = operation.get()
                    if result.status != winml.ExecutionProviderReadyResultState.SUCCESS:
                        LOGGER.warning(
                            "Failed to make provider ready: %s (status=%s)",
                            provider.name,
                            result.status,
                        )
                        continue

                if provider.ready_state != winml.ExecutionProviderReadyState.READY:
                    LOGGER.info(
                        "Skipping provider %s because it is not ready (state=%s).",
                        provider.name,
                        provider.ready_state,
                    )
                    continue

                if not provider.library_path:
                    LOGGER.info(
                        "Skipping provider %s because it has no library_path.",
                        provider.name,
                    )
                    continue

                try:
                    ort.register_execution_provider_library(provider.name, provider.library_path)
                    LOGGER.info(
                        "Registered Windows ML execution provider: %s (%s)",
                        provider.name,
                        provider.library_path,
                    )
                except Exception as e:
                    LOGGER.warning(
                        "Failed to register execution provider %s: %s",
                        provider.name,
                        e,
                    )
    except Exception as e:
        LOGGER.warning("Automatic Windows ML execution provider initialization failed: %s", e)


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

        if hasattr(ort, "preload_dlls"):
            ort.preload_dlls()
        _ensure_windows_ml_execution_providers(ort)

        _InferenceSession = ort.InferenceSession

        def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
            providers = ort.get_available_providers()

            # if "DmlExecutionProvider" == providers[0]:
            #     if sess_options is None:
            #         sess_options = ort.SessionOptions()
            #     sess_options.enable_mem_pattern = False
            #     sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL

            LOGGER.info("ORT providers available: %s", providers)

            return _InferenceSession(path_or_bytes, sess_options, providers, **kwargs)

        ort.InferenceSession = InferenceSession  # ty: ignore[invalid-assignment]
        _patch_ultralytics_requirements()
        IS_AVAILABLE = True

    except ImportError:
        return False
    return True
