from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pipeline.comfy.provenance import extract_workflow_parameters, write_output_provenance
from pipeline.common.io import read_json


class ComfyProvenanceTests(unittest.TestCase):
    def test_extracts_models_sampler_vae_and_prompts(self) -> None:
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "anime.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["1", 1], "text": "positive"}},
            "3": {"class_type": "VAELoader", "inputs": {"vae_name": "vae.safetensors"}},
            "4": {
                "class_type": "KSampler",
                "inputs": {"model": ["1", 0], "seed": 11, "steps": 24, "cfg": 6.5, "sampler_name": "euler", "scheduler": "normal"},
            },
            "5": {"class_type": "SaveImage", "inputs": {"filename_prefix": "run/out"}},
        }

        extracted = extract_workflow_parameters(workflow)

        self.assertIn({"node_id": "1", "class_type": "CheckpointLoaderSimple", "role": "checkpoint", "field": "ckpt_name", "name": "anime.safetensors"}, extracted["models"])
        self.assertIn({"node_id": "3", "class_type": "VAELoader", "role": "vae", "field": "vae_name", "name": "vae.safetensors"}, extracted["models"])
        self.assertEqual(extracted["samplers"][0]["inputs"]["seed"], 11)
        self.assertEqual(extracted["prompts"][0]["inputs"]["text"], "positive")
        self.assertEqual(extracted["outputs"][0]["inputs"]["filename_prefix"], "run/out")

    def test_write_sidecar_binds_full_workflow_to_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            output = project_root / "runtime" / "out.png"
            output.parent.mkdir(parents=True)
            output.write_bytes(b"fake")
            workflow = {
                "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "anime.safetensors"}},
                "2": {"class_type": "KSampler", "inputs": {"seed": 7, "steps": 4}},
            }

            sidecar = write_output_provenance(
                output,
                project_root=project_root,
                workflow=workflow,
                workflow_name="unit_test_workflow",
                prompt_id="pid-1",
                client_id="agent:test|workflow:unit|run:abc",
                task_context={"case": "demo"},
            )

            data = read_json(sidecar)
            self.assertEqual(data["output_file"], "runtime/out.png")
            self.assertEqual(data["prompt_id"], "pid-1")
            self.assertEqual(data["workflow_api"], workflow)
            self.assertEqual(data["extracted_parameters"]["samplers"][0]["inputs"]["seed"], 7)


if __name__ == "__main__":
    unittest.main()
