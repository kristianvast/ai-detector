from typing import Self

from huggingface_hub.file_download import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler

from aidetector.config import Config
from aidetector.detector import Detector


class Manager:
    detectors: list[Detector]

    def __init__(self, detectors: list[Detector]):
        self.detectors = detectors

    @classmethod
    def from_config(cls, config: Config) -> Self:
        llama: Llama | None = None
        if config.vlm is not None:
            llama = Llama(
                model_path=hf_hub_download(config.vlm.repo, config.vlm.model),
                chat_handler=Qwen3VLChatHandler(clip_model_path=hf_hub_download(config.vlm.repo, config.vlm.mmproj)),
                n_ctx=config.vlm.context,
                n_gpu_layers=-1,
                verbose=False,
            )
        return cls([Detector.from_config(config, detector, llama) for detector in config.detectors])

    def start(self):
        for detector in self.detectors:
            detector.start()
