# agent-skills 目录说明

这个目录只负责跨代理技能层，不再作为所有代理生成文件的总兜底目录。

## 这个目录适合放什么

- comfyui/
  放 ComfyUI 专用资产，比如注册表、技能规则、API 工作流导出文件，以及和本地 Aki 包直接耦合的自动化元数据。
- docs/
  放技能包说明、技能层规则、ComfyUI 自动化相关文档。
- scripts/
  放技能层辅助脚本、适配器或小工具。

## 这个目录不该放什么

- 独立 Python 项目
- 独立 Web、CLI 或服务项目
- 与技能层无关的通用实验代码
- 只服务某个新项目的项目内文档、测试和脚本

## 分流规则

- 独立项目一律放到 agent-projects/<project-slug>/。
- 只有和技能层直接耦合、需要跨代理复用的资产，才放到 agent-skills/。
- 现有根目录兼容入口文件不是后续新增文件的默认落点。
- 秋叶启动器原区默认只读；没有用户明确允许，不要改 agent-skills/ 之外的原项目文件。
- 人类可读文档默认使用简体中文，除非用户明确要求别的语言。

## 文档与临时文件规则

- 优先更新已有技能文档，不创建重复说明、历史副本或“新版说明 / 旧版说明”并存文件。
- 技能层总结文档只在用户明确要求“总结 / 沉淀”时新增，建议放在 agent-skills/docs/，命名格式为 YYYY-MM-DD_简要内容.md。
- 一次性排查脚本、实验脚本、临时分析脚本放在 agent-skills/scripts/generated/<topic>/，不要堆到根目录。
- JSON、TXT、CSV、截图、分析记录等中间产物不要散落在根目录；如需保留，放到对应 topic 子目录，稳定后再迁移到 docs/、scripts/ 或 comfyui/ 正式位置。
- 只有在脚本已经参数化、补齐说明并确认会长期复用时，才从 generated 目录提升到 agent-skills/scripts/ 或 agent-skills/comfyui/。

## 例子

- 新的技能注册表或 API 工作流导出应放在 agent-skills/comfyui/。
- 技能包说明、插件路线或自动化说明应放在 agent-skills/docs/。
- 技能层补丁脚本和适配器应放在 agent-skills/scripts/。
- 新的批处理 Python 工具、独立实验项目或完整应用应放在 agent-projects/<project-slug>/。