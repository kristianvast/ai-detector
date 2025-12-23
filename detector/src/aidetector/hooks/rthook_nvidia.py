import os

if os.name == "nt":
    try:
        import torch

        torch_file = torch.__file__
        if torch_file is None:
            raise Exception("torch.__file__ is None")
        torch_dir = os.path.dirname(torch_file)
        torch_lib_path = os.path.join(torch_dir, "lib")
        if os.path.exists(torch_lib_path) and hasattr(os, "add_dll_directory"):
            os.add_dll_directory(torch_lib_path)
    except Exception:
        pass
