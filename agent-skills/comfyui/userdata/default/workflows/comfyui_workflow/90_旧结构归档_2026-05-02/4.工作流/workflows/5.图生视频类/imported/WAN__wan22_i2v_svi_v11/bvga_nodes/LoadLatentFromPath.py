import os
from comfy.utils import load_torch_file

class LoadLatentFromPath:
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
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "load"
    CATEGORY = "latent"

    def load(self, latent_path):
        if not latent_path:
            raise ValueError("No latent path provided")

        latent_path = os.path.normpath(latent_path)

        if not os.path.isfile(latent_path):
            raise FileNotFoundError(f"Latent file not found: {latent_path}")

        if not latent_path.lower().endswith(".latent"):
            raise ValueError("File is not a .latent file")

        # SAFE: uses ComfyUI’s vetted torch loader
        data = load_torch_file(latent_path)

        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("Invalid latent file format")

        return (data,)
