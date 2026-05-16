import os
import torch
from comfy.utils import load_torch_file

class LoadLatentV2:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent_path": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "C:/path/to/file.latent",
                    },
                ),
                "target_dtype": (
                    ["auto", "fp16", "fp32"],
                    {"default": "auto"},
                ),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "load"
    CATEGORY = "latent"

    def load(self, latent_path, target_dtype):
        if not latent_path:
            raise ValueError("No latent path provided")

        latent_path = os.path.normpath(latent_path)

        if not os.path.isfile(latent_path):
            raise FileNotFoundError(f"Latent file not found: {latent_path}")

        if not latent_path.lower().endswith(".latent"):
            raise ValueError("File is not a .latent file")

        data = load_torch_file(latent_path)

        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("Invalid latent file format")

        # Normalize dtype if requested
        if target_dtype != "auto":
            dtype = torch.float16 if target_dtype == "fp16" else torch.float32

            for k, v in data.items():
                if torch.is_tensor(v):
                    data[k] = v.to(dtype=dtype)

        return (data,)