from PyInstaller.utils.hooks import collect_dynamic_libs

# Automatically collect all shared libraries
binaries = collect_dynamic_libs("llama_cpp")
print(f"🚀 Hook executed at compile time: {binaries}")
