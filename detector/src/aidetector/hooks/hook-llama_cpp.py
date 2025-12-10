# How to use this file
#
# 1. create a folder called "hooks" in your repo
# 2. copy this file there
# 3. add the --additional-hooks-dir flag to your pyinstaller command:
#    ex: `pyinstaller --name binary-name --additional-hooks-dir=./hooks entry-point.py`


import os
import sys

from PyInstaller.utils.hooks import collect_data_files, get_package_paths

package_path = get_package_paths("llama_cpp")[0]
datas = collect_data_files("llama_cpp")
if os.name == "nt":  # Windows
    for l in ["ggml", "llama", "llava"]:
        dll_path = os.path.join(package_path, "llama_cpp", "lib", f"{l}.dll")
        datas.append((dll_path, "llama_cpp/lib"))
elif sys.platform == "darwin":  # Mac
    for l in ["ggml", "llama", "llava"]:
        dylib_path = os.path.join(package_path, "llama_cpp", "lib", f"lib{l}.dylib")
        datas.append((dylib_path, "llama_cpp/lib"))
elif os.name == "posix":  # Linux
    for l in ["ggml", "llama", "llava"]:
        so_path = os.path.join(package_path, "llama_cpp", "lib", f"lib{l}.so")
        datas.append((so_path, "llama_cpp/lib"))
