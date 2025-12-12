from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    get_package_paths,
    is_module_satisfies,
    logger,
)

if is_module_satisfies("PyInstaller >= 6.0"):
    from PyInstaller import compat
    from PyInstaller.utils.hooks import PY_DYLIB_PATTERNS

    module_collection_mode = "pyz+py"
    warn_on_missing_hiddenimports = False

    datas = collect_data_files(
        "llama_cpp",
        excludes=[
            "**/*.h",
            "**/*.hpp",
            "**/*.cuh",
            "**/*.lib",
            "**/*.cpp",
            "**/*.pyi",
            "**/*.cmake",
        ],
    )
    hiddenimports = collect_submodules("llama_cpp")
    binaries = collect_dynamic_libs(
        "llama_cpp",
        search_patterns=PY_DYLIB_PATTERNS + ["*.so.*"],
    )
    if compat.is_linux:

        def _infer_nvidia_hiddenimports():
            import packaging.requirements
            from _pyinstaller_hooks_contrib.compat import importlib_metadata
            from _pyinstaller_hooks_contrib.utils import nvidia_cuda as cudautils

            dist = importlib_metadata.distribution("llama_cpp")
            requirements = [packaging.requirements.Requirement(req) for req in dist.requires or []]
            requirements = [req.name for req in requirements if req.marker is None or req.marker.evaluate()]

            return cudautils.infer_hiddenimports_from_requirements(requirements)

        try:
            nvidia_hiddenimports = _infer_nvidia_hiddenimports()
        except Exception:
            # Log the exception, but make it non-fatal
            logger.warning("hook-llama_cpp: failed to infer NVIDIA CUDA hidden imports!", exc_info=True)
            nvidia_hiddenimports = []
        logger.info("hook-llama_cpp: inferred hidden imports for CUDA libraries: %r", nvidia_hiddenimports)
        hiddenimports += nvidia_hiddenimports
        bindepend_symlink_suppression = ["**/llama_cpp/lib/*.so*"]
else:
    datas = [(get_package_paths("llama_cpp")[1], "llama_cpp")]
