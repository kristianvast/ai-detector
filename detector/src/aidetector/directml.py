import sys

IS_AVAILABLE = False


def setup_directml() -> bool:
    global IS_AVAILABLE
    if sys.platform != "win32":
        return False

    if IS_AVAILABLE:
        return True

    try:
        import onnxruntime as ort

        _InferenceSession = ort.InferenceSession

        def InferenceSession(path_or_bytes, sess_options=None, providers=None, **kwargs):
            # Ensure DirectML provider is prioritized
            if not providers:
                providers = ["DmlExecutionProvider", "CPUExecutionProvider"]
            elif "DmlExecutionProvider" not in providers:
                providers = ["DmlExecutionProvider"] + list(providers)

            import logging

            logger = logging.getLogger(__name__)
            logger.info(f"Available Providers: {ort.get_available_providers()}")
            logger.info(f"Selected Providers: {providers}")

            # DirectML requires specific session options to avoid crashes
            # https://onnxruntime.ai/docs/execution-providers/DirectML-ExecutionProvider.html#configuration-options
            if sess_options is None:
                sess_options = ort.SessionOptions()

            sess_options.enable_mem_pattern = False
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL

            # Debug logging
            import logging

            logger = logging.getLogger(__name__)
            # logger.info(f"Creation InferenceSession with providers: {providers}")

            # Pass explicit arguments to avoid signature confusion
            return _InferenceSession(path_or_bytes, sess_options, providers, **kwargs)

        ort.InferenceSession = InferenceSession
        IS_AVAILABLE = True

        # Monkeypatch ultralytics check_requirements to avoid auto-update loop
        # Ultralytics checks for 'onnxruntime' package, but we have 'onnxruntime-directml'
        # which provides the same module but different package metadata.
        try:
            from ultralytics.utils import checks

            _original_check_requirements = checks.check_requirements

            def _check_requirements(*args, **kwargs):
                # Helper to filter requirements
                def should_skip(r):
                    return "onnxruntime-gpu" in r or "onnxruntime" in r or "onnx" in r

                # Inspect arguments to find 'requirements'
                # signature is typically (requirements=(), exclude=(), install=True, ...)
                # logic: check first arg if present, or 'requirements' in kwargs

                reqs = args[0] if args else kwargs.get("requirements", ())

                if isinstance(reqs, (list, tuple)):
                    # Allow function to proceed but filter the list
                    filtered_reqs = [r for r in reqs if not should_skip(r)]

                    # Construct new args
                    if args:
                        args = (filtered_reqs,) + args[1:]
                    else:
                        kwargs["requirements"] = filtered_reqs

                elif isinstance(reqs, str):
                    if should_skip(reqs):
                        return True  # Skip entirely for single string check

                return _original_check_requirements(*args, **kwargs)

            checks.check_requirements = _check_requirements
        except ImportError:
            pass

        return True

    except ImportError:
        import logging

        logging.getLogger(__name__).warning("onnxruntime not installed or improper installation")
        return False
