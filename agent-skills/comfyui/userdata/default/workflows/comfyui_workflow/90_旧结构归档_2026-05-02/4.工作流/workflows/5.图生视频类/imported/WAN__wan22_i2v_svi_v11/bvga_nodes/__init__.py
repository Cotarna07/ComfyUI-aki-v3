from .LoadLatentFromPath import LoadLatentFromPath
from .SaveLatentAuto import SaveLatentAuto
from.LoadLatentFromPathv2 import LoadLatentV2
from.SaveLatentAutov2 import SaveLatentV2

NODE_CLASS_MAPPINGS = {
    "LoadLatentFromPath": LoadLatentFromPath,
    "SaveLatentAuto": SaveLatentAuto,
     "LoadLatentV2": LoadLatentV2,
     "SaveLatentV2": SaveLatentV2,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoadLatentFromPath": "Load Latent (Path)",
    "SaveLatentAuto": "Save Latent (Auto Path)",
     "LoadLatentV2": "Load Latent V2",
     "SaveLatentV2": "Save Latent V2",
}