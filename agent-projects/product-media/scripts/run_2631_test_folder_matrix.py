# -*- coding: utf-8 -*-
"""Run a creative product-image matrix from TEST/26-5-31 workflows.

The script is intentionally self-contained: it picks five product inputs,
builds fantasy-cartoon prompts, converts TEST workflows through ComfyUI,
runs the currently runnable workflow variants, and writes an HTML report.
"""

from __future__ import annotations

import argparse
import copy
import html
import json
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")


REPO = Path(__file__).resolve().parents[3]
COMFY_INPUT = REPO / "ComfyUI" / "input"
COMFY_OUTPUT = REPO / "ComfyUI" / "output"
COMFY_MAIN = REPO / "ComfyUI" / "main.py"
COMFY_ROOT = REPO / "ComfyUI"
COMFY_PYTHON = REPO / "python" / "python.exe"
TEST_WORKFLOW_DIR = REPO / "agent-skills" / "comfyui" / "workflows" / "TEST" / "26-5-31"
RUNTIME_ROOT = REPO / "agent-projects" / "product-media" / "runtime" / "product_image"
LOG_ROOT = REPO / "agent-projects" / "product-media" / "runtime" / "logs"
DEFAULT_SOURCE_BATCH = RUNTIME_ROOT / "aliexpress_lego_5_20260531"
DEFAULT_PRODUCT_INPUT_DIR = DEFAULT_SOURCE_BATCH / "selected_cutouts_20260531"

sys.path.insert(0, str(REPO / "agent-projects" / "comfyui-shared"))
from comfyui_shared.client import ComfyClient, ComfyClientConfig  # noqa: E402


@dataclass(frozen=True)
class ProductSpec:
    product_id: str
    label: str
    source_image: Path
    prompt: str
    color_script: str


@dataclass(frozen=True)
class VariantSpec:
    variant_id: str
    title: str
    unet_name: str
    steps: int = 4
    megapixels: float = 1.0
    lora_name: str | None = None
    lora_strength: float = 0.0
    heavy: bool = False


@dataclass
class JobRecord:
    product_id: str
    label: str
    variant_id: str
    variant_title: str
    prompt: str
    source_image: str
    status: str
    seed: int
    model: str
    lora: str | None = None
    lora_strength: float | None = None
    prompt_id: str | None = None
    api_path: str | None = None
    outputs: list[str] = field(default_factory=list)
    error: str | None = None
    skip_reason: str | None = None
    elapsed_seconds: float | None = None


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve())).replace("\\", "/")
    except ValueError:
        return str(path)


def rel_to(path: Path, base: Path) -> str:
    return path.resolve().relative_to(base.resolve()).as_posix()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def http_json(server: str, method: str, path: str, body: Any | None = None, timeout: int = 120) -> Any:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(server.rstrip("/") + path, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8") or "{}"
            return json.loads(raw)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {path}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Cannot reach ComfyUI {path}: {exc.reason}") from exc


def free_comfy_memory(server: str) -> None:
    try:
        http_json(server, "POST", "/free", {"unload_models": True, "free_memory": True}, timeout=10)
    except Exception as exc:
        print(f"[warn] /free failed: {exc}")


def server_ready(server: str) -> bool:
    try:
        http_json(server, "GET", "/system_stats", timeout=5)
        return True
    except Exception:
        return False


def ensure_comfy_server(
    server: str,
    run_dir: Path,
    no_auto_start: bool,
    startup_timeout: int,
    comfy_python: Path,
    comfy_main: Path,
) -> dict[str, str | int | bool | None]:
    if server_ready(server):
        return {"started": False, "status": "already_ready", "server": server}
    if no_auto_start:
        raise RuntimeError(f"ComfyUI is not reachable at {server} and --no-auto-start was set.")

    parsed = urlparse(server)
    host = parsed.hostname or "127.0.0.1"
    if host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(f"Auto-start only supports local ComfyUI servers, got {server}")
    if not comfy_python.exists():
        raise RuntimeError(f"ComfyUI bundled Python not found: {comfy_python}")
    if not comfy_main.exists():
        raise RuntimeError(f"ComfyUI main.py not found: {comfy_main}")

    port = parsed.port or 8188
    listen = "127.0.0.1" if host == "localhost" else host
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stdout_log = LOG_ROOT / f"comfyui_2631_matrix_{stamp}.out.log"
    stderr_log = LOG_ROOT / f"comfyui_2631_matrix_{stamp}.err.log"
    args = [
        str(comfy_python),
        str(comfy_main),
        "--listen",
        listen,
        "--port",
        str(port),
        "--preview-method",
        "auto",
        "--disable-cuda-malloc",
        "--disable-dynamic-vram",
        "--disable-mmap",
        "--disable-auto-launch",
        "--enable-manager",
    ]
    stdout_handle = stdout_log.open("w", encoding="utf-8", errors="replace")
    stderr_handle = stderr_log.open("w", encoding="utf-8", errors="replace")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        args,
        cwd=COMFY_ROOT,
        stdout=stdout_handle,
        stderr=stderr_handle,
        creationflags=creationflags,
    )
    stdout_handle.close()
    stderr_handle.close()
    launch_record: dict[str, str | int | bool | None] = {
        "started": True,
        "status": "starting",
        "server": server,
        "pid": process.pid,
        "stdout_log": display_path(stdout_log),
        "stderr_log": display_path(stderr_log),
        "command": " ".join(args),
    }
    write_json(run_dir / "comfyui_launch.json", launch_record)
    print(f"[comfyui] started PID {process.pid}; waiting up to {startup_timeout}s")
    print(f"[comfyui] logs: {stdout_log} ; {stderr_log}")

    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if server_ready(server):
            launch_record["status"] = "ready"
            write_json(run_dir / "comfyui_launch.json", launch_record)
            print(f"[comfyui] ready: {server}")
            return launch_record
        if process.poll() is not None:
            launch_record["status"] = "exited"
            launch_record["returncode"] = process.returncode
            write_json(run_dir / "comfyui_launch.json", launch_record)
            raise RuntimeError(
                f"ComfyUI exited before becoming ready. See logs: {stdout_log} ; {stderr_log}"
            )
        time.sleep(5)

    launch_record["status"] = "timeout"
    write_json(run_dir / "comfyui_launch.json", launch_record)
    raise RuntimeError(f"ComfyUI did not become ready within {startup_timeout}s. See logs: {stdout_log} ; {stderr_log}")


def convert_workflow(server: str, workflow_path: Path) -> dict[str, Any]:
    return http_json(server, "POST", "/workflow/convert", read_json(workflow_path), timeout=180)


def required_class_types(api_graph: dict[str, Any]) -> set[str]:
    return {
        node.get("class_type")
        for node in api_graph.values()
        if isinstance(node, dict) and isinstance(node.get("class_type"), str)
    }


def available_model_names(object_info: dict[str, Any], node_type: str, input_name: str) -> set[str]:
    req = object_info.get(node_type, {}).get("input", {}).get("required", {})
    value = req.get(input_name)
    if isinstance(value, list) and value and isinstance(value[0], list):
        return {str(item) for item in value[0]}
    return set()


def preflight_workflows(server: str, run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    stats = http_json(server, "GET", "/system_stats", timeout=10)
    object_info = http_json(server, "GET", "/object_info", timeout=20)
    available_nodes = set(object_info)
    api_dir = run_dir / "api_converted"
    workflows: list[dict[str, Any]] = []
    for path in sorted(TEST_WORKFLOW_DIR.glob("*.json")):
        record: dict[str, Any] = {
            "workflow": path.name,
            "source": display_path(path),
            "status": "unknown",
        }
        try:
            api_graph = convert_workflow(server, path)
            write_json(api_dir / f"{path.stem}.api.json", api_graph)
            missing_nodes = sorted(required_class_types(api_graph) - available_nodes)
            record.update(
                {
                    "status": "converted",
                    "api_node_count": len(api_graph),
                    "missing_node_types": missing_nodes,
                    "converted_api": display_path(api_dir / f"{path.stem}.api.json"),
                }
            )
            if path.name == "image_flux2_klein_image_edit_4b_distilled.json":
                record["matrix_role"] = "runnable_primary"
                record["notes"] = "Patched to SaveImage 9 branch, FLUX2 VAE, and model variants."
            elif path.name == "templates-qwen_image_edit-crop_and_stitch-fusion.json":
                record["matrix_role"] = "blocked_optional_lora_route"
                record["notes"] = "Qwen route has LoRA nodes, but local main Qwen Image Edit model/Fusion LoRA are not ready."
            elif path.name == "image_flux2_fp8.json":
                record["matrix_role"] = "blocked_missing_flux2_full"
                record["notes"] = "Flux2 full route remains blocked by missing full-model assets."
            elif path.name.startswith("template_ltx2_3") or "WAN2.2" in path.name:
                record["matrix_role"] = "video_or_upscale_not_static_product_i2i"
                record["notes"] = "Not used for static product creative image generation in this run."
            else:
                record["matrix_role"] = "diagnostic_only"
                record["notes"] = "Converted for visibility, not a tested route."
        except Exception as exc:
            record.update({"status": "convert_failed", "error": str(exc)})
        workflows.append(record)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "server": server,
        "system_stats": stats,
        "workflow_dir": display_path(TEST_WORKFLOW_DIR),
        "workflows": workflows,
        "unet_models": sorted(available_model_names(object_info, "UNETLoader", "unet_name")),
        "lora_models": sorted(available_model_names(object_info, "LoraLoaderModelOnly", "lora_name")),
    }
    write_json(run_dir / "preflight.json", report)
    return report, object_info


def pick_products(input_dir: Path, max_products: int = 5) -> list[ProductSpec]:
    product_templates: dict[str, tuple[str, str, str]] = {
        "1005007109462323": (
            "blue brick police car and small aircraft",
            "urban police chase palette: sapphire blue, siren red, cyan window light, wet road reflections",
            "Use the input blue brick police vehicle set as the locked hero product reference. Preserve the exact toy-brick silhouette, blue body, roof light bar, "
            "wheel count, cockpit/window shape, yellow side stripe and the small aircraft/drone if visible; do not redesign the vehicle or add/remove parts. "
            "Show that same police car speeding along a miniature city road during an urgent patrol: wet asphalt lanes, crosswalk markings, sidewalks, traffic lights, "
            "shop windows, apartment buildings and blue-red siren reflections. Use a dynamic low tracking camera beside the road, the product itself sharp and readable, "
            "motion blur only in the background road lights, glossy plastic brick material, warm city windows and clear urban depth. The aircraft/drone should fly above the same city street. "
            "Edit the scene, lighting and atmosphere only; keep original markings if visible, no invented readable text, no race track, no forest, no packaging, no watermark.",
        ),
        "1005009067934624": (
            "red open-wheel brick race car",
            "high-speed grand-prix palette: crimson car, white track markings, sunset orange, stadium light streaks",
            "Use the input red open-wheel brick race car as the locked hero product reference. Preserve the exact exposed-wheel layout, four tires, red brick body, "
            "front wing, rear wing, cockpit/driver area and toy-brick proportions; do not turn it into a different car and do not add/remove major parts. "
            "Show that same race car speeding on a grand-prix circuit, not parked: asphalt racing lane, red-and-white curbs, pit wall, grandstands, finish-line gantry, stadium lights, "
            "tire barriers and light confetti in the background. Use a low chase camera close to the asphalt, the race car sharp and readable, strong speed lines on the track edges only, "
            "glossy toy reflections and warm sunset race-day lighting. Keep it clearly an open-wheel race car in a race venue, no city street, no off-road scene, no packaging, "
            "no invented readable sponsor text, no watermark.",
        ),
        "1005010410824249": (
            "green blocky creeper-style figure",
            "voxel survival game palette: grass green, dirt brown, torch amber, moonlit blue",
            "Use the input green blocky creeper-style figure as the locked hero product reference. Preserve the exact tall rectangular body, square head, green pixel pattern, "
            "blocky feet/legs and simple toy-brick geometry; do not change it into a different monster and do not add extra limbs or accessories. "
            "Place that same figure in a blocky voxel survival game scene: square grass blocks, dirt blocks, cube trees, torchlight, a small block-built player base, "
            "stone cave entrance and moonlit sky. The figure should play its expected role as a sneaky hostile mob approaching the player base from the grass. "
            "Use crisp foreground focus, readable square edges, torch amber highlights and subtle green particle tension. No extra main monsters, no real game logo, "
            "no readable text, no packaging, no watermark.",
        ),
        "1005010739958948": (
            "red brick sports car",
            "sports-car road commercial palette: coral red, golden sun, turquoise coast, clean black asphalt",
            "Use the input red brick sports car as the locked hero product reference. Preserve the exact red coupe silhouette, wheel count, windshield/cockpit shape, "
            "front bumper, rear spoiler if visible and toy-brick proportions; do not turn it into a realistic supercar, open-wheel racer or spaceship. "
            "Show that same sports car speeding through a proper road-car commercial scene: smooth coastal highway or modern city boulevard, guardrails, lane markings, palm silhouettes, "
            "distant ocean, clean asphalt and golden-hour reflections. Use a low tracking camera parallel to the road, the car sharp and readable, bright sun flare, glossy red toy-brick highlights "
            "and controlled speed trails only in the background. No readable road signs, no logos, no packaging, no watermark.",
        ),
        "1005008273906722": (
            "wizard bathroom wall set with minifigures",
            "high-angle wizard bathroom palette: candle gold, teal magic steam, warm stone, polished tile reflections",
            "Use the input wizard-themed bathroom wall set as the locked hero product reference. Preserve the exact wall structure, tiled floor base, sinks, mirrors/arches, "
            "pipes, potion bottles and the visible minifigure count and positions as much as possible; do not replace it with a generic castle hall and do not add extra main characters. "
            "Test a wider long-shot composition from a high three-quarter overhead camera: show the complete bathroom playset as a small architectural room inside an enchanted castle washroom, "
            "with stone arches, tiled floor, sinks, mirrors, pipes, potion bottles, warm candle sconces, teal magical steam and polished tile reflections. Keep the entire product sharp, centered, "
            "uncropped and readable, with the bathroom wall set as the main subject and surrounding castle architecture only supporting it. No outdoor scene, no readable text, no logos, no packaging, no watermark.",
        ),
    }
    products: list[ProductSpec] = []
    for product_id, (label, color_script, prompt) in product_templates.items():
        path = input_dir / f"{product_id}_cutout_on_light.png"
        if not path.exists():
            path = DEFAULT_SOURCE_BATCH / "outputs" / f"{product_id}_locked_studio_light.png"
        if path.exists():
            products.append(ProductSpec(product_id, label, path, prompt, color_script))
        if len(products) >= max_products:
            break
    if len(products) < max_products:
        for path in sorted(input_dir.glob("*_cutout_on_light.png")):
            product_id = path.name.split("_")[0]
            if any(item.product_id == product_id for item in products):
                continue
            prompt = (
                "Create a polished fantasy-cartoon toy-commercial key visual from the input product. "
                "First identify the product's natural scene and role, then place it there with appropriate action or viewing angle. Vehicles should be shown moving in their proper road or track environment, "
                "and architectural playsets should use a wider high-angle view that keeps the whole set readable. Keep the product sharp, preserve major structure and colors, "
                "avoid unrelated fantasy scenery, no readable text, no packaging, no watermark."
            )
            products.append(ProductSpec(product_id, "auto-selected product", path, prompt, "action-scene or high-angle product-context palette"))
            if len(products) >= max_products:
                break
    if not products:
        raise RuntimeError(f"No product inputs found in {input_dir}")
    return products


def build_variants(object_info: dict[str, Any], include_heavy: bool) -> list[VariantSpec]:
    unets = available_model_names(object_info, "UNETLoader", "unet_name")
    loras = available_model_names(object_info, "LoraLoaderModelOnly", "lora_name")
    candidates = [
        VariantSpec("klein_4b_fp8", "Flux2 Klein 4B FP8 4-step", "flux-2-klein-4b-fp8.safetensors", steps=4),
        VariantSpec("klein_base_4b_fp8_16step", "Flux2 Klein Base 4B FP8 16-step", "flux-2-klein-base-4b-fp8.safetensors", steps=16),
        VariantSpec("klein_9b", "Flux2 Klein 9B", "flux-2-klein-9b.safetensors", steps=4, heavy=True),
        VariantSpec(
            "klein_4b_flux2_turbo_lora",
            "Flux2 Klein 4B + Flux2 Turbo LoRA",
            "flux-2-klein-4b-fp8.safetensors",
            steps=4,
            lora_name="Flux2TurboComfyv2.safetensors",
            lora_strength=0.65,
        ),
    ]
    variants: list[VariantSpec] = []
    for item in candidates:
        if item.heavy and not include_heavy:
            continue
        model_ok = item.unet_name in unets
        lora_ok = item.lora_name is None or item.lora_name in loras
        if model_ok and lora_ok:
            variants.append(item)
    return variants


def skipped_variants(object_info: dict[str, Any], include_heavy: bool) -> list[dict[str, str]]:
    unets = available_model_names(object_info, "UNETLoader", "unet_name")
    loras = available_model_names(object_info, "LoraLoaderModelOnly", "lora_name")
    skipped: list[dict[str, str]] = []
    checks = [
        ("klein_9b", "Flux2 Klein 9B", "flux-2-klein-9b.safetensors", None, not include_heavy),
        ("klein_4b_flux2_turbo_lora", "Flux2 Klein 4B + Flux2 Turbo LoRA", "flux-2-klein-4b-fp8.safetensors", "Flux2TurboComfyv2.safetensors", False),
    ]
    for variant_id, title, model, lora, disabled_heavy in checks:
        if disabled_heavy:
            skipped.append({"variant_id": variant_id, "title": title, "reason": "Skipped by default; pass --include-heavy to test the 9B model."})
            continue
        if model not in unets:
            skipped.append({"variant_id": variant_id, "title": title, "reason": f"UNET not available in ComfyUI object_info: {model}"})
        elif lora and lora not in loras:
            skipped.append({"variant_id": variant_id, "title": title, "reason": f"Compatible LoRA not available in object_info: {lora}"})
    return skipped


def dependency_node_ids(api_graph: dict[str, Any], roots: list[str]) -> set[str]:
    seen: set[str] = set()
    stack = list(roots)

    def visit(value: Any) -> None:
        if isinstance(value, list):
            if len(value) == 2 and isinstance(value[0], str) and value[0] in api_graph:
                stack.append(value[0])
            else:
                for item in value:
                    visit(item)
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)

    while stack:
        node_id = stack.pop()
        if node_id in seen or node_id not in api_graph:
            continue
        seen.add(node_id)
        visit(api_graph[node_id].get("inputs", {}))
    return seen


def prune_to_roots(api_graph: dict[str, Any], roots: list[str]) -> dict[str, Any]:
    keep = dependency_node_ids(api_graph, roots)
    return {node_id: copy.deepcopy(api_graph[node_id]) for node_id in sorted(keep)}


def set_input(api_graph: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
    api_graph[node_id].setdefault("inputs", {})[input_name] = value


def inject_lora(api_graph: dict[str, Any], model_node: str, guider_node: str, variant: VariantSpec) -> None:
    if not variant.lora_name:
        return
    lora_node = "agent:lora"
    api_graph[lora_node] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "model": [model_node, 0],
            "lora_name": variant.lora_name,
            "strength_model": variant.lora_strength,
        },
        "_meta": {"title": f"Agent LoRA {variant.lora_name}"},
    }
    set_input(api_graph, guider_node, "model", [lora_node, 0])


def stage_input(product: ProductSpec, batch_id: str) -> str:
    dst_dir = COMFY_INPUT / "agent_product_tests" / batch_id / "test_2631_matrix_inputs"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{product.product_id}_{product.source_image.name}"
    shutil.copy2(product.source_image, dst)
    return dst.relative_to(COMFY_INPUT).as_posix()


def build_flux2_klein_graph(
    source_api: dict[str, Any],
    product: ProductSpec,
    variant: VariantSpec,
    prompt: str,
    seed: int,
    batch_id: str,
) -> dict[str, Any]:
    api_graph = prune_to_roots(source_api, ["9"])
    input_name = stage_input(product, batch_id)
    set_input(api_graph, "76", "image", input_name)
    set_input(api_graph, "75:74", "text", prompt)
    set_input(api_graph, "75:73", "noise_seed", seed)
    set_input(api_graph, "75:72", "vae_name", "FLUX2\\flux2-vae.safetensors")
    set_input(api_graph, "75:70", "unet_name", variant.unet_name)
    set_input(api_graph, "75:62", "steps", variant.steps)
    set_input(api_graph, "75:80", "megapixels", variant.megapixels)
    set_input(
        api_graph,
        "9",
        "filename_prefix",
        f"agent_runs/{batch_id}/test_2631_matrix/{product.product_id}_{variant.variant_id}_s{seed}",
    )
    inject_lora(api_graph, "75:70", "75:63", variant)
    return api_graph


def collect_outputs(history_item: dict[str, Any], output_dir: Path) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []
    for node_output in history_item.get("outputs", {}).values():
        for image in node_output.get("images", []):
            if image.get("type") != "output":
                continue
            src = COMFY_OUTPUT / image.get("subfolder", "") / image["filename"]
            if not src.exists():
                continue
            dst = output_dir / image["filename"]
            shutil.copy2(src, dst)
            saved.append(str(dst))
    return saved


def extract_history_error(history_item: dict[str, Any]) -> str | None:
    messages = history_item.get("status", {}).get("messages", [])
    for message in reversed(messages):
        if not isinstance(message, list) or len(message) < 2:
            continue
        kind, payload = message[0], message[1]
        if kind != "execution_error" or not isinstance(payload, dict):
            continue
        node = payload.get("node_id")
        node_type = payload.get("node_type")
        exc_type = payload.get("exception_type")
        exc_message = str(payload.get("exception_message", "")).strip()
        return f"{node} {node_type}: {exc_type}: {exc_message}"
    return None


def run_matrix(
    server: str,
    run_dir: Path,
    products: list[ProductSpec],
    variants: list[VariantSpec],
    dry_run: bool,
    no_wait: bool,
    base_seed: int,
) -> list[JobRecord]:
    workflow_path = TEST_WORKFLOW_DIR / "image_flux2_klein_image_edit_4b_distilled.json"
    source_api = convert_workflow(server, workflow_path)
    api_dir = run_dir / "api_jobs"
    output_dir = run_dir / "outputs"
    records_dir = run_dir / "records"
    client = ComfyClient(
        ComfyClientConfig(
            server=server,
            prompt_timeout_seconds=1800,
            poll_interval_seconds=2.0,
        )
    )
    records: list[JobRecord] = []
    job_index = 0
    last_model = None
    for product in products:
        for variant in variants:
            job_index += 1
            seed = base_seed + job_index
            if last_model and last_model != variant.unet_name and not dry_run:
                free_comfy_memory(server)
            last_model = variant.unet_name
            prompt = product.prompt
            api_graph = build_flux2_klein_graph(source_api, product, variant, prompt, seed, run_dir.name)
            api_path = api_dir / f"{product.product_id}_{variant.variant_id}_s{seed}.api.json"
            write_json(api_path, api_graph)
            record = JobRecord(
                product_id=product.product_id,
                label=product.label,
                variant_id=variant.variant_id,
                variant_title=variant.title,
                prompt=prompt,
                source_image=display_path(product.source_image),
                status="prepared",
                seed=seed,
                model=variant.unet_name,
                lora=variant.lora_name,
                lora_strength=variant.lora_strength if variant.lora_name else None,
                api_path=display_path(api_path),
            )
            if dry_run:
                record.status = "dry_run"
                records.append(record)
                continue
            print(f"[submit] {product.product_id} / {variant.variant_id} / seed={seed}")
            started = time.monotonic()
            try:
                prompt_id = client.submit_prompt(
                    api_graph,
                    client_id=f"agent:codex|workflow:2631_flux2_klein_matrix|run:{uuid.uuid4().hex[:8]}",
                    extra_data={
                        "agent": "codex",
                        "workflow_name": "2631_flux2_klein_matrix",
                        "source_workflow": display_path(workflow_path),
                        "track": "creative_campaign",
                        "product_id": product.product_id,
                        "variant_id": variant.variant_id,
                        "notes": (
                            f"model={variant.unet_name}; lora={variant.lora_name}; "
                            f"seed={seed}; steps={variant.steps}; prompt={prompt}"
                        ),
                    },
                )
                record.prompt_id = prompt_id
                if no_wait:
                    record.status = "queued"
                else:
                    result = client.wait_for_result(prompt_id)
                    record.status = result.status
                    if result.history:
                        record.outputs = collect_outputs(result.history, output_dir)
                        record.error = extract_history_error(result.history)
            except Exception as exc:
                record.status = "failed"
                record.error = str(exc)
            record.elapsed_seconds = round(time.monotonic() - started, 2)
            records.append(record)
            write_json(records_dir / f"{product.product_id}_{variant.variant_id}_s{seed}.json", record.__dict__)
            print(f"[done] {product.product_id} / {variant.variant_id}: {record.status}, outputs={len(record.outputs)}")
    write_json(run_dir / "job_records.json", [record.__dict__ for record in records])
    return records


def build_prompt_plan(run_dir: Path, products: list[ProductSpec]) -> None:
    write_json(
        run_dir / "prompt_plan.json",
        [
            {
                "product_id": item.product_id,
                "label": item.label,
                "source_image": display_path(item.source_image),
                "color_script": item.color_script,
                "creative_campaign_prompt": item.prompt,
            }
            for item in products
        ],
    )


def relative_image_src(path_value: str, html_path: Path) -> str:
    path = Path(path_value)
    if not path.is_absolute():
        path = REPO / path
    try:
        return path.resolve().relative_to(html_path.parent.resolve()).as_posix()
    except ValueError:
        return path.as_uri()


def write_html_report(
    run_dir: Path,
    products: list[ProductSpec],
    variants: list[VariantSpec],
    skipped: list[dict[str, str]],
    preflight: dict[str, Any],
    records: list[JobRecord],
    dry_run: bool,
) -> Path:
    report_path = run_dir / "report.html"
    by_product: dict[str, list[JobRecord]] = {}
    for record in records:
        by_product.setdefault(record.product_id, []).append(record)
    stats = preflight.get("system_stats", {})
    dev = (stats.get("devices") or [{}])[0] if isinstance(stats, dict) else {}
    css = """
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 28px; background: #f7f7f4; color: #202124; }
    h1, h2, h3 { margin: 0.8em 0 0.45em; }
    .meta, .note { color: #5f6368; line-height: 1.55; }
    .pill { display: inline-block; border: 1px solid #c9c9c3; border-radius: 999px; padding: 3px 9px; margin: 2px 4px 2px 0; background: white; font-size: 12px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .card { background: white; border: 1px solid #dddcd5; border-radius: 8px; padding: 14px; box-shadow: 0 1px 4px rgba(0,0,0,.04); }
    .card img { width: 100%; height: auto; border-radius: 6px; background: #eee; }
    .small { font-size: 12px; color: #5f6368; line-height: 1.45; word-break: break-word; }
    .prompt { white-space: pre-wrap; font-size: 13px; line-height: 1.5; background: #f2f2ee; padding: 10px; border-radius: 6px; }
    table { border-collapse: collapse; width: 100%; background: white; }
    th, td { border: 1px solid #dddcd5; padding: 8px; text-align: left; vertical-align: top; }
    th { background: #ecebe4; }
    .ok { color: #146c2e; font-weight: 600; }
    .bad { color: #a33b24; font-weight: 600; }
    .skip { color: #8a6500; font-weight: 600; }
    """
    parts: list[str] = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<title>26-5-31 TEST 工作流商品图矩阵报告</title>",
        f"<style>{css}</style></head><body>",
        "<h1>26-5-31 TEST 工作流商品图矩阵报告</h1>",
        f"<p class='meta'>生成时间：{html.escape(datetime.now().isoformat(timespec='seconds'))}</p>",
        f"<p class='meta'>运行目录：{html.escape(display_path(run_dir))}</p>",
        f"<p class='meta'>ComfyUI：{html.escape(str(stats.get('system', {}).get('comfyui_version')))} | GPU：{html.escape(str(dev.get('name')))} | dry_run={dry_run}</p>",
        "<h2>执行结论</h2>",
        "<p>本报告只使用 <code>agent-skills/comfyui/workflows/TEST/26-5-31</code> 下的工作流。当前可作为静态商品创意图生图主测路线的是 <code>image_flux2_klein_image_edit_4b_distilled.json</code>；脚本对同一工作流切换了可用 UNET 模型变体。LoRA 变体会预检，但本机目前没有被 ComfyUI 识别为兼容 Flux2/Klein 的 LoRA 时会跳过。</p>",
        "<h2>产品与提示词</h2>",
    ]
    for product in products:
        parts.append("<div class='card'>")
        parts.append(f"<h3>{html.escape(product.product_id)} - {html.escape(product.label)}</h3>")
        parts.append(f"<p class='small'>输入：{html.escape(display_path(product.source_image))}</p>")
        parts.append(f"<p class='small'>色彩脚本：{html.escape(product.color_script)}</p>")
        parts.append(f"<div class='prompt'>{html.escape(product.prompt)}</div>")
        parts.append("</div>")
    parts.append("<h2>模型 / LoRA 变体</h2><div>")
    for variant in variants:
        label = f"{variant.title} | {variant.unet_name}"
        if variant.lora_name:
            label += f" | LoRA {variant.lora_name} @ {variant.lora_strength}"
        parts.append(f"<span class='pill'>{html.escape(label)}</span>")
    parts.append("</div>")
    if skipped:
        parts.append("<h3>跳过的变体</h3><table><tr><th>变体</th><th>原因</th></tr>")
        for item in skipped:
            parts.append(f"<tr><td>{html.escape(item['title'])}</td><td>{html.escape(item['reason'])}</td></tr>")
        parts.append("</table>")
    parts.append("<h2>生成结果</h2>")
    for product in products:
        parts.append(f"<h3>{html.escape(product.product_id)} - {html.escape(product.label)}</h3>")
        parts.append("<div class='grid'>")
        for record in by_product.get(product.product_id, []):
            status_class = "ok" if record.status in {"success", "completed"} and record.outputs else ("skip" if record.status in {"queued", "dry_run"} else "bad")
            parts.append("<div class='card'>")
            parts.append(f"<h3>{html.escape(record.variant_title)}</h3>")
            parts.append(f"<p class='{status_class}'>状态：{html.escape(record.status)}</p>")
            if record.outputs:
                for output in record.outputs:
                    src = relative_image_src(output, report_path)
                    parts.append(f"<a href='{html.escape(src)}'><img src='{html.escape(src)}' alt='{html.escape(record.product_id)} {html.escape(record.variant_id)}'></a>")
            else:
                parts.append("<p class='small'>无输出图。</p>")
            parts.append(f"<p class='small'>model: {html.escape(record.model)}</p>")
            parts.append(f"<p class='small'>lora: {html.escape(str(record.lora or 'none'))}</p>")
            parts.append(f"<p class='small'>seed: {record.seed}; elapsed: {html.escape(str(record.elapsed_seconds))}</p>")
            if record.error:
                parts.append(f"<p class='bad'>error: {html.escape(record.error)}</p>")
            parts.append("</div>")
        parts.append("</div>")
    parts.append("<h2>TEST 文件夹预检</h2><table><tr><th>workflow</th><th>status</th><th>role</th><th>missing nodes</th><th>notes</th></tr>")
    for item in preflight.get("workflows", []):
        parts.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('workflow')))}</td>"
            f"<td>{html.escape(str(item.get('status')))}</td>"
            f"<td>{html.escape(str(item.get('matrix_role', '')))}</td>"
            f"<td>{html.escape(str(item.get('missing_node_types', [])))}</td>"
            f"<td>{html.escape(str(item.get('notes', item.get('error', ''))))}</td>"
            "</tr>"
        )
    parts.append("</table>")
    parts.append("<h2>后续建议</h2><p>如果 Flux2 Klein 的想象力仍不够，下一步不要继续在同一 prompt 上微调，应优先补可运行的 Qwen Image Edit 主模型/Fusion LoRA，或切换到本地 Flux Kontext full 与 SDXL + LEGO/Product LoRA 矩阵。该 HTML 当前用于比较 TEST 文件夹内可运行工作流的模型变体。</p>")
    parts.append("</body></html>")
    report_path.write_text("\n".join(parts), encoding="utf-8")
    return report_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run 26-5-31 TEST workflow model/LoRA matrix and write HTML report.")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--input-dir", default=str(DEFAULT_PRODUCT_INPUT_DIR))
    parser.add_argument("--batch-id", default="aliexpress_lego_5_20260531_test2631_matrix")
    parser.add_argument("--max-products", type=int, default=5)
    parser.add_argument("--base-seed", type=int, default=263100)
    parser.add_argument("--include-heavy", action="store_true", help="Also run heavy model variants such as Flux2 Klein 9B.")
    parser.add_argument("--no-auto-start", action="store_true", help="Do not start local ComfyUI when the server is offline.")
    parser.add_argument("--startup-timeout", type=int, default=420, help="Seconds to wait for auto-started ComfyUI.")
    parser.add_argument("--comfy-python", default=str(COMFY_PYTHON), help="Python executable used to auto-start ComfyUI.")
    parser.add_argument("--comfy-main", default=str(COMFY_MAIN), help="ComfyUI main.py used to auto-start ComfyUI.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-wait", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = RUNTIME_ROOT / args.batch_id
    run_dir.mkdir(parents=True, exist_ok=True)
    print(f"[run] {display_path(run_dir)}")
    launch_record = ensure_comfy_server(
        server=args.server,
        run_dir=run_dir,
        no_auto_start=args.no_auto_start,
        startup_timeout=args.startup_timeout,
        comfy_python=Path(args.comfy_python),
        comfy_main=Path(args.comfy_main),
    )
    write_json(run_dir / "comfyui_launch.json", launch_record)
    products = pick_products(Path(args.input_dir), max_products=args.max_products)
    build_prompt_plan(run_dir, products)
    preflight, object_info = preflight_workflows(args.server, run_dir)
    variants = build_variants(object_info, include_heavy=args.include_heavy)
    skipped = skipped_variants(object_info, include_heavy=args.include_heavy)
    if not variants:
        raise RuntimeError("No runnable model variants found for image_flux2_klein_image_edit_4b_distilled.json.")
    write_json(run_dir / "variant_plan.json", [variant.__dict__ for variant in variants])
    write_json(run_dir / "skipped_variants.json", skipped)
    records = run_matrix(
        server=args.server,
        run_dir=run_dir,
        products=products,
        variants=variants,
        dry_run=args.dry_run,
        no_wait=args.no_wait,
        base_seed=args.base_seed,
    )
    report = write_html_report(run_dir, products, variants, skipped, preflight, records, args.dry_run)
    print(f"[report] {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
