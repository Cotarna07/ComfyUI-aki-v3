# 代理协作说明

这个工作区把“代理自有区”和“秋叶启动器原区”分开管理，供 Copilot、Codex 以及其他编码代理共同遵守。

## 必读文件

- 先读 AGENTS.md。
- 涉及技能包或 ComfyUI 自动化时，再读 agent-skills/README.md、agent-skills/comfyui/registry.json 和 agent-skills/comfyui/SKILL.md。
- 涉及独立项目时，再读 agent-projects/README.md。

## 协作输出约定

- 所有代理生成的人类可读文档默认使用简体中文，除非用户明确要求其他语言。
- 只有在用户要求提交、生成 commit message 或编写 PR 描述时，才进入提交流程相关约定。
- Commit message 使用中文，格式统一为：<类型>: <一句话中文说明>。
- 常用类型建议使用：修复 / 优化 / 重构 / 测试 / 文档 / 配置。
- PR 标题与描述使用中文，描述按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。

## 目录归属

- agent-skills/：只放跨代理技能包、ComfyUI 自动化资产、与技能层直接相关的小型脚本和说明。
- agent-projects/：只放独立项目代码。未来新建的 Python 项目、工具项目、实验项目都应按 agent-projects/<project-slug>/ 单独落目录。
- 秋叶启动器原区：除上述 agent 自有区及固定入口文件外的其他路径，默认都视为启动器或上游项目管理区，包括 ComfyUI/、现有根目录脚本、启动器资源和已有业务文件。

## 修改权限规则

- 默认只读：agent-skills/ 与 agent-projects/ 之外的路径，代理只能读取和分析，不能擅自创建、修改、删除、重命名。
- 只有在用户明确允许的情况下，才能改动秋叶启动器原区文件。
- “明确允许”指用户直接点名要改的文件或目录，或明确说明本次任务可以改启动器或上游文件。
- 如果问题可以通过在 agent 自有区新增文件解决，就不要改秋叶启动器原区。
- AGENTS.md、CLAUDE.md、.github/copilot-instructions.md 是发布这套规则的固定入口文件。除维护这套规则本身外，不要把新的普通文件继续堆在根目录。

## Git 管理约定

- agent-skills/ 与 agent-projects/ 下由代理协作生成和维护的文件，默认统一纳入当前工作区根目录的 overlay Git 仓库管理。
- 秋叶启动器原区文件继续由其自身仓库管理；未经用户明确允许，不要把原区文件并入 overlay Git 仓库。
- 非用户明确要求，不要在 agent-skills/ 或 agent-projects/ 子目录内再初始化或保留并行的独立 Git 仓库。
- 如果引入了自带 .git 的外部项目，先停用或迁出其子仓库元数据，再决定是否并入当前 overlay Git 仓库。

## 放置规则

- agent-skills/docs/：技能包说明、技能层规则、与技能层直接相关的文档。
- agent-skills/scripts/：技能层辅助脚本、适配器、小工具。
- agent-skills/comfyui/：ComfyUI 专用注册表、工作流导出、技能资产。
- agent-projects/<project-slug>/：独立项目的代码、测试、项目文档和项目内脚本。
- 不要把独立应用、独立 Python 包、独立服务项目放进 agent-skills/。
- 现有根目录文件 comfyui_skill_utils.py、download_models.py、generate_video.py 属于兼容性保留入口，不是后续新文件的默认落点。

## 文档与临时文件规则

- 优先更新已有文档，不创建重复文档、历史副本或“新版说明 / 旧版说明”并存的文件。
- 技能层说明文档放在 agent-skills/docs/；独立项目文档放在各自项目目录内的 README.md 或 docs/。
- 只有在用户明确要求“总结 / 沉淀”时，才新增总结文档；命名建议为 YYYY-MM-DD_简要内容.md。
- 一次性排查脚本、实验脚本、临时分析脚本不要放在根目录。
- 技能层临时代码放在 agent-skills/scripts/generated/<topic>/；独立项目临时代码放在 agent-projects/<project-slug>/scripts/generated/<topic>/。
- JSON、CSV、TXT、截图、分析结果等运行产物放在对应项目或主题自己的 runtime/ 目录，不要散落在根目录或 docs/。

## Windows 开发默认值

- 命令示例默认使用 PowerShell。
- 优先使用仓库或项目现有的 .venv。
- 如果项目已经使用 requirements.txt 或 pyproject.toml，优先沿用现有依赖管理方式，不强行迁移到 uv 或其他新工具。
- 不要假设 src/ 目录布局；先按真实项目结构组织代码、测试和校验范围。
- lint、type check、测试优先针对真实源码路径和本次改动范围执行。

## 编码与校验安全

- 不要用 PowerShell 默认编码管道直接改写包含中文的 .py、.md、.json、.yaml 等文本文件。
- 如需脚本化读写文本，必须显式使用 UTF-8。
- 修改 Python 文件后，优先运行最相关的校验，例如 python -m py_compile、pytest 或目标脚本自检。
- 临时日志、缓存和中间结果优先放在 agent 自有区的 runtime/、logs/ 或 generated 目录，不要继续堆在根目录。

## 本机开发环境约束

### 运行时版本
| 环境 | 版本 |
|------|------|
| Python | 3.10.6 (64-bit, MSC v.1932) |
| Node.js | v22.14.0 |
| PyTorch | 2.6.0+cu124 |
| CUDA | 12.4 |
| GPU | NVIDIA GeForce RTX 4080 (16GB) |

## 既有约定

- 使用 D:/ComfyUI-Models 作为主模型目录。
- 本地自动化优先使用 D:/ComfyUI-aki-v3/.venv/Scripts/python.exe。
- 可重复执行的 ComfyUI 自动化优先使用 API 工作流。
- 导出的 API 工作流仍放在 agent-skills/comfyui/workflows/api/。
- 未检查前不要假设节点 ID、节点类名或模型文件名。

## 推荐流程

1. 先确认 ComfyUI 可通过 127.0.0.1:8188 访问。
2. 用 download_models.py 检查或同步所需模型包。
3. 用 generate_video.py --list-skills、--skill 或 --workflow-api 运行自动化。
4. 如果工作流还是完整 UI 格式，先导出一次 API JSON，不要每次临时重建。
