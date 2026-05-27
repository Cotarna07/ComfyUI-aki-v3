以 AGENTS.md 作为本工作区的跨代理总规则入口；如果本文件与 AGENTS.md 不一致，以 AGENTS.md 为准。

这个工作区只有两个代理自有区：

- agent-skills/：技能包、ComfyUI 自动化资产、技能层脚本与说明
- agent-projects/：独立项目代码，尤其是后续新建的 Python 项目

固定入口说明文件仅指 AGENTS.md、CLAUDE.md 和 .github/copilot-instructions.md。除这两个目录及这三个固定入口说明文件外，其他路径默认都视为秋叶启动器原区；未经用户明确允许，不得新建、删除、写入或重命名。读取、执行只读命令，以及在各自 runtime/ 目录中生成运行产物，不算这里的“修改”。
如需改动秋叶启动器原区，先复述将要修改的路径与变更内容，得到用户明确“同意/确认”后方可执行，并在回复中标注已修改原区路径。
不要再把独立项目代码放进 agent-skills/。
所有代理生成的人类可读文档默认使用简体中文，除非用户明确要求其他语言。

默认约定：

以下只保留默认摘要；涉及 Git、Windows 文本安全和 ComfyUI API 的具体细则，以 AGENTS.md 引导的专题文档为准。

- 如需提交、生成 commit message 或编写 PR 描述，统一使用中文；commit 格式为：<类型>: <一句话中文说明>，PR 描述按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。
- 优先更新已有文档，不创建重复说明或历史副本；只有用户明确要求“总结 / 沉淀”且现有 README.md 或 docs/ 没有合适承载位置时，才按 YYYY-MM-DD_简要内容.md 新建总结文档。
- 一次性排查、实验、临时分析脚本不要放根目录；技能层放 agent-skills/scripts/generated/<topic>/，独立项目放 agent-projects/<project-slug>/scripts/generated/<topic>/。
- 运行产物和中间结果放各自 runtime/ 目录，不要散落在根目录或 docs/。
- 命令示例默认使用 PowerShell，优先使用现有 .venv。
- 项目已有 requirements.txt 或 pyproject.toml 时沿用现有方式，不强推 uv，也不要预设 src/ 布局。
- ComfyUI 工作流统一以 agent-skills/comfyui/workflows/ 为总入口：01-shared/ 放跨项目正式模板，02-project/<project>/ 放项目专用模板，03-source/ 放 imported、vendor、drafts 与历史归档。
- 修改含中文文本时，使用 UTF-8（无 BOM）写入；在 PowerShell 中使用 [System.IO.File]::WriteAllText(path, content, [System.Text.UTF8Encoding]::new($false))，不要使用默认 Set-Content / Out-File。修改 Python 文件后至少执行：(1) python -m py_compile 检查语法；(2) 若存在 pytest，则运行相关测试文件；(3) 若涉及导入路径变化，则运行 python -c "import <module>" 验证；其余细则按 agent-skills/docs/windows_dev_defaults.md 执行。
- ComfyUI 已安装 Queue Manager：ComfyUI/custom_nodes/comfyui-queue-manager，用于统一查看网页队列和代理后台提交的任务。
- 代理调用 ComfyUI /prompt API、填写 client_id / extra_data.notes、以及处理画布同步时，按 agent-skills/docs/comfyui_api_rules.md 执行。

## 本机开发环境约束

> 设备配置以 AGENTS.md 中的"已知设备清单"为唯一权威来源。
> 代理启动后按 AGENTS.md 中的"代理设备探测指引"探测并更新当前设备标记。
> 此处不再单独维护设备表，避免多文件不一致。


涉及技能包或 ComfyUI 自动化时，还要读取：

- agent-skills/README.md
- agent-skills/comfyui/registry.json
- agent-skills/comfyui/SKILL.md
- agent-skills/docs/workspace_git_rules.md
- agent-skills/docs/windows_dev_defaults.md
- agent-skills/docs/comfyui_api_rules.md

涉及独立项目时，还要读取：

- agent-projects/README.md
