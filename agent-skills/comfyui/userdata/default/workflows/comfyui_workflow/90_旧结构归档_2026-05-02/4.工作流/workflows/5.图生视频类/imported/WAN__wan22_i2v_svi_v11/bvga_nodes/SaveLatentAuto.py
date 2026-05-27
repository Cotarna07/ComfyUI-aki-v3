import os
import torch
import folder_paths

class SaveLatentAuto:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "latent": ("LATENT",),
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "latents/latent",
                        "multiline": False,
                    },
                ),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "latent"

    def save(self, latent, filename_prefix):
        # Extract tensor
        samples = latent["samples"].detach().cpu()

        # ComfyUI output root (e.g. output/)
        output_dir = folder_paths.get_output_directory()

        # Native ComfyUI auto-numbering helper
        (
            full_output_folder,
            filename,
            counter,
            subfolder,
            resolved_prefix,
        ) = folder_paths.get_save_image_path(
            filename_prefix,
            output_dir,
        )

        os.makedirs(full_output_folder, exist_ok=True)

        output_name = f"{filename}_{counter:05d}_.latent"
        full_path = os.path.join(full_output_folder, output_name)

        torch.save(
            {"samples": samples},
            full_path,
            _use_new_zipfile_serialization=True,
        )

        print(f"[SaveLatentAuto] Saved latent: {full_path}")
        return ()
