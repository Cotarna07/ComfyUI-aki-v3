# agent-projects 目录说明

这个目录是后续与 Copilot、Claude、Codex 或其他 agent 协作生成独立项目代码的专用区，用来和 ComfyUI 上游原区、启动器原区、agent-skills 技能层分开。

## 使用方式

- 每个独立项目单独建一个子目录，统一使用 agent-projects/<project-slug>/。
- 后续新建的 Python 项目、CLI 工具、数据整理工具、自动化服务默认建在这里。
- 项目自己的 README、requirements.txt 或 pyproject.toml、源码目录、tests、scripts 都放在各自项目子目录内部。
- 如果项目已经有 requirements.txt、pyproject.toml 或 .venv，优先沿用现有方式，不要再平行造一套新配置。

## 推荐结构

- agent-projects/<project-slug>/README.md
- agent-projects/<project-slug>/requirements.txt 或 pyproject.toml
- agent-projects/<project-slug>/<package_or_app>/
- agent-projects/<project-slug>/tests/
- agent-projects/<project-slug>/scripts/
- agent-projects/<project-slug>/scripts/generated/
- agent-projects/<project-slug>/docs/
- agent-projects/<project-slug>/runtime/

## 开发默认值

- 命令示例默认使用 PowerShell。
- 优先使用仓库或项目现有的 .venv。
- 已经使用 requirements.txt 或 pyproject.toml 的项目，优先沿用现有方式，不强推 uv 或平行配置。
- 不要先假设 src/ 布局；先按项目真实源码目录组织代码、测试和校验范围。
- lint、type check、测试优先针对真实源码路径和本次改动范围执行。

## 文档规则

- 优先更新项目内已有 README.md 或 docs/ 文档，不创建重复版本、历史副本或“新版说明 / 旧版说明”并存文件。
- 项目级概览优先放 README.md；较长的专题说明放 docs/。
- 只有用户明确要求“总结 / 沉淀”时，才新建总结文档。
- 总结文档命名建议：YYYY-MM-DD_简要内容.md，描述使用简体中文。

## 临时文件与运行产物

- 一次性排查脚本、实验脚本、临时分析脚本放 scripts/generated/<topic>/，不要放到项目根目录。
- JSON、CSV、TXT、截图、中间结果、分析报告等运行产物放 runtime/<topic>/。
- 非正式日志不要散落在项目根目录；需要保留时放 logs/ 或 runtime/logs/。

## 权限边界

- 代理可以在这个目录下创建和维护独立项目文件。
- 如果某个项目将来需要接入 ComfyUI 上游文件或启动器原区，接入那一步仍然需要用户明确允许后，才能改原区文件。
- 模型文件、LoRA、VAE、embedding、视频素材等大体积资源不要存入这个目录。

## 提交与验证

- 如果某个独立项目进入正式版本管理，commit message 建议使用中文，格式为：<类型>: <一句话中文说明>。
- 若需要 PR 描述，建议按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。
- 每次修改后优先运行最相关的验证命令，例如 python -m py_compile、pytest 或项目自带脚本自检。