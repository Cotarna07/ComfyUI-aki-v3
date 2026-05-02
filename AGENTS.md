# 代理协作说明

这个工作区把“agent 自有区”“模型与大体积素材区”以及“ComfyUI 上游原区”分开管理，供 Copilot、Claude、Codex 以及其他编码代理共同遵守。

## 必读文件

- 先读 AGENTS.md。
- 如存在 .github/copilot-instructions.md，再将其视为补充约束。
- 涉及跨代理技能层或 ComfyUI 自动化时，再读 agent-skills/README.md 与 agent-skills/comfyui/README.md。
- 涉及独立项目时，再读 agent-projects/README.md。

## 协作输出约定

- 所有代理生成的人类可读文档默认使用简体中文，除非用户明确要求其他语言。
- 只有在用户要求提交、生成 commit message 或编写 PR 描述时，才进入提交流程相关约定。
- Commit message 使用中文，格式统一为：<类型>: <一句话中文说明>。
- 常用类型建议使用：修复 / 优化 / 重构 / 测试 / 文档 / 配置。
- PR 标题与描述使用中文，描述按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。

## 目录归属

- agent-skills/：只放跨代理技能包、ComfyUI 自动化资产、技能层脚本与技能层说明。
- agent-projects/：只放与用户协同创建的独立项目代码、项目内文档、项目测试与项目脚本。
- 模型与大体积素材区：优先放在 ComfyUI/models/ 或 ComfyUI/extra_model_paths.yaml 指向的外部目录中，不要混入 agent-skills/ 或 agent-projects/。
- ComfyUI/：ComfyUI 自带仓库与其插件、测试、配置、蓝图等上游管理内容，按上游仓库边界处理。
- 启动器原区：除 agent-skills/、agent-projects/ 以及固定入口说明文件外，根目录中的 .launcher/、python/、git/、txt/exe 文件等都默认视为启动器或现有环境管理区。

## 修改权限规则

- 默认只允许代理创建、修改、删除 agent-skills/、agent-projects/ 以及固定入口说明文件。
- 固定入口说明文件仅限 AGENTS.md、CLAUDE.md、.github/copilot-instructions.md 这类协作入口。
- ComfyUI/、启动器原区、模型目录默认只读；只有在用户明确允许的情况下，才能改动这些路径。
- “明确允许”指用户直接点名要改的文件或目录，或明确说明本次任务可以改 ComfyUI 上游文件、启动器文件或模型配置。
- 如果问题可以通过 agent 自有区新增文件解决，就不要改 ComfyUI 上游区或启动器原区。
- 模型权重、缓存、大体积素材默认不移动、不重命名、不删除，除非用户明确要求。

## Git 管理约定

- agent-skills/ 与 agent-projects/ 下由代理协作生成和维护的文件，默认纳入当前工作区根目录 Git 仓库管理。
- ComfyUI/ 目录保留其自身 Git 仓库边界；未经用户明确允许，不要把 agent 自有区和 ComfyUI/ 的改动混成一次破坏性调整。
- 非用户明确要求，不要在 agent-skills/ 或 agent-projects/ 子目录内再初始化并行 Git 仓库。
- 如果引入了自带 .git 的外部项目，先停用或迁出其子仓库元数据，再决定是否并入当前工作区。

## 放置规则

- agent-skills/docs/：技能包说明、技能层规则、ComfyUI 自动化相关文档。
- agent-skills/scripts/：技能层辅助脚本、适配器、小工具。
- agent-skills/comfyui/：ComfyUI 专用技能资产、工作流导出、兼容性说明。
- agent-projects/<project-slug>/：独立项目的源码、配置、测试、文档、脚本与运行产物。
- 不要把独立 Python 项目、独立服务项目或独立 CLI 工具继续放进 agent-skills/。
- 不要把模型文件、LoRA、VAE、embedding、视频素材或大型中间结果塞进 agent 自有区。

## 文档与临时文件规则

- 优先更新已有文档，不创建重复文档、历史副本或“新版说明 / 旧版说明”并存文件。
- 项目逻辑、处理链路、限制条件变化后，应同步更新 docs/ 下对应文档，例如 docs/architecture.md、docs/需求.md。
- 模块说明文档默认放在已有文档体系内；只有 agent 自有区的边界说明，才放在 agent-skills/README.md 或 agent-projects/README.md。
- 只有在用户明确要求“总结 / 沉淀”时，才新增总结文档；命名建议为 YYYY-MM-DD_简要内容.md。
- 一次性排查脚本、实验脚本、临时分析脚本不要放在根目录。
- 技能层临时代码放在 agent-skills/scripts/generated/<topic>/；独立项目临时代码放在 agent-projects/<project-slug>/scripts/generated/<topic>/。
- JSON、CSV、TXT、截图、分析报告等运行产物放在各自 runtime/ 目录，不要散落在根目录。

## Windows 开发默认值

- 命令示例默认使用 PowerShell。
- 优先使用仓库或项目现有的 .venv。
- 如果项目已经使用 requirements.txt 或 pyproject.toml，优先沿用现有方式，不强推 uv，也不要预设 src/ 布局。
- lint、type check、测试优先针对真实源码路径和本次改动范围执行。
- 修改含中文的文本文件时必须使用安全的 UTF-8 编辑方式，不要用 PowerShell 默认编码管道直接覆盖。
- 修改 Python 文件后，优先运行最相关的语法、导入或行为校验。
- 明确禁止访问或读取任何名为 cache 或其变体的文件夹内容；自动化流程不得依赖或修改 cache 目录内文件。

## GUI 与产品约束

- 桌面 GUI 默认统一使用 tkinter。
- 不要改成 Gradio、Electron、Web 前端作为默认主界面，除非用户明确要求。
- UI 以可用、清晰、稳定为优先，不追求复杂皮肤化设计。

## 性能与工程原则

本项目默认是 GPU-first。

### Hardware assumptions

- Desktop CPU class similar to Intel Core Ultra 7 265K
- NVIDIA RTX 5070 Ti class GPU
- 16GB VRAM class constraint
- 64GB system RAM

### Mandatory engineering rules

- 不要在应走 CUDA 的重路径上静默回退到 CPU。
- 所有重推理链路都应支持 batch 配置。
- 长视频必须支持分段处理、缓存和重入。
- 避免对未变化的输入重复计算 embedding、抽帧、切分结果。
- CPU 负责调度、数据库、封装与文件管理；GPU 负责推理、检索、编解码加速。
- 新增性能开关应暴露到 YAML 或 TOML 配置中。
- 关键阶段应记录耗时、缓存命中、异常回退与显存占用信息。

## 当前项目重点

后续优化时，优先级默认为：

1. 创作者工作流速度
2. 本地稳定运行
3. 可重跑与可恢复
4. GPU 利用率
5. 干净导出与后期衔接效率

## 业务方向提示

当前项目已经不只是单一的视觉检索工具，后续重点应逐步转向：

1. 说话人感知切分
2. 文本检索
3. 角色检索
4. 多模态素材定位

若功能变化影响到以上方向，应同步更新 docs/需求.md 与 docs/architecture.md。
