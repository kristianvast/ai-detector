"""
PyInstaller hook for llama-cpp-python

This hook ensures that llama-cpp-python and its native libraries
are properly included in the executable.
"""

from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files
import llama_cpp
import os

# Collect dynamic libraries
binaries = collect_dynamic_libs('llama_cpp')

# Collect data files (model files, etc.)
datas = collect_data_files('llama_cpp')

# Add hidden imports
hiddenimports = [
    'llama_cpp',
    'llama_cpp.llama',
    'llama_cpp.llama_cpp',
    'llama_cpp.llama_grammar',
    'llama_cpp.llama_chat_format',
]

# Platform-specific binaries
import platform
if platform.system() == 'Darwin':
    # macOS Metal support
    hiddenimports.extend([
        'llama_cpp.llama_cpp_metal',
    ])
elif platform.system() == 'Windows':
    # Windows CUDA support (if available)
    hiddenimports.extend([
        'llama_cpp.llama_cpp_cuda',
    ])
elif platform.system() == 'Linux':
    # Linux CUDA/OpenCL support
    hiddenimports.extend([
        'llama_cpp.llama_cpp_cuda',
        'llama_cpp.llama_cpp_opencl',
    ])
