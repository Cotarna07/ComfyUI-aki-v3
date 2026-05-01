以 AGENTS.md 作为本工作区的跨代理总规则入口。

这个工作区只有两个代理自有区：

- agent-skills/：技能包、ComfyUI 自动化资产、技能层脚本与说明
- agent-projects/：独立项目代码，尤其是后续新建的 Python 项目

除这两个目录及固定入口说明文件外，其他路径默认都视为秋叶启动器原区；未经用户明确允许，不得修改。
不要再把独立项目代码放进 agent-skills/。
所有代理生成的人类可读文档默认使用简体中文，除非用户明确要求其他语言。

默认约定：

- 如需提交、生成 commit message 或编写 PR 描述，统一使用中文；commit 格式为：<类型>: <一句话中文说明>，PR 描述按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。
- 优先更新已有文档，不创建重复说明或历史副本。
- 只有用户明确要求“总结 / 沉淀”时，才新建总结文档；命名建议为 YYYY-MM-DD_简要内容.md。
- 一次性排查、实验、临时分析脚本不要放根目录；技能层放 agent-skills/scripts/generated/<topic>/，独立项目放 agent-projects/<project-slug>/scripts/generated/<topic>/。
- 运行产物和中间结果放各自 runtime/ 目录，不要散落在根目录或 docs/。
- 命令示例默认使用 PowerShell，优先使用现有 .venv。
- 项目已有 requirements.txt 或 pyproject.toml 时沿用现有方式，不强推 uv，也不要预设 src/ 布局。
- 修改含中文的文本文件时必须使用安全的 UTF-8 编辑方式；修改 Python 文件后要做最相关的校验。
- ComfyUI 已安装 Queue Manager：ComfyUI/custom_nodes/comfyui-queue-manager，用于统一查看网页队列和代理后台提交的任务。
- 代理调用 ComfyUI /prompt API 时，必须使用可识别的 client_id，例如 agent:<代理名>|workflow:<工作流名>|run:<短ID>，并在 extra_data 中写明 agent、workflow_name、source、notes。
- 临时覆写 prompt、seed、模型、LoRA、尺寸、帧数或输入媒体时，必须记录在 extra_data.notes 并告知用户。
- 后台 API 排队不会自动改变 Chrome 画布；用户要求界面同步时，先保存或加载对应工作流，再执行。

## 本机开发环境约束

### 运行时版本
| 环境 | 版本 |
|------|------|
| Python | 3.10.6 (64-bit, MSC v.1932) |
| Node.js | v22.14.0 |
| PyTorch | 2.6.0+cu124 |
| CUDA | 12.4 |
| GPU | NVIDIA GeForce RTX 4080 (16GB) |


涉及技能包或 ComfyUI 自动化时，还要读取：

- agent-skills/README.md
- agent-skills/comfyui/registry.json
- agent-skills/comfyui/SKILL.md

涉及独立项目时，还要读取：

- agent-projects/README.md
