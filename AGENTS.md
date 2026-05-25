# 代理协作说明

这个工作区把“代理自有区”和“秋叶启动器原区”分开管理，供 Copilot、Codex 以及其他编码代理共同遵守。

## 必读文件

- 先读 AGENTS.md，并先据此判定目录归属、修改权限与根目录例外；只有命中相关场景时，再继续查看后续专题段落。
- 涉及技能包或 ComfyUI 自动化时，再读 agent-skills/README.md、agent-skills/comfyui/registry.json 和 agent-skills/comfyui/SKILL.md。
- 涉及 Git 管理、根目录兼容入口或子仓库边界时，再读 agent-skills/docs/workspace_git_rules.md。
- 涉及 Windows 文本编辑、编码或验证时，再读 agent-skills/docs/windows_dev_defaults.md。
- 涉及 ComfyUI API 提交、Queue Manager 或自动化执行时，再读 agent-skills/docs/comfyui_api_rules.md。
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

| 路径类别 | 读取 / 执行 | 新建 / 修改 / 删除 | 说明 |
|------|------|------|------|
| agent-skills/ 与 agent-projects/ | 允许 | 允许 | 仍需遵守放置规则、Git 管理约定与项目内说明 |
| AGENTS.md / CLAUDE.md / .github/copilot-instructions.md | 允许 | 仅允许维护这些入口文件本身 | 属于根目录例外，不等于允许新增其他根级普通文件 |
| 其他路径（包括 ComfyUI/、启动器原文件、根目录兼容入口脚本） | 允许 | 仅在用户明确允许时 | 默认视为秋叶启动器原区 |
- “明确允许”指用户直接点名要改的文件或目录，或明确说明本次任务可以改启动器或上游文件。
- 如果问题既可以通过在 agent 自有区新增文件解决，也可以通过改秋叶启动器原区解决，默认选择前者。

## Git 管理约定

- agent-skills/ 与 agent-projects/ 下由代理协作生成和维护的文件，默认统一由当前工作区现有版本管理跟踪；涉及根目录 .git、overlay 或子仓库边界时，按 agent-skills/docs/workspace_git_rules.md 执行。

## 放置规则

- agent-skills/docs/：技能包说明、技能层规则、与技能层直接相关的文档。
- agent-skills/scripts/：技能层辅助脚本、适配器、小工具。
- agent-skills/comfyui/：ComfyUI 专用注册表、工作流导出、技能资产。
- agent-projects/<project-slug>/：独立项目的代码、测试、项目文档和项目内脚本。
- 不要把独立应用、独立 Python 包、独立服务项目放进 agent-skills/。
- 现有根目录文件 comfyui_skill_utils.py、download_models.py、generate_video.py 属于兼容性保留入口，可作为读取或执行入口使用，但除用户明确允许外，不作为默认修改目标。

## 文档与临时文件规则

- 优先更新已有文档，不创建重复文档、历史副本或“新版说明 / 旧版说明”并存的文件。
- 技能层说明文档放在 agent-skills/docs/；独立项目文档放在各自项目目录内的 README.md 或 docs/。
- 只有在用户明确要求“总结 / 沉淀”时，才新增总结文档；命名建议为 YYYY-MM-DD_简要内容.md。
- 一次性排查脚本、实验脚本、临时分析脚本不要放在根目录。
- 技能层临时代码放在 agent-skills/scripts/generated/<topic>/；独立项目临时代码放在 agent-projects/<project-slug>/scripts/generated/<topic>/。
- JSON、CSV、TXT、截图、分析结果等运行产物放在对应项目或主题自己的 runtime/ 目录，不要散落在根目录或 docs/。

## Windows 开发默认值

- Windows 下的命令、依赖沿用、源码路径判断与验证范围，按 agent-skills/docs/windows_dev_defaults.md 执行。

## 编码与校验安全

- 涉及中文文本改写、UTF-8 安全和 Python 文件后的最相关校验时，按 agent-skills/docs/windows_dev_defaults.md 执行。

## 本机开发环境约束

### 当前已观测运行时版本
| 环境 | 版本 |
|------|------|
| Python | 3.13.11 (64-bit, MSC v.1944) |
| Node.js | v22.14.0 |
| PyTorch | 2.9.1+cu130 |
| CUDA | 13.0 |
| GPU | NVIDIA GeForce RTX 4080 (16GB) |

## 既有约定

- 使用 D:/ComfyUI-aki-v3/ComfyUI/models 作为主模型目录。
- 本地自动化优先使用 D:/ComfyUI-aki-v3/.venv/Scripts/python.exe。
- 可重复执行的 ComfyUI 自动化优先使用 API 工作流。
- 导出的 API 工作流仍放在 agent-skills/comfyui/workflows/api/；其余 ComfyUI API 与队列约定详见 agent-skills/docs/comfyui_api_rules.md。

## ComfyUI API 队列可见性

- ComfyUI API 提交、Queue Manager 可见性、client_id、extra_data 和画布同步规则详见 agent-skills/docs/comfyui_api_rules.md。

## 推荐流程

1. ComfyUI 自动化执行的推荐步骤详见 agent-skills/docs/comfyui_api_rules.md。
