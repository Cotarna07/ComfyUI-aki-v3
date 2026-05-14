# manga-anime-pipeline

这是《私有化漫画转动漫多模块工作流设计方案》的外部 pipeline 原型工程，当前目标覆盖：输入漫画图片 -> 长图切片 -> OCR provider -> OCR-based Dialogue provider -> 轻量检测 provider -> Qwen3-VL director -> shot manifest -> 门禁报告 -> ComfyUI API 批量投递框架。

当前已经具备 Stage 3A / Stage 4A / Stage 5 / Stage 6 的门禁脚本和 provider 抽象：PaddleOCR、规则型 OCR-based Dialogue、轻量检测、Qwen3-VL director（local / Ollama / OpenAI 兼容模式）和 ComfyUI batch submitter 都已经有代码入口。仍未完成的是：Grounded-SAM-2 真实检测 provider、Manga Image Translator provider、`configs/comfy_workflows/` 下的真实 ComfyUI API 工作流模板，以及可直接安装到 `ComfyUI/custom_nodes/` 的自建节点包。

一句话定位：本项目当前可用于验证“漫画 -> 结构化素材包 -> shot manifest -> ComfyUI 路由”的工程闭环，但还不是完整生产级漫画转动漫系统。

## 环境要求

- Windows PowerShell
- Python 3.10+，本工作区优先使用 `d:\ComfyUI-aki-v3\.venv\Scripts\python.exe`
- Pillow，用于读取和切片漫画图片

安装依赖：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Stage 2 OCR 可选依赖单独安装，不强制进入基础依赖：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -U pip
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt
```

`requirements-ocr.txt` 包含 CPU 优先的 `paddlepaddle` 和 `paddleocr`。PaddleOCR 3.x 需要同时安装 `paddleocr` 包和 PaddlePaddle 推理引擎；如果当前 Python 版本没有可用 wheel，建议单独建立兼容的 Python 3.10/3.11 OCR 虚拟环境。GPU 版 PaddlePaddle / CUDA 适配不在本阶段处理。

## 准备输入图片

章节输入是一个 JSON 文件，包含 `series_id`、`chapter_id` 和 `pages`。每个页面必须提供 `page_id`、`image_path`、`width`、`height`。

可以先生成内置示例：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\create_example_input.py
```

示例输入会写入：

- `runtime/input/example_page.png`
- `runtime/input/example_chapter.json`

示例 JSON：

```json
{
  "series_id": "example_series",
  "chapter_id": "ep001",
  "input_type": "webtoon",
  "pages": [
    {
      "page_id": "p001",
      "image_path": "runtime/input/example_page.png",
      "width": 720,
      "height": 2200
    }
  ]
}
```

## 运行 stage1

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\run_stage1.py --input runtime\input\example_chapter.json
```

使用 PaddleOCR provider：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\run_stage1.py --input runtime\input\example_chapter.json --config configs\stage1.ocr.paddle.json --force
```

使用 PaddleOCR + OCR-based Dialogue provider：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\run_stage1.py --input runtime\input\example_chapter.json --config configs\stage1.ocr.dialogue.json --force
```

运行自动验收并生成 JSON/Markdown 报告：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\run_acceptance.py --input runtime\input\example_chapter.json --config configs\stage1.ocr.dialogue.json --force
```

可选参数：

- `--window-height 1200`：长图窗口高度
- `--overlap 160`：相邻窗口重叠像素
- `--runtime-root runtime`：运行产物根目录
- `--config configs/stage1.default.json`：默认配置
- `--force`：强制重建已有输出

复跑策略：默认会复用已经存在且通过校验的 `window_manifest.json`、`structured_packets.json` 和 `shot_manifest.json`，不会覆盖这些产物；添加 `--force` 后会删除对应章节的 stage 输出并重新生成。若检测到不完整输出目录但缺少稳定 manifest，会失败并写出错误状态报告。

默认 provider 配置如下：

```json
{
  "providers": {
    "ocr": "mock",
    "dialogue": "mock",
    "detection": "mock",
    "director": "mock"
  }
}
```

PaddleOCR 配置示例见 `configs/stage1.ocr.paddle.json`：

```json
{
  "providers": {
    "ocr": "paddleocr",
    "dialogue": "mock",
    "detection": "mock",
    "director": "mock"
  }
}
```

PaddleOCR + OCR-based Dialogue 配置示例见 `configs/stage1.ocr.dialogue.json`：

```json
{
  "providers": {
    "ocr": "paddleocr",
    "dialogue": "ocr_based",
    "detection": "mock",
    "director": "mock"
  },
  "dialogue": {
    "ocr_based": {
      "min_confidence": 0.3,
      "max_merge_distance": 48,
      "min_text_length": 1
    }
  }
}
```

如果未安装 OCR 依赖，选择 `paddleocr` 后会在 OCR 阶段抛出友好的 `RuntimeError`，提示运行 `python -m pip install -r requirements-ocr.txt`，而不是在项目 import 阶段崩溃。

## 输出文件

默认输出在项目内 `runtime/` 下：

- `runtime/windows/<series_id>/<chapter_id>/window_manifest.json`
- `runtime/windows/<series_id>/<chapter_id>/<page_id>/w0000.png`
- `runtime/structured/<series_id>/<chapter_id>/packets/<window_id>.json`
- `runtime/structured/<series_id>/<chapter_id>/structured_packets.json`
- `runtime/manifests/<series_id>/<chapter_id>/shot_manifest.json`
- `runtime/qc/<series_id>/<chapter_id>/stage1_status.json`
- `runtime/qc/<series_id>/<chapter_id>/acceptance_report.json`
- `runtime/qc/<series_id>/<chapter_id>/acceptance_report.md`

每个阶段都会写入 task status，字段包含 `task_id`、`stage`、`status`、`started_at`、`finished_at`、`input_refs`、`output_refs`、`error_message`、`retry_count`。

## 当前模块

- `pipeline/ingest/chapter.py`：读取章节 manifest，并校验图片尺寸。
- `pipeline/ingest/slicer.py`：按窗口高度和 overlap 切片，保留 `source_page`、`source_box`、窗口尺寸和重叠关系。
- `pipeline/manifest/integrity.py`：校验 window、structured packet、shot manifest 之间的 ID、坐标和链接完整性。
- `pipeline/ocr/mock.py`：mock OCR，输出 `ocr_blocks`、`reading_order`、`layout_blocks`。
- `pipeline/ocr/base.py` 与 `pipeline/ocr/provider_factory.py`：OCR provider 抽象与加载。
- `pipeline/ocr/paddle_provider.py`：PaddleOCR provider，延迟 import `paddleocr`，把真实 OCR 输出统一规范为 `ocr_blocks`、`reading_order`、`layout_blocks`。
- `pipeline/dialogue/mock.py`：mock 漫画对白，输出 `dialogue_blocks`、`bubble_boxes`、`sfx_blocks`、`cleaned_text_candidates`。
- `pipeline/dialogue/base.py` 与 `pipeline/dialogue/provider_factory.py`：对白 provider 抽象与加载。
- `pipeline/dialogue/ocr_based_provider.py`：规则型 OCR-based Dialogue provider，只基于 OCR 结果整理对白、拟声词和 cleaned text candidates。
- `pipeline/detection/mock.py`：mock 检测与裁切候选，输出 `object_boxes`、`object_masks`、`crop_candidates`、`focus_subjects`、`scene_density`。
- `pipeline/detection/base.py` 与 `pipeline/detection/provider_factory.py`：检测 provider 抽象与加载。
- `pipeline/detection/lightweight_provider.py`：规则型轻量检测 provider，基于图像密度、中心构图和文本避让生成 `crop_candidates`；它是 Grounded-SAM-2 接入前的流程占位，不等价于真实主体分割。
- `pipeline/manifest/packets.py`：合并结构化素材包并逐 window 落盘。
- `pipeline/director/mock.py`：mock director，输出符合 schema 的 shot 草稿。
- `pipeline/director/base.py`、`pipeline/director/context.py` 与 `pipeline/director/provider_factory.py`：导演 provider 抽象、上下文摘要与加载。
- `pipeline/director/qwen3vl_provider.py`：Qwen3-VL director provider，支持 local、Ollama、OpenAI-compatible 三种模式，负责把结构化素材包生成符合 schema 的 shot 草稿。
- `pipeline/manifest/shot_manifest.py`：写入 shot manifest，并在写入前校验 JSON schema。
- `pipeline/comfy/client.py`、`pipeline/comfy/workflow_router.py`、`pipeline/comfy/submitter.py`：ComfyUI HTTP 客户端、workflow_route 到模板路径的路由器、批量提交器。
- `pipeline/qc/acceptance.py` 与 `pipeline/qc/report.py`：自动验收规则、质量统计、JSON/Markdown 报告。
- `pipeline/qc/detection_acceptance.py`、`pipeline/qc/director_acceptance.py`、`pipeline/qc/comfy_acceptance.py`：Stage 4A、Stage 5、Stage 6 的门禁验收逻辑。
- `pipeline/stage1.py`：串联第一阶段闭环。
- `scripts/run_acceptance.py`：运行 pipeline 并输出 acceptance report。
- `scripts/run_stage3a_gate.py`、`scripts/run_stage4a_gate.py`、`scripts/run_stage5_gate.py`、`scripts/run_stage6_gate.py`：分阶段门禁脚本。
- `scripts/run_all_gates.py`：按 next_stage 规则串联全部门禁。
- `scripts/run_comfy_batch.py`：独立执行 ComfyUI 批量投递。

## schema 校验

JSON schema 定义在 `pipeline/common/schemas.py`，校验器在 `pipeline/common/validation.py`。`workflow_route` 被限制为：

- `establish_scene`
- `dialogue_light_motion`
- `dialogue_heavy_expression`
- `action_performance`
- `transition_atmosphere`
- `repair_only`
- `skip`

manifest 写入前必须通过 schema 校验和完整性校验；如果字段缺失、类型错误、坐标越界、重叠关系错误、ID 无法追溯或路由非法，命令会失败并输出明确错误。失败时会写出状态报告，包含失败阶段的 `error_message`。

## 替换 mock OCR

真实 OCR 接入点在 `pipeline/ocr/`。当前已经提供 PaddleOCR provider；后续 Surya 或 PaddleOCR-VL 也应新增 provider 类继承 `OCRProvider`，保持 `analyze(window_packet) -> dict` 接口不变，并返回：

- `ocr_blocks`
- `reading_order`
- `layout_blocks`

然后在 `pipeline/ocr/provider_factory.py` 中注册 provider 名称，并在 `configs/stage1.default.json` 或自定义配置中选择。真实 provider 不应改变 structured packet 的字段名称。

PaddleOCR 输出会被统一转换成：

```json
{
  "ocr_blocks": [
    {
      "block_id": "ep001_p001_w0000_ocr_0000",
      "text": "识别到的文字",
      "box": [10, 12, 70, 24],
      "confidence": 0.95,
      "language": "unknown",
      "provider": "paddleocr"
    }
  ],
  "reading_order": ["ep001_p001_w0000_ocr_0000"],
  "layout_blocks": []
}
```

没有识别到文字时会稳定返回空数组字段：`ocr_blocks: []`、`reading_order: []`、`layout_blocks: []`。

## 替换 mock dialogue

当前提供 `ocr_based` provider，不接 Manga Image Translator，不接新模型，只基于 OCR 结果做规则整理。Manga Image Translator 后续接入点仍在 `pipeline/dialogue/`。新增 provider 类继承 `DialogueProvider`，保持 `analyze(window_packet, ocr_result=None) -> dict` 接口，返回：

- `dialogue_blocks`
- `bubble_boxes`
- `sfx_blocks`
- `cleaned_text_candidates`

`ocr_based` 支持配置：

- `min_confidence`
- `max_merge_distance`
- `min_text_length`

provider factory 支持名称：`mock`、`mock_dialogue`、`ocr_based`、`ocr-based`、`ocrbased`。

## 自动验收

`scripts/run_acceptance.py` 会先运行 pipeline，再读取 window manifest、structured packets、shot manifest 和最新 status report，输出：

- `runtime/qc/<series_id>/<chapter_id>/acceptance_report.json`
- `runtime/qc/<series_id>/<chapter_id>/acceptance_report.md`

验收结果分为：

- `pass`：OCR 和 dialogue 已按目标 provider 产出有效结构，且无 fail 级错误。
- `warning`：无 fail 错误，但存在低置信度、部分空窗口、mock detection/director 或复用输出等提醒。
- `fail`：pipeline 失败、产物缺失、schema/integrity/status 错误、配置要求真实 provider 但产物仍是 mock，或 OCR/dialogue 全空。

## Detection provider 路线

当前已有两个 detection provider：

- `mock`：仅用于最早期 schema 和流程测试。
- `lightweight`：规则型轻量检测，基于中心裁切、文本避让和图像边缘密度生成 `crop_candidates`。

`lightweight` 可以验证 Stage 4A 流程，但不能满足最终需求。它不会真正识别人、脸、手、道具或背景主体，也不会输出真实 mask；因此它只能作为 Grounded-SAM-2 接入前的占位层。

### Grounded-SAM-2 provider 应该怎么做

Grounded-SAM-2 接入点仍在 `pipeline/detection/`。新增 provider 类建议命名为 `grounded_sam2_provider.py`，继承 `DetectionProvider`，保持 `analyze(window_packet) -> dict` 接口，并返回：

- `object_boxes`
- `object_masks`
- `crop_candidates`
- `focus_subjects`
- `scene_density`

推荐实现步骤：

1. 新增 `pipeline/detection/grounded_sam2_provider.py`。
2. 在 provider 内部加载 Grounding DINO / Grounded-SAM-2 / SAM2 推理入口，重依赖必须延迟 import，避免项目启动阶段直接崩溃。
3. 给 provider 增加 `check_runtime()`，检查权重路径、模型配置、CUDA 或 CPU fallback 是否可用。
4. 输入使用 `window_packet["window_image_path"]` 或 `window_packet["image_path"]`。
5. 用文本提示检测漫画镜头所需主体，例如 `person, face, hand, weapon, phone, vehicle, room, background object`。
6. 把检测框统一映射成 `object_boxes`，字段至少包含 `object_id`、`label`、`box`、`confidence`、`provider`。
7. 把 SAM2 mask 以文件路径或 RLE 引用写入 `object_masks`，不要直接把巨大 mask 数组塞进 JSON。
8. 根据主体框、mask、OCR 文本框和画面比例生成 `crop_candidates`，每个候选包含 `crop_id`、`box`、`reason`、`score`、`provider`。
9. 在 `pipeline/detection/provider_factory.py` 注册 `grounded_sam2`、`grounded-sam2`、`gsam2` 等别名。
10. 新增 `configs/stage1.ocr.dialogue.gsam2.json`，让 Stage 4A 可以用真实 provider 跑门禁。

推荐配置形态：

```json
{
  "providers": {
    "ocr": "paddleocr",
    "dialogue": "ocr_based",
    "detection": "grounded_sam2",
    "director": "mock"
  },
  "detection": {
    "grounded_sam2": {
      "model_root": "runtime/downloads/grounded_sam2",
      "device": "cuda",
      "box_threshold": 0.3,
      "text_threshold": 0.25,
      "dump_masks": true,
      "prompts": ["person", "face", "hand", "weapon", "phone", "vehicle", "room", "background object"]
    }
  }
}
```

真实 Grounded-SAM-2 接入后，Stage 4A 的验收目标应从“有 crop_candidates”升级为：

1. 至少部分窗口存在非 mock 的 `object_boxes`。
2. 高分窗口存在可追溯的 `crop_candidates`。
3. mask 文件或 mask 引用能在 runtime 下找到。
4. crop 不越界，并且能映射回原图 `source_box`。
5. provider_summary 中 detection 必须为 `grounded_sam2`，不能再是 `lightweight`。

## Qwen3-VL director 与 Ollama 配置

Qwen3-VL 接入点在 `pipeline/director/`。当前 `pipeline/director/qwen3vl_provider.py` 已支持三种模式：

- `local`：直接用 transformers 加载本地权重目录。
- `ollama`：调用 Ollama `/api/chat`，支持把窗口图转成 base64 image 输入。
- `openai_compatible`：调用 LM Studio 或其他 OpenAI 兼容 API。

当前推荐先使用 Ollama 模式，因为它把模型服务和 pipeline 解耦，不会在当前 Python 进程里直接吃满显存。

### Ollama 模式配置

`configs/stage1.full.director.json` 当前应保持类似配置：

```json
{
  "providers": {
    "ocr": "paddleocr",
    "dialogue": "ocr_based",
    "detection": "lightweight",
    "director": "qwen3vl"
  },
  "director": {
    "qwen3vl": {
      "mode": "ollama",
      "api_base": "http://127.0.0.1:11434",
      "api_model": "huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M",
      "max_retries": 2,
      "require_json": true,
      "timeout_seconds": 120
    }
  }
}
```

使用前必须确认：

```powershell
ollama list
Invoke-RestMethod http://127.0.0.1:11434/api/tags
```

`api_model` 必须和 Ollama 返回的模型名完全一致。已经通过 `huggingface-cli download` 下载到本地目录的 Hugging Face 权重，不会自动成为 Ollama 模型；如果继续走 Ollama，需要先按 Ollama 的方式创建或导入模型。若要直接使用下载目录，则应改用 `mode=local` 并配置 `model_path`。

Qwen3-VL provider 会要求模型输出严格 JSON，并在落盘前经过 `SHOT_SCHEMA` 校验。真实 director 应继续输出 `pipeline/common/schemas.py` 中 `SHOT_SCHEMA` 要求的所有字段。

替换后仍需调用 `build_shot_manifest()`，让最终 manifest 在落盘前通过 schema 校验。

## 测试

当前测试使用标准库 `unittest`：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m unittest discover -s tests
```

PaddleOCR smoke test 在未安装 `paddleocr` 时会自动 skip，不影响普通单测通过。

也可以做语法检查：

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m py_compile scripts\run_stage1.py scripts\create_example_input.py pipeline\stage1.py
```

## 当前能力边界

已经具备：

- 长图切片、窗口 manifest、结构化 packet 和 shot manifest 落盘。
- PaddleOCR provider 和 OCR-based Dialogue provider。
- lightweight detection provider，可用于流程验收和临时裁切候选。
- Qwen3-VL director provider，支持 local、Ollama、OpenAI-compatible 三种模式。
- Stage 3A / 4A / 5 / 6 门禁脚本和总门禁编排器。
- ComfyUI API batch submitter 和 workflow_route 模板路由器。

仍需补齐：

- Manga Image Translator provider：替换或增强当前 OCR-based Dialogue。
- Grounded-SAM-2 provider：替换 lightweight detection，输出真实主体框、mask 和智能裁切候选。
- `configs/comfy_workflows/`：放置各 route 对应的 ComfyUI API workflow JSON。
- ComfyUI 自建节点包：让分析图 / 导演图能在 ComfyUI 画布中拖节点搭建。
- Prompt 注入和工作流模板覆写逻辑：当前 submitter 只提交模板 JSON，还没有根据 shot manifest 自动改写模板里的 prompt、输入图、seed 和输出名。
- 人工审核台、失败重试策略、镜头质检模型、音频 / 口型 / BGM 后期链。


## Stage 3A / 4A / 5 / 6 门禁体系

工程已经搭好从 OCR 到 ComfyUI 批量投递前后的完整闭环。每个 gate 都会输出独立 JSON + Markdown 报告，并由 `scripts/run_all_gates.py` 统一编排。

### Provider 切换表

| 角色 | 配置文件 | provider 名 | 真实依赖 |
|------|----------|-------------|----------|
| OCR | `configs/stage1.ocr.dialogue.json` 等 | `paddleocr` / `paddle` | `requirements-ocr.txt` |
| Dialogue | 同上 | `ocr_based` | 无外部依赖 |
| Detection（轻量） | `configs/stage1.ocr.dialogue.detect.json` | `lightweight` / `light` / `rule_based` | `requirements-detection.txt`（Pillow + opencv-python-headless） |
| Director（Qwen3-VL） | `configs/stage1.full.director.json` | `qwen3vl` / `qwen3-vl` / `qwen_vl` | 三选一：本地 `transformers` 权重目录，或 Ollama API，或 LM Studio / 其他 OpenAI 兼容 API |
| ComfyUI 投递 | `configs/comfy.default.json` | — | ComfyUI 服务（默认 `http://127.0.0.1:8188`）+ `configs/comfy_workflows/*.json` 模板 |

切换只需修改对应配置文件里的 `provider` 字段；mock provider 不会让任何 gate 通过 `next_stage_allowed=true`。

### 各阶段安装命令

```powershell
# OCR (Stage 2 / 3A)
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements-ocr.txt

# 轻量 Detection (Stage 3 / 4A)
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements-detection.txt

# Qwen3-VL Director (Stage 4 / 5)
# local 模式才需要 transformers / torch 与 Hugging Face 权重目录
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements-director.txt

# Ollama 模式：确保服务已启动并已拉取目标模型
ollama list

# LM Studio / OpenAI 兼容模式：确保服务已启动并可访问 /v1/models

# ComfyUI 批量投递 (Stage 6)
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe -m pip install -r requirements-comfy.txt
# 同时启动 ComfyUI 服务 http://127.0.0.1:8188，并准备好 configs/comfy_workflows/*.json 工作流模板
```

### 门禁脚本

| Gate | 脚本 | 输入 | 输出 | blocked | fail |
|------|------|------|------|---------|------|
| Stage 3A | `scripts/run_stage3a_gate.py` | OCR 配置 | `runtime/qc/<series>/<chapter>/stage3a_gate_report.{json,md}` | paddleocr/paddle 缺失 | provider 真实运行但 acceptance 失败 |
| Stage 4A | `scripts/run_stage4a_gate.py` | OCR + Detection 配置 | `stage4a_gate_report.{json,md}` | Pillow/Detection 依赖缺失 | mock detection 冒充 lightweight、crops 越界等 |
| Stage 5 | `scripts/run_stage5_gate.py` | 上面三份配置 | `stage5_gate_report.{json,md}` | local 模式缺权重，或 Ollama / LM Studio / OpenAI 兼容服务不可达，或目标模型未加载 | workflow_route 非法、空 prompt、score 越界 |
| Stage 6 | `scripts/run_stage6_gate.py` + `scripts/run_comfy_batch.py` | 四份配置 | `stage6_gate_report.{json,md}` + `comfy_tasks.json` | ComfyUI 服务不可达 | 工作流模板缺失、提交失败 |
| 全部 | `scripts/run_all_gates.py` | 四份配置 | `all_gates_report.{json,md}` | 上游任一阶段 blocked，下游级联 blocked | 任一阶段 fail |

## Stage 6 ComfyUI 工作流模板设计

Stage 6 的目标不是重新分析漫画，而是消费 Stage 5 生成的 `shot_manifest.json`，把每条 shot 按 `workflow_route` 投递到对应的 ComfyUI API 工作流。

当前 `configs/comfy.default.json` 已经定义 route 到模板文件的映射，但 `configs/comfy_workflows/` 目录还没有实际 API workflow JSON。因此 Stage 6 目前会因为模板缺失而 fail，这是预期的 honest fail，不是 ComfyUI 生成链已经可用。

### 必须准备的模板文件

按默认配置，需要准备这些文件：

```text
configs/comfy_workflows/
  establish_scene.json
  dialogue_light_motion.json
  dialogue_heavy_expression.json
  action_performance.json
  transition_atmosphere.json
  repair_only.json
```

`skip` route 不需要模板。

这些文件必须是 ComfyUI 导出的 API workflow JSON，不是 UI workflow JSON。建议先在 ComfyUI 页面手工调通，再导出 API 格式，最后放入上述目录。

### workflow_route 到工作流的职责

| workflow_route | 目标 | 推荐 ComfyUI 主链 | 主要输入 | 主要输出 |
| --- | --- | --- | --- | --- |
| `establish_scene` | 场景建立、环境展示、转场开场 | LTX I2V/T2V 或 Wan 2.2 T2V/I2V | `positive_prompt`、`negative_prompt`、可选 crop 图 | 3-6 秒场景镜头 |
| `dialogue_light_motion` | 对白、反应、轻微表情和镜头运动 | Wan 2.2 I2V 或 LTX I2V | crop 图、角色/画风锚点、prompt | 轻运动对白镜头 |
| `dialogue_heavy_expression` | 强表情对白、情绪爆发、后续口型链入口 | WanAnimate 或后续 talking/lipsync 工作流 | 角色参考图、crop 图、prompt、可选音频 | 表情更强的对白镜头 |
| `action_performance` | 动作、肢体、表演镜头 | WanAnimate 优先，必要时接 pose/动作参考 | 角色参考、动作参考或 pose、prompt | 动作镜头 |
| `transition_atmosphere` | 氛围转场、空镜、情绪铺垫 | Wan 2.2 T2V / LTX T2V | prompt、风格锚点 | 转场或空镜 |
| `repair_only` | 修补、局部重绘、延长、遮罩修复 | VACE | 待修视频/图、mask、修补 prompt | 修补后镜头 |
| `skip` | 不生成 | 无 | 无 | 无 |

### 模板交接字段

每个非 skip 模板都必须能接收或被覆写以下字段：

- `shot_id`：用于输出文件命名和回溯。
- `positive_prompt`：来自 shot manifest。
- `negative_prompt`：来自 shot manifest。
- `workflow_route`：用于选择模板。
- `source_ranges` / `crop_recommendation`：用于定位源漫画区域。
- `style_anchor`：用于选择角色/风格参考。
- `seed`：如果 manifest 没有，可由路由器生成并写入 notes。
- `output_prefix`：建议包含 `series_id`、`chapter_id`、`shot_id`。

当前 `submitter.py` 只会提交模板 JSON，并把 `shot_id` 写入 `extra_data.notes`；还没有自动覆写模板里的 prompt、输入图、seed 和输出名。要让 Stage 6 真正进入生产态，下一步需要新增“模板注入层”。

### 推荐新增模板注入层

建议新增模块：

```text
pipeline/comfy/template_patcher.py
```

职责：

1. 读取 workflow template JSON。
2. 根据 route 对应的 mapping，把 shot manifest 字段写入指定节点输入。
3. 覆写 prompt、negative_prompt、输入图、seed、输出前缀。
4. 返回可直接提交给 `/prompt` 的 API workflow。

推荐为每张模板准备一个 mapping 文件：

```text
configs/comfy_workflows/dialogue_light_motion.mapping.json
```

示例形态：

```json
{
  "positive_prompt": {"node_id": "12", "input": "text"},
  "negative_prompt": {"node_id": "13", "input": "text"},
  "input_image": {"node_id": "4", "input": "image"},
  "seed": {"node_id": "20", "input": "seed"},
  "output_prefix": {"node_id": "45", "input": "filename_prefix"}
}
```

后续 `submitter.py` 应从“直接提交模板”升级为：

1. `WorkflowRouter` 找到 route 对应模板。
2. `template_patcher` 根据 shot 和 mapping 覆写模板。
3. `ComfyClient.submit_prompt()` 提交已经注入参数的 workflow。
4. `comfy_tasks.json` 记录 `shot_id`、`workflow_route`、`prompt_id`、输出文件和重试次数。

### 推荐的实际搭建顺序

1. 先只准备 `dialogue_light_motion.json`，用 Wan 2.2 I2V 或 LTX I2V 做最小镜头生成。
2. 再准备 `establish_scene.json` 和 `transition_atmosphere.json`，覆盖场景和转场。
3. 再准备 `repair_only.json`，接 VACE 修补链。
4. 最后再接 `dialogue_heavy_expression.json` 和 `action_performance.json`，引入 WanAnimate、口型和动作参考。

这样能先让 Stage 6 跑通一条低风险视频链，再逐步提高镜头类型覆盖率。

## ComfyUI 自建节点包路线

当前项目还没有 `comfyui_nodes/` 或可直接安装到 `ComfyUI/custom_nodes/` 的节点包。现有能力都在 `pipeline/` 和 `scripts/` 里，适合作为自建节点的后端逻辑。

### 推荐目录结构

后续建议在项目内新增：

```text
comfyui_nodes/
  manga_anime_pipeline/
    __init__.py
    nodes.py
    adapters/
      path_utils.py
      json_io.py
      image_io.py
    README.md
```

开发稳定后，再把 `comfyui_nodes/manga_anime_pipeline/` 复制或软链接到：

```text
D:/ComfyUI-aki-v3/ComfyUI/custom_nodes/manga_anime_pipeline
```

注意：安装或更新 ComfyUI 自建节点通常需要重启 ComfyUI。本机当前如果正在跑生成工作流，不要现在重启。

### 第一批建议节点

| 节点名 | 后端复用模块 | 输入 | 输出 | 用途 |
| --- | --- | --- | --- | --- |
| `MangaChapterLoad` | `pipeline/ingest/chapter.py` | chapter JSON 路径 | chapter 对象 | 读取章节输入 |
| `MangaLongImageSlice` | `pipeline/ingest/slicer.py` | chapter、window_height、overlap | window_manifest 路径 | 长图切片 |
| `MangaOCRAnalyze` | `pipeline/ocr/*` | window packet、provider config | OCR result JSON | OCR 和阅读顺序 |
| `MangaDialogueAnalyze` | `pipeline/dialogue/*` | window packet、OCR result | dialogue result JSON | 对白和气泡信息 |
| `MangaDetectCandidates` | `pipeline/detection/*` | window packet、OCR/dialogue result | detection result JSON | 主体框、mask、裁切候选 |
| `MangaBuildStructuredPacket` | `pipeline/manifest/packets.py` | OCR、dialogue、detection | structured packet JSON | 合并结构化素材包 |
| `MangaDirectorDraft` | `pipeline/director/*` | structured packet、上下文摘要 | shot JSON | Qwen3-VL 生成导演草稿 |
| `MangaManifestWrite` | `pipeline/manifest/shot_manifest.py` | shots、packet refs | shot_manifest 路径 | manifest 落盘与校验 |
| `MangaManifestReadShot` | 新增轻量节点 | manifest 路径、shot_id 或 index | 单条 shot | 生成图读取镜头任务 |
| `MangaPromptInject` | 后续 `template_patcher.py` | shot、workflow template | patched workflow | 给生成模板注入 prompt / seed / 输入图 |

### 节点设计原则

1. 节点只封装单步能力，不把整章批处理塞进一个节点。
2. 节点输出优先是 JSON 路径或结构化对象，便于复用、缓存和人工检查。
3. 重模型依赖必须延迟加载，不能在 ComfyUI 启动时就强制 import Grounded-SAM-2、PaddleOCR 或 Qwen3-VL。
4. 每个节点要尽量支持 `runtime_root`，避免运行产物散落到 ComfyUI 根目录。
5. 节点内遇到缺模型、缺依赖、服务不可达时，应抛出清晰错误，不要静默返回空结果。

### 推荐的 ComfyUI 分图方式

不要把所有节点放在一张大图里。建议拆成：

1. 漫画分析图：`MangaChapterLoad` -> `MangaLongImageSlice` -> OCR / Dialogue / Detection -> Structured Packet。
2. 导演草稿图：Structured Packet -> `MangaDirectorDraft` -> `MangaManifestWrite`。
3. 单镜头生成图：`MangaManifestReadShot` -> `MangaPromptInject` -> Wan / LTX / VACE / WanAnimate 模板。
4. 修补图：读取失败镜头或待修视频 -> VACE -> 输出修补结果。

这样可以让 ComfyUI 负责可视化调试和单镜头生成，让外部编排器负责整章循环、补跑和归档。

### 自建节点与外部 pipeline 的关系

自建节点不是替代 `pipeline/`，而是调用 `pipeline/` 的薄包装层。推荐保持：

1. `pipeline/` 保存核心逻辑和单元测试。
2. `comfyui_nodes/` 只做 ComfyUI 输入输出适配。
3. `scripts/` 继续负责批处理、门禁和外部编排。

这样后续既能在 ComfyUI 画布中拖节点调试，也能用命令行批量跑整章。

### 一键运行

只有在 PaddleOCR、Qwen3-VL Ollama 服务、ComfyUI 服务和 `configs/comfy_workflows/*.json` 模板都准备好之后，才建议运行全部 gate。当前如果 ComfyUI 正在跑其他工作流，或模板目录还没准备好，建议先只跑 Stage 3A / 4A / 5，不要运行 Stage 6。

```powershell
cd d:\ComfyUI-aki-v3\agent-projects\manga-anime-pipeline
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe scripts\run_all_gates.py --input runtime\input\example_chapter.json --force
```

orchestrator 严格遵守 next_stage 决策：上一阶段未通过时直接跳过下游并写入 blocked 报告；不会用 mock provider 让 gate 误判为 pass。

### blocked vs fail 常见原因

- `blocked`：真实依赖缺失（PaddleOCR、Pillow/opencv、本地 Qwen3-VL 权重目录、Ollama / LM Studio / OpenAI 兼容服务、ComfyUI 服务、ComfyUI 工作流模板）。处理：按 `next_action` 安装依赖或准备资源后重跑。
- `fail`：依赖齐全但产出不合格（mock 冒充真实 provider、crop 越界、workflow_route 非法、空 prompt、ComfyUI 提交失败）。处理：根据 `errors` 字段定位并修正配置或 provider 输出。

### 用户必须自行准备的外部资源

1. PaddleOCR：`pip install -r requirements-ocr.txt` 成功，并确认 `paddleocr` 与 `paddlepaddle` 可导入。
2. Qwen3-VL Director：三种接法任选其一。
  - local：把权重放在本地目录，并配置 `director.qwen3vl.model_path`。
  - ollama：配置 `director.qwen3vl.mode=ollama`、`api_base`、`api_model`，可指向本机或局域网内其他 Ollama 设备。
  - openai_compatible：配置 `director.qwen3vl.mode=openai_compatible`、`api_base`、`api_model`，适用于 LM Studio 或其他 OpenAI 兼容服务，也可指向局域网内设备。
3. ComfyUI 服务：本机或远程启动并可访问 `http://127.0.0.1:8188`，必要时修改 `configs/comfy.default.json` 的 `server`。
4. ComfyUI 工作流模板：把对应 API workflow JSON 放到 `configs/comfy_workflows/`，文件名要与 `configs/comfy.default.json` 中的 `workflow_templates` 映射一致（`establish_scene.json`、`dialogue_light_motion.json` 等）。

未准备完成前，相应 gate 会输出 honest blocked 报告而不是假成功。
