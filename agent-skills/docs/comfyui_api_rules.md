# ComfyUI 自动化与 API 队列规则

- 使用 D:/ComfyUI-aki-v3/ComfyUI/models 作为主模型目录。
- 本地自动化优先使用 D:/ComfyUI-aki-v3/.venv/Scripts/python.exe。
- 可重复执行的 ComfyUI 自动化优先使用 API 工作流。
- 导出的 API 工作流仍放在 agent-skills/comfyui/workflows/api/。
- 未检查前不要假设节点 ID、节点类名或模型文件名。
- 已安装 ComfyUI Queue Manager：ComfyUI/custom_nodes/comfyui-queue-manager，用于统一查看网页队列和代理后台提交的任务。
- 代理调用 ComfyUI API 提交任务时，必须让任务能在网页队列中被识别；不要使用无意义的随机 client_id。
- 调用 /prompt 时，client_id 建议使用：agent:<代理名>|workflow:<工作流名>|run:<8位十六进制随机ID，例如 a3f9c1b2>。
- 调用 /prompt 时，extra_data 建议至少包含 agent、workflow_name、source、notes 等字段，方便 Queue Manager 或 history 页面显示来源。
- 如果临时覆写了 prompt、seed、模型、LoRA、尺寸、帧数或输入媒体，必须在 extra_data.notes 中简要说明，并在最终回复里告知用户。
- 对明确要求质量优先的任务，先用当前设备可稳定运行的最佳配置测试出可评价、可复现的本地实用方案，并记录模型精度、尺寸与限制；只有该路线在本机验证有效后，才规划云端同系更大/更高精度配置提升质量上限。
- 若用户希望画布反映 API 提交内容，则加载该工作流到画布；若用户希望 API 提交沿用当前画布，则先导出当前画布为 API JSON 再提交。

## 推荐流程

1. 先确认 ComfyUI 可通过 127.0.0.1:8188 访问。
2. 用 download_models.py 检查或同步所需模型包。
3. 用 generate_video.py --list-skills、--skill 或 --workflow-api 运行自动化。
4. 如果工作流还是完整 UI 格式，先导出一次 API JSON，不要每次临时重建。
