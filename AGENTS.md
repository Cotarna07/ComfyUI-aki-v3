# 代理协作说明

这个工作区把“代理自有区”和“秋叶启动器原区”分开管理，供 Copilot、Codex 以及其他编码代理共同遵守。

## 必读文件

- 先读 AGENTS.md，并先据此判定目录归属、修改权限与根目录例外；只有命中相关场景时，再继续查看后续专题段落。
- 涉及技能包或 ComfyUI 自动化时，再读 agent-skills/README.md、agent-skills/comfyui/registry.json 和 agent-skills/comfyui/SKILL.md。
- 涉及 Git 管理、根目录兼容入口或子仓库边界时，再读 agent-skills/docs/workspace_git_rules.md。
- 涉及 Windows 文本编辑、编码或验证时，再读 agent-skills/docs/windows_dev_defaults.md。
- 涉及 ComfyUI API 提交、Queue Manager 或自动化执行时，再读 agent-skills/docs/comfyui_api_rules.md。
- 涉及电商商品图优化、商品广告主视觉、产品视频关键帧或商品真实性验收时，再读 agent-skills/comfyui/skills/comfyui-product-image-integrity/SKILL.md。
- 涉及独立项目时，再读 agent-projects/README.md。
- 涉及新建文件归属判断、项目域归属、runtime 内容规范、ComfyUI 客户端选择或共享能力晋升时，再读 agent-skills/docs/project_governance.md。

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
- agent-skills/comfyui/disabled-custom-nodes/：已禁用的 ComfyUI 自定义节点存档（含源码，不是产物）。
- agent-projects/<project-slug>/：独立项目的代码、测试、项目文档和项目内脚本。
- agent-projects/comfyui-shared/：跨项目共享的 ComfyUI HTTP 客户端与 LLM 输出解析工具（纯 stdlib，无第三方依赖）。
- agent-projects/product-media/：商品图 / 商品视频 / 营销创意广告 / 商品真实性验收的代码与运行产物统一宿主。
- 不要把独立应用、独立 Python 包、独立服务项目放进 agent-skills/。
- runtime/ 目录只允许放图片、JSON 记录、Markdown 报告、日志等运行产物；Python 源码、依赖包、可复用脚本禁止放入 runtime/。
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

> **多设备说明**：本项目在多台设备间共享使用（如通过 Git 同步）。
> 下方表格记录了各设备的运行时环境。代理启动后应主动探测当前设备，
> 与下表比对并更新"当前"标记。如发现未记录的新设备，请在表格末尾按模板补充。

### 已知设备清单

| 设备标识 | GPU | 显存 | Python | Node.js | PyTorch | CUDA | 备注 |
|---------|-----|------|--------|---------|---------|------|------|
| 设备 A | NVIDIA GeForce RTX 5070 Ti | 16 GB | 3.13.11 | v22.14.0 | 2.9.1+cu130 | 13.0 | — |
| 设备 B（当前） | NVIDIA GeForce RTX 4080 | 16 GB | 3.13.11 | v22.14.0 | 2.9.1+cu128 | 12.8 | ComfyUI 运行时为 D:\ComfyUI-aki-v3\python\python.exe |
| *(待补充)* | | | | | | | 代理探测到新设备时填写此行 |

### 代理设备探测指引

1. **启动时探测**：运行 `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` 获取 GPU 信息，运行 `python --version`、`node --version` 确认运行时版本，与上表比对。
2. **匹配已知设备**：将匹配行标记为"当前"，其余行去除"当前"标记。
3. **发现新设备**：在上表末尾新增一行，填写探测到的完整配置，标记为"当前"，并在本次对话中告知用户已添加新设备记录。
4. **显存敏感任务**：生成配置、分辨率、batch size 等参数时，以**当前设备**的显存和 GPU 型号为准，不得假设其他设备的配置。

## 既有约定

- 使用 D:/ComfyUI-aki-v3/ComfyUI/models 作为主模型目录。
- 本地自动化优先使用 D:/ComfyUI-aki-v3/.venv/Scripts/python.exe。
- 可重复执行的 ComfyUI 自动化优先使用 API 工作流。
- ComfyUI 工作流统一以 agent-skills/comfyui/workflows/ 作为总入口：01-shared/ 放跨项目正式模板，02-project/<project>/ 放项目专用模板，03-source/ 放 imported、vendor、drafts 与历史归档。
- 导出的 API 工作流默认进入 agent-skills/comfyui/workflows/01-shared/；其余 ComfyUI API 与队列约定详见 agent-skills/docs/comfyui_api_rules.md。

## 质量优先生成规则

- 对用户明确要求“效果最好”或“质量优先”的图像/视频生成任务，先发挥当前设备性能，测试出能够稳定执行、可评价且视觉效果尽可能好的本地实用方案；不得仅为速度或运行便利无依据降质。
- 本地测试可以采用适配当前显存的同系较小/量化权重、合理尺寸或受控采样配置，但必须记录参数、效果和限制；不得把本机结果冒充同路线更大模型或云算力下的质量上限。
- 只有本机已证明工作流、提示词与视觉方向具有实用价值后，才规划云 GPU 上同路线更高精度、更大模型或更高分辨率的复测与最终制作。
- 选择工作流、主模型、VAE、LoRA、控制模型和放大/补帧模型时，按当前阶段的视觉质量、结构一致性、任务适配度与实际可运行性共同决策。
- 商品图与商品视频还必须区分“创意广告视觉”和“真实商品展示”：创意重绘可以强化场景、光影和叙事，但真实 SKU、配件数量、结构与包装信息需要由原图或严格验收素材兜底。
- 商品图输出一旦出现结构、配件数量、材质、颜色、角色身份或关键比例与原图不一致，除非明确标注为不可用于实物核验的创意广告图，否则不得作为真实商品展示或发布素材交付。

## ComfyUI API 队列可见性

- ComfyUI API 提交、Queue Manager 可见性、client_id、extra_data 和画布同步规则详见 agent-skills/docs/comfyui_api_rules.md。

## 推荐流程

1. ComfyUI 自动化执行的推荐步骤详见 agent-skills/docs/comfyui_api_rules.md。
