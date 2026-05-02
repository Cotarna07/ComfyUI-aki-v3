先读 AGENTS.md。

这个工作区只有两个 agent 自有区：agent-skills/ 和 agent-projects/。
除这两个目录及固定入口说明文件外，其他路径默认都视为 ComfyUI 上游区、启动器原区或模型配置区；未经用户明确允许，不得修改。

模型与大体积素材默认留在 ComfyUI/models/ 或 ComfyUI/extra_model_paths.yaml 指向的外部目录，不要塞进 agent-skills/ 或 agent-projects/。
人类可读文档默认简体中文；如需 commit 或 PR 说明，统一使用中文。
优先更新已有文档，不要新增重复说明；临时脚本和运行产物必须留在 agent 自有区子目录内，不要堆在根目录。

命令示例默认使用 PowerShell，优先使用现有 .venv；编辑含中文的文本文件时必须保证 UTF-8 安全。
涉及 ComfyUI 自动化或技能层时，再读 agent-skills/README.md 和 agent-skills/comfyui/README.md。
涉及独立项目时，再读 agent-projects/README.md。

本机硬件假设：Intel Core Ultra 7 265K 同级 CPU、RTX 5070 Ti 同级 GPU、16GB VRAM、64GB RAM。后续推理链路默认按 GPU-first、支持分段与可重入处理来设计。