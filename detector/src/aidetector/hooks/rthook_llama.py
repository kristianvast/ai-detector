import os
import sys

# Get the internal folder where PyInstaller unpacks the app
_base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

# The folder where we will tell PyInstaller to put the DLLs
_lib_path = os.path.join(_base_path, "llama_cpp", "lib")

# Force Windows to look in this directory when loading DLLs
os.environ["PATH"] = _lib_path + os.pathsep + os.environ["PATH"]

if hasattr(os, "add_dll_directory"):
    try:
        os.add_dll_directory(_lib_path)
    except Exception:
        pass
