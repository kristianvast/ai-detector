import glob
import os

from PyInstaller.utils.hooks import get_package_paths

# Get the package path
pkg_base, pkg_dir = get_package_paths("llama_cpp")

# Find all DLLs in the package directory
dlls = glob.glob(os.path.join(pkg_dir, "*.dll"))

# Add them as binaries, preserving the folder structure (putting them inside llama_cpp in the bundle)
binaries = []
for dll in dlls:
    binaries.append((dll, "llama_cpp"))
