from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import logging
from pathlib import Path
import time
from typing import Callable, TypeVar

from .comfyui import ComfyUiClient, workflow_exists
from .config import AppConfig, ParameterSet
from .lmstudio import LmStudioClient
from .prompt_quality import extract_prompt_pair, score_prompt_pair
from .report import write_summary
from .state import Checkpoint, append_jsonl, read_jsonl

T = TypeVar("T")


class BenchmarkRunner:
    def __init__(self, config: AppConfig, run_id: str | None = None) -> None:
        self.config = config
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = config.run.output_dir / self.run_id
        self.checkpoint_path = self.run_dir / "checkpoint.json"
        self.llm_results_path = self.run_dir / "llm_results.jsonl"
        self.image_jobs_path = self.run_dir / "image_jobs.jsonl"
        self.summary_path = self.run_dir / "summary.csv"
        self.log_path = self.run_dir / "run.log"
        self.checkpoint = Checkpoint.load(self.checkpoint_path)

    def run(self) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._setup_logging()
        logging.info("Run directory: %s", self.run_dir)

        lm_client = LmStudioClient(self.config.lmstudio)
        models = self.config.lmstudio.models or lm_client.list_models()
        if not models:
            raise RuntimeError("No LM Studio models configured or discovered.")
        logging.info("Models: %s", ", ".join(models))

        comfy_client: ComfyUiClient | None = None
        workflow = None
        if self.config.comfyui.enabled:
            if not workflow_exists(self.config.comfyui):
                raise FileNotFoundError(f"ComfyUI workflow not found: {self.config.comfyui.workflow_path}")
            comfy_client = ComfyUiClient(self.config.comfyui)
            comfy_client.check()
            workflow = comfy_client.load_workflow()
            logging.info("ComfyUI workflow loaded: %s", self.config.comfyui.workflow_path)

        for model in models:
            for parameter in self.config.parameters:
                self._run_llm_case(lm_client, model, parameter)

        if comfy_client and workflow:
            for row in read_jsonl(self.llm_results_path):
                if row.get("status") == "succeeded":
                    self._run_image_case(comfy_client, workflow, row)

        write_summary(self.summary_path, read_jsonl(self.llm_results_path), read_jsonl(self.image_jobs_path))
        logging.info("Summary written: %s", self.summary_path)
        return self.run_dir

    def _run_llm_case(self, client: LmStudioClient, model: str, parameter: ParameterSet) -> None:
        llm_key = make_llm_key(model, parameter)
        if llm_key in self.checkpoint.completed_llm:
            logging.info("Skip completed LLM case: %s", llm_key)
            return

        logging.info("Run LLM case: %s", llm_key)
        started_at = datetime.now().isoformat(timespec="seconds")
        try:
            result = retry(
                lambda: client.generate(model, parameter, self.config.run.fixed_instruction),
                retries=self.config.lmstudio.retries,
                sleep_sec=self.config.lmstudio.retry_sleep_sec,
            )
            pair = extract_prompt_pair(result.response_text)
            quality = score_prompt_pair(pair, self.config.quality)
            append_jsonl(
                self.llm_results_path,
                {
                    "llm_key": llm_key,
                    "status": "succeeded",
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "model": model,
                    "parameter_key": parameter.key,
                    "temperature": parameter.temperature,
                    "top_p": parameter.top_p,
                    "max_tokens": parameter.max_tokens,
                    "completion_tokens": result.completion_tokens,
                    "elapsed_sec": result.elapsed_sec,
                    "tokens_per_sec": result.tokens_per_sec,
                    "response_text": result.response_text,
                    "positive_prompt": pair.positive_prompt,
                    "negative_prompt": pair.negative_prompt,
                    "notes": pair.notes,
                    "parse_ok": pair.parse_ok,
                    "quality_score": quality.score,
                    "quality_reasons": quality.reasons,
                },
            )
            self.checkpoint.completed_llm.add(llm_key)
            self.checkpoint.save(self.checkpoint_path)
        except Exception as exc:
            logging.exception("LLM case failed: %s", llm_key)
            append_jsonl(
                self.llm_results_path,
                {
                    "llm_key": llm_key,
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "model": model,
                    "parameter_key": parameter.key,
                    "temperature": parameter.temperature,
                    "top_p": parameter.top_p,
                    "max_tokens": parameter.max_tokens,
                    "error": str(exc),
                },
            )

    def _run_image_case(self, client: ComfyUiClient, workflow: dict, row: dict) -> None:
        llm_key = str(row["llm_key"])
        if llm_key in self.checkpoint.completed_images:
            logging.info("Skip completed image case: %s", llm_key)
            return

        logging.info("Run image case: %s", llm_key)
        started_at = datetime.now().isoformat(timespec="seconds")
        try:
            prompt = client.build_prompt(workflow, str(row["positive_prompt"]), str(row["negative_prompt"]))
            prompt_id = retry(
                lambda: client.enqueue(prompt),
                retries=self.config.comfyui.retries,
                sleep_sec=self.config.comfyui.poll_interval_sec,
            )
            result = client.wait_for_history(prompt_id)
            append_jsonl(
                self.image_jobs_path,
                {
                    "llm_key": llm_key,
                    "status": result.status,
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "prompt_id": result.prompt_id,
                    "history": compact_history(result.history),
                },
            )
            if result.status != "timeout":
                self.checkpoint.completed_images.add(llm_key)
                self.checkpoint.save(self.checkpoint_path)
        except Exception as exc:
            logging.exception("Image case failed: %s", llm_key)
            append_jsonl(
                self.image_jobs_path,
                {
                    "llm_key": llm_key,
                    "status": "failed",
                    "started_at": started_at,
                    "finished_at": datetime.now().isoformat(timespec="seconds"),
                    "error": str(exc),
                },
            )

    def _setup_logging(self) -> None:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[
                logging.FileHandler(self.log_path, encoding="utf-8"),
                logging.StreamHandler(),
            ],
            force=True,
        )


def make_llm_key(model: str, parameter: ParameterSet) -> str:
    safe_model = "".join(char if char.isalnum() or char in "._-" else "_" for char in model)
    return f"{safe_model}__{parameter.key}"


def compact_history(history: dict) -> dict:
    outputs = history.get("outputs", {})
    return {
        "status": history.get("status", {}),
        "output_node_ids": sorted(outputs.keys()),
        "outputs": outputs,
    }


def retry(action: Callable[[], T], retries: int, sleep_sec: int) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return action()
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(sleep_sec)
    assert last_error is not None
    raise last_error
