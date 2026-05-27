import os
import torch
import folder_paths

class SaveLatentV2:
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
                "save_as_fp32": (
                    "BOOLEAN",
                    {
                        "default": True,
                    },
                ),
            }
        }

    RETURN_TYPES = ()
    FUNCTION = "save"
    OUTPUT_NODE = True
    CATEGORY = "latent"

    def save(self, latent, filename_prefix, save_as_fp32):
        # Preserve full latent structure
        latent_to_save = {}

        for k, v in latent.items():
            if torch.is_tensor(v):
                tensor = v.detach().cpu()

                # Optional: store as fp32 to avoid cumulative fp16 drift
                if save_as_fp32:
                    tensor = tensor.to(torch.float32)

                latent_to_save[k] = tensor
            else:
                latent_to_save[k] = v

        output_dir = folder_paths.get_output_directory()

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
            latent_to_save,
            full_path,
            _use_new_zipfile_serialization=True,
        )

        print(f"[SaveLatentV2] Saved latent: {full_path}")
        return ()