# manga-anime-pipeline

这是《私有化漫画转动漫多模块工作流设计方案》的私有化漫画转动漫流水线工程。当前目标覆盖：输入漫画图片 -> 长图切片 -> OCR provider -> OCR-based Dialogue provider -> lightweight 或 Grounded-SAM-2 检测 -> 导演草稿 shot manifest -> ComfyUI API 工作流投递 -> 自动验收报告。

当前已接入可选 PaddleOCR、规则型 OCR-based Dialogue、lightweight detection、Grounded-SAM-2/Ultralytics 检测入口、Qwen3-VL director 入口，以及 Wan/VACE 方向的 ComfyUI API 工作流模板。Manga Image Translator、完整口型/音频/BGM 后期链和人工审核台仍未接入。

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

实际执行 `run_stage1.py`、`run_acceptance.py`、各 stage gate 或 `run_all_gates.py` 时，脚本会自动在 `runtime/` 下创建当前漫画的专属目录，目录名格式为 `YYYY-MM-DD_<series_id>`。当前输入 manifest 会被复制到该专属目录的 `input/` 下，后续 stage 产物也都会统一写入这个目录。

如果同一个 `series_id` 之前已经跑过，脚本会复用已有专属目录，而不是重复创建新的日期目录；旧版散落在 `runtime/windows/`、`runtime/structured/`、`runtime/manifests/`、`runtime/qc/`、`runtime/comfy/` 下的同漫画产物也会自动迁入该专属目录。

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

默认输出在项目内 `runtime/YYYY-MM-DD_<series_id>/` 下：

- `runtime/YYYY-MM-DD_<series_id>/input/<chapter_manifest>.json`
- `runtime/YYYY-MM-DD_<series_id>/input/pages/<page_id>_<image_name>.png`
- `runtime/YYYY-MM-DD_<series_id>/windows/<series_id>/<chapter_id>/window_manifest.json`
- `runtime/YYYY-MM-DD_<series_id>/windows/<series_id>/<chapter_id>/<page_id>/w0000.png`
- `runtime/YYYY-MM-DD_<series_id>/structured/<series_id>/<chapter_id>/packets/<window_id>.json`
- `runtime/YYYY-MM-DD_<series_id>/structured/<series_id>/<chapter_id>/structured_packets.json`
- `runtime/YYYY-MM-DD_<series_id>/manifests/<series_id>/<chapter_id>/shot_manifest.json`
- `runtime/YYYY-MM-DD_<series_id>/qc/<series_id>/<chapter_id>/stage1_status.json`
- `runtime/YYYY-MM-DD_<series_id>/qc/<series_id>/<chapter_id>/acceptance_report.json`
- `runtime/YYYY-MM-DD_<series_id>/qc/<series_id>/<chapter_id>/acceptance_report.md`
- `runtime/YYYY-MM-DD_<series_id>/comfy/<series_id>/<chapter_id>/comfy_tasks.json`

每个阶段都会写入 task status，字段包含 `task_id`、`stage`、`status`、`started_at`、`finished_at`、`input_refs`、`output_refs`、`error_message`、`retry_count`。

## 核心工作流目录

项目核心代码开始按“可单独理解、可单独测试、可复用产物”的工作流边界收敛到 `pipeline/workflows/`：

- `pipeline/workflows/chapter_analysis/`：章节分析闭环，负责读取章节、切片窗口、构建结构化素材包、生成 shot manifest 和写入阶段状态。
- `pipeline/stage1.py`：旧入口兼容层，继续导出 `run_stage1`，方便既有脚本、测试和门禁不受目录拆分影响。

`chapter_analysis` 内部再按职责拆分：

- `artifacts.py`：负责 windows、structured packets、shot manifest 的复用、校验和重建。
- `providers.py`：负责 OCR、dialogue、detection、director provider 装配和 runtime check。
- `executor.py`：负责单个 stage 的状态追踪、reused/completed/failed 标记和输出引用收集。
- `reports.py`：负责失败状态报告。
- `runner.py`：只保留章节分析主编排。

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
- `pipeline/manifest/packets.py`：合并结构化素材包并逐 window 落盘。
- `pipeline/director/mock.py`：mock director，输出符合 schema 的 shot 草稿。
- `pipeline/director/base.py`、`pipeline/director/context.py` 与 `pipeline/director/provider_factory.py`：导演 provider 抽象、上下文摘要与加载。
- `pipeline/manifest/shot_manifest.py`：写入 shot manifest，并在写入前校验 JSON schema。
- `pipeline/qc/acceptance.py` 与 `pipeline/qc/report.py`：自动验收规则、质量统计、JSON/Markdown 报告。
- `pipeline/workflows/chapter_analysis/runner.py`：串联第一阶段闭环。
- `pipeline/stage1.py`：兼容旧导入路径，后续新代码优先引用 `pipeline.workflows.chapter_analysis`。
- `scripts/run_acceptance.py`：运行 pipeline 并输出 acceptance report。

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

## 替换 mock detection

Grounded-SAM-2 接入点在 `pipeline/detection/`。新增 provider 类继承 `DetectionProvider`，保持 `analyze(window_packet) -> dict` 接口，返回：

- `object_boxes`
- `object_masks`
- `crop_candidates`
- `focus_subjects`
- `scene_density`

## 替换 mock director

Qwen3-VL 本地调用接入点在 `pipeline/director/`。真实 director 应继承 `DirectorProvider`，保持 `create_shots(structured_packet, context=None) -> list[dict]` 接口，并继续输出 `pipeline/common/schemas.py` 中 `SHOT_SCHEMA` 要求的所有字段。

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

## 当前未实现内容清单

- 未接真实 Surya、PaddleOCR-VL。
- 未接 Manga Image Translator。
- Grounded-SAM-2 当前通过 Ultralytics YOLO + SAM2 入口接入；本机未安装 `ultralytics` 时会降级为同接口 mock。
- 未实现人工审核台、失败重试策略和镜头质检模型。
- 未接完整音频 / 口型 / BGM 后期链。


## Stage 3A / 4A / 5 / 6 门禁体系

工程已经搭好从 OCR 到 ComfyUI 批量投递前后的完整闭环。每个 gate 都会输出独立 JSON + Markdown 报告，并由 `scripts/run_all_gates.py` 统一编排。

### Provider 切换表

| 角色 | 配置文件 | provider 名 | 真实依赖 |
|------|----------|-------------|----------|
| OCR | `configs/stage1.ocr.dialogue.json` 等 | `paddleocr` / `paddle` | `requirements-ocr.txt` |
| Dialogue | 同上 | `ocr_based` | 无外部依赖 |
| Detection（轻量） | `configs/stage1.ocr.dialogue.detect.json` | `lightweight` / `light` / `rule_based` | `requirements-detection.txt`（Pillow + opencv-python-headless） |
| Detection（Grounded-SAM-2） | `configs/stage1.grounded_sam2.detect.json` | `grounded_sam2` / `grounded-sam-2` | `requirements-detection.txt`（ultralytics + SAM2 权重；缺失时可同接口降级） |
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

### 一键运行

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
