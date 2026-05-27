先读 AGENTS.md。

这个工作区只有两个代理自有区：agent-skills/ 和 agent-projects/。
除这两个目录及固定入口说明文件外，其他路径默认都视为秋叶启动器原区；未经用户明确允许，不得修改。
人类可读文档默认简体中文；如需 commit 或 PR 说明，统一使用中文。
优先更新已有文档，不要新增重复说明；临时脚本和运行产物必须留在 agent 自有区子目录内，不要堆在根目录。
命令示例默认使用 PowerShell，优先使用现有 .venv；编辑含中文的文本文件时必须保证 UTF-8 安全。
技能包相关规则继续读取 agent-skills/README.md、agent-skills/comfyui/registry.json 和 agent-skills/comfyui/SKILL.md。
ComfyUI 工作流统一以 agent-skills/comfyui/workflows/ 为总入口：01-shared/ 放跨项目正式模板，02-project/<project>/ 放项目专用模板，03-source/ 放 imported、vendor、drafts 与历史归档。
独立项目代码默认放在 agent-projects/<project-slug>/，不要再放进 agent-skills/。
ComfyUI 已安装 Queue Manager：ComfyUI/custom_nodes/comfyui-queue-manager。
代理调用 ComfyUI /prompt API 时，必须使用可识别的 client_id，例如 agent:<代理名>|workflow:<工作流名>|run:<短ID>，并在 extra_data 中写明 agent、workflow_name、source、notes；临时覆写 prompt、seed、模型、LoRA、尺寸、帧数或输入媒体时，必须记录在 notes 并告知用户。
后台 API 排队不会自动改变 Chrome 画布；用户要求界面同步时，先保存或加载对应工作流，再执行。
