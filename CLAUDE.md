先读 AGENTS.md。

这个工作区只有两个代理自有区：agent-skills/ 和 agent-projects/。
除这两个目录及固定入口说明文件外，其他路径默认都视为秋叶启动器原区；未经用户明确允许，不得修改。
人类可读文档默认简体中文；如需 commit 或 PR 说明，统一使用中文。
优先更新已有文档，不要新增重复说明；临时脚本和运行产物必须留在 agent 自有区子目录内，不要堆在根目录。
命令示例默认使用 PowerShell，优先使用现有 .venv；编辑含中文的文本文件时必须保证 UTF-8 安全。
技能包相关规则继续读取 agent-skills/README.md、agent-skills/comfyui/registry.json 和 agent-skills/comfyui/SKILL.md。
独立项目代码默认放在 agent-projects/<project-slug>/，不要再放进 agent-skills/。
