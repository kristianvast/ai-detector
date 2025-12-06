from typing import Self

from huggingface_hub.file_download import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_chat_format import Qwen3VLChatHandler

from aidetector.config import Config
from aidetector.detector import Detector
from aidetector.utils import calculate_optimal_layers


class Manager:
    detectors: list[Detector]

    def __init__(self, detectors: list[Detector]):
        self.detectors = detectors

    @classmethod
    def from_config(cls, config: Config) -> Self:
        llama: Llama | None = None
        if config.vlm is not None:
            model_path = hf_hub_download(config.vlm.repo, config.vlm.model)
            n_gpu_layers = config.vlm.n_gpu_layers if config.vlm.n_gpu_layers else calculate_optimal_layers(model_path)
            llama = Llama(
                model_path=model_path,
                chat_handler=Qwen3VLChatHandler(clip_model_path=hf_hub_download(config.vlm.repo, config.vlm.mmproj)),
                n_ctx=config.vlm.n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )
        return cls([Detector.from_config(config, detector, llama) for detector in config.detectors])

    def start(self):
        for detector in self.detectors:
            detector.start()
