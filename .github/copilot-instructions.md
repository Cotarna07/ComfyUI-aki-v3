以 AGENTS.md 作为本工作区的跨代理总规则入口。

这个工作区只有两个 agent 自有区：

- agent-skills/
- agent-projects/

除这两个目录及固定入口说明文件外，其他路径默认都视为 ComfyUI 上游区、启动器原区或模型配置区；未经用户明确允许，不得修改。

人类可读文档默认使用简体中文；如需 commit 或 PR 说明，统一使用中文。
优先更新已有文档，不创建重复说明或历史副本。
只有用户明确要求“总结 / 沉淀”时，才新增总结文档，命名建议为 YYYY-MM-DD_简要内容.md。

默认约定：

- 独立项目代码统一放在 agent-projects/<project-slug>/，不要再放进 agent-skills/。
- 跨代理可复用的技能包、ComfyUI 自动化资产、工作流导出、技能层脚本与说明放在 agent-skills/。
- 模型权重、大体积素材与缓存留在 ComfyUI/models/ 或 ComfyUI/extra_model_paths.yaml 指向的外部目录，不要塞进 agent-skills/ 或 agent-projects/。
- 临时脚本不要放根目录；技能层放 agent-skills/scripts/generated/<topic>/，独立项目放 agent-projects/<project-slug>/scripts/generated/<topic>/。
- JSON、CSV、TXT、截图、分析结果等运行产物放各自 runtime/ 目录，不要散落在根目录或 docs/。
- 命令示例默认使用 PowerShell，优先使用现有 .venv。
- 项目已有 requirements.txt 或 pyproject.toml 时沿用现有方式，不强推 uv，也不要预设 src/ 布局。
- 明确禁止访问或读取任何名为 cache 或其变体的文件夹内容；自动化流程不得依赖或修改 cache 目录内文件。
- 修改含中文的文本文件时必须使用安全的 UTF-8 编辑方式；修改 Python 文件后要做最相关的校验。

本地产品与工程约束：

- 桌面 GUI 默认使用 tkinter，不要改成 Gradio、Electron 或 Web 前端作为默认主界面，除非用户明确要求。
- 功能逻辑、处理链路、限制条件发生变化后，应同步更新 docs/ 中对应文档，例如 docs/architecture.md、docs/需求.md。
- 优先代码可读性与模块边界清晰，避免单个文件持续膨胀。

## Hardware assumptions
- Desktop CPU class similar to Intel Core Ultra 7 265K
- NVIDIA RTX 5070 Ti class GPU
- 16GB VRAM class constraint
- 64GB system RAM

## Performance rules
- This project is GPU-first.
- Do not silently run model inference on CPU when CUDA is expected.
- All heavy inference paths must support batch size configuration.
- Long videos must be processed in chunks and support resumable execution.
- Avoid recomputing embeddings, detections, frame extraction, or split results for unchanged inputs.
- Separate CPU orchestration from GPU inference.
- Expose performance-related options in YAML or TOML config when practical.
- Log processing time, cache hits, fallback reasons, and memory usage.

## Project priorities
1. Creator workflow speed
2. Stable local execution
3. Resumability
4. GPU utilization
5. Clean exports for post-production workflows

## 本机 TTS 服务集成规范

- 禁止在本项目里重新安装或加载任何 TTS 模型。
- 禁止直接 import D:/tts 下的模型代码。
- 必须通过 HTTP 调用本机已部署的 TTS 统一网关。
- 网关入口：D:/tts/src/tts-gateway/app.py
- 启动方式：在 D:/tts/src/tts-gateway 目录下执行 D:/tts/venv/tts-main/Scripts/python.exe -m uvicorn app:app --host 0.0.0.0 --port 18081 --workers 1
- 基地址：http://localhost:18081
- 每次调用前先调 /healthz。
- 必须处理 succeeded / failed / skipped 三种状态，不能假设一定成功。
- 解说词配片场景里，TTS 主要用于时轴估算，不直接等同最终成片配音。
- TTS 客户端统一封装到单一模块，不要在各处散写 HTTP 调用。
