# How to use this file
#
# 1. create a folder called "hooks" in your repo
# 2. copy this file there
# 3. add the --additional-hooks-dir flag to your pyinstaller command:
#    ex: `pyinstaller --name binary-name --additional-hooks-dir=./hooks entry-point.py`


import os
import sys

from PyInstaller.utils.hooks import collect_data_files, get_package_paths

# Get the package path
package_path = get_package_paths("llama_cpp")[0]

# Collect data files
datas = collect_data_files("llama_cpp")

libs = [
    "ggml-base",
    "ggml-cpu",
    "ggml-cuda",
    "ggml",
    "llama",
    "mtmd",
]

# Append the additional .dll or .so file
if os.name == "nt":  # Windows
    for lib in libs:
        dll_path = os.path.join(package_path, "llama_cpp", "lib", f"{lib}.dll")
        datas.append((dll_path, "llama_cpp"))
        datas.append((dll_path, "llama_cpp/lib"))
elif sys.platform == "darwin":  # Mac
    for lib in libs:
        so_path = os.path.join(package_path, "llama_cpp", "lib", f"lib{lib}.dylib")
        datas.append((so_path, "llama_cpp"))
        datas.append((so_path, "llama_cpp/lib"))
elif os.name == "posix":  # Linux
    for lib in libs:
        so_path = os.path.join(package_path, "llama_cpp", "lib", f"lib{lib}.so")
        datas.append((so_path, "llama_cpp"))
        datas.append((so_path, "llama_cpp/lib"))
