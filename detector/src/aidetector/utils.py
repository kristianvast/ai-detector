import os

import gguf
import psutil


def get_system_vram_limit():
    """
    Returns the estimated safe VRAM limit in bytes.
    - NVIDIA: Uses pynvml to check free VRAM.
    - Mac (Metal): Uses psutil to check available Unified RAM (minus safe buffer).
    - CPU: Returns 0.
    """
    # 1. Check for NVIDIA GPU
    try:
        import pynvml

        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pynvml.nvmlShutdown()
        # Leave 500MB buffer for display overhead
        return info.free - (500 * 1024 * 1024)
    except Exception:
        pass  # Not NVIDIA

    # 2. Check for Mac (Apple Silicon)
    if os.uname().sysname == "Darwin":
        # Mac Unified Memory logic
        vm = psutil.virtual_memory()

        # Apple limits Metal usage to roughly 75% of TOTAL RAM.
        # We use 70% to be safe and allow for some OS overhead.
        return int(vm.total * 0.70)

    return 0  # No GPU detected


def calculate_optimal_layers(model_path):
    """
    Peeks at the GGUF file and calculates how many layers fit in VRAM.
    """
    # 1. Get Model Info without loading it
    reader = gguf.GGUFReader(model_path)

    # Extract total layers from metadata
    # Qwen2/3 architecture usually uses 'llm_kv.n_layer' or similar
    n_layers = 0
    for field in reader.fields.values():
        if "n_layer" in field.name or "block_count" in field.name:
            n_layers = field.parts[-1][0]  # Get the value
            break

    if n_layers == 0:
        print("⚠️  Could not detect layer count. Defaulting to CPU.")
        return 0

    # 2. Calculate Size per Layer
    file_size = os.path.getsize(model_path)

    # We reserve ~1GB for the 'non-layer' overhead (Vision Projector + Context Cache)
    # This is a heuristic, but usually accurate enough.
    overhead_bytes = 1.5 * 1024 * 1024 * 1024

    bytes_per_layer = file_size / n_layers

    # 3. Check Hardware
    available_vram = get_system_vram_limit()

    print("🔍 Analysis:")
    print(f"   - Model File: {file_size / (1024**3):.2f} GB")
    print(f"   - Total Layers: {n_layers}")
    print(f"   - Est. Layer Size: {bytes_per_layer / (1024**2):.2f} MB")
    print(f"   - Available VRAM: {available_vram / (1024**3):.2f} GB")

    if available_vram <= overhead_bytes:
        return 0

    # 4. The Math
    # (Available - Overhead) / Size per Layer
    possible_layers = (available_vram - overhead_bytes) / bytes_per_layer

    # Round down to be safe
    optimal_layers = int(possible_layers)

    # Clamp (Don't exceed actual model layers)
    if optimal_layers >= n_layers:
        return -1  # Special flag for "Load Everything"

    # Safety floor
    if optimal_layers < 0:
        optimal_layers = 0

    return optimal_layers
