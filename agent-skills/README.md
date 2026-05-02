# agent-skills 目录说明

这个目录只负责跨代理技能层，不再作为所有 agent 生成文件的总兜底目录。

## 这个目录适合放什么

- comfyui/
  放 ComfyUI 专用技能资产、工作流导出、兼容性说明、自动化入口与复用规则。
- docs/
  放技能包说明、技能层规则、ComfyUI 自动化相关文档。
- scripts/
  放技能层辅助脚本、适配器或小工具。
- runtime/
  放技能层运行过程产生的中间结果、日志或可复用产物。

## 这个目录不该放什么

- 独立 Python 项目
- 独立 Web、CLI 或服务项目
- 与技能层无关的通用实验代码
- 模型权重、LoRA、VAE、embedding、大体积视频素材

## 分流规则

- 独立项目一律放到 agent-projects/<project-slug>/。
- 只有和技能层直接耦合、需要跨代理复用的资产，才放到 agent-skills/。
- 模型文件默认留在 ComfyUI/models/ 或 ComfyUI/extra_model_paths.yaml 指向的外部目录。
- ComfyUI/ 上游仓库默认只读；没有用户明确允许，不要改 agent-skills/ 之外的原项目文件。
- 人类可读文档默认使用简体中文，除非用户明确要求别的语言。

## 文档与临时文件规则

- 优先更新已有技能文档，不创建重复说明、历史副本或“新版说明 / 旧版说明”并存文件。
- 技能层总结文档只在用户明确要求“总结 / 沉淀”时新增，建议放在 agent-skills/docs/，命名格式为 YYYY-MM-DD_简要内容.md。
- 一次性排查脚本、实验脚本、临时分析脚本放在 agent-skills/scripts/generated/<topic>/，不要堆到根目录。
- JSON、TXT、CSV、截图、分析记录等中间产物不要散落在根目录；如需保留，放到对应 topic 子目录。

## 例子

- 新的 ComfyUI 自动化说明、API 工作流导出、兼容性笔记应放在 agent-skills/comfyui/。
- 技能包说明与自动化规则应放在 agent-skills/docs/。
- 技能层补丁脚本和适配器应放在 agent-skills/scripts/。
- 新的批处理 Python 工具、独立实验项目或完整应用应放在 agent-projects/<project-slug>/。