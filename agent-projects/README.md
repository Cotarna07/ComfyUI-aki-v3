# agent-projects 目录说明

这个目录是后续与 Copilot、Codex 或其他 agent 协作生成独立项目代码的专用区，用来和秋叶启动器原区、agent-skills 技能层分开。

## 使用方式

- 每个独立项目单独建一个子目录，统一使用 agent-projects/<project-slug>/。
- 未来的新 Python 项目默认建在这里，不要再放进 agent-skills/。
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
- 人类可读文档默认使用简体中文，除非用户明确要求其他语言。

## 临时文件与运行产物

- 一次性排查脚本、实验脚本、临时分析脚本放 scripts/generated/<topic>/，不要放到项目根目录。
- JSON、CSV、TXT、截图、中间结果、分析报告等运行产物放 runtime/<topic>/。
- 非正式日志不要散落在项目根目录；需要保留时放 logs/ 或 runtime/logs/。
- 当脚本已经参数化、补齐说明并确认会长期复用时，再从 scripts/generated/ 提升到 scripts/ 或正式模块目录。

## 权限边界

- 代理可以在这个目录下创建和维护独立项目文件。
- 如果某个项目将来需要接入秋叶启动器原文件，接入那一步仍然需要用户明确允许后，才能改原区文件。
- 如果某个项目要做单独版本管理，可以在项目子目录内单独初始化 Git，也可以继续使用当前 overlay Git 白名单。

## 命名建议

- 目录名尽量使用清晰的短横线风格，例如 video-batch-tools、prompt-lab、dataset-cleaner。
- 同一类实验如果准备长期维护，不要继续堆在同一个目录里，直接拆成新的项目子目录。

## 提交与验证

- 如果某个独立项目进入正式版本管理，commit message 建议使用中文，格式为：<类型>: <一句话中文说明>。
- 若需要 PR 描述，建议按“背景 / 修改内容 / 验证方式 / 风险与回滚”四段组织。
- 每次修改后优先运行最相关的验证命令，例如 python -m py_compile、pytest 或项目自带脚本自检。

## 归档原则

- 技能包共用资产回收到 agent-skills/。
- 独立项目自己的代码、测试、文档留在各自项目目录。
- 只要一个文件主要服务于某个独立项目，就不要再塞回 agent-skills/。