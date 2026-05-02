# agent-skills/comfyui 说明

这个目录用于存放跨代理可复用的 ComfyUI 自动化资产与协作规则，用来和 ComfyUI 上游仓库本体区分。

## 适合放什么

- API 工作流导出文件
- 工作流覆写规则、节点兼容性记录、提示词模板
- 与本机 ComfyUI 运行方式直接相关的自动化说明
- 供多个 agent 复用的 ComfyUI 小工具或适配脚本说明

## 不适合放什么

- ComfyUI 官方源码或插件源码副本
- 模型权重、LoRA、VAE、embedding
- 大体积输入素材、输出视频或长期缓存

## 本机边界说明

- ComfyUI/ 目录是上游仓库，自带独立 Git 仓库边界；默认读多写少，除非用户明确允许。
- 模型与大体积素材优先留在 ComfyUI/models/ 或 ComfyUI/extra_model_paths.yaml 指向的外部路径中。
- 如果后续需要整理可重复执行的 API 工作流，导出文件放在 agent-skills/comfyui/workflows/api/。
- 在假设模型路径前，先检查 ComfyUI/extra_model_paths.yaml、启动器配置或当前实际模型目录，不要直接照搬其他机器的盘符。

## 运行与性能假设

- 设备按 Intel Core Ultra 7 265K 同级 CPU、RTX 5070 Ti 同级 GPU、16GB VRAM、64GB RAM 规划。
- 重推理流程默认按 GPU-first 设计，不要静默回退到 CPU。
- 长视频处理默认考虑分段、缓存和可重入。
- 设计工作流时优先兼顾显存约束与本地稳定运行。

## 推荐习惯

- 优先把可重复执行流程整理成 API 工作流，而不是依赖手工 UI 操作。
- 新的技能层脚本先放 agent-skills/scripts/generated/<topic>/，确认长期复用后再提升为正式脚本。
- 需要说明操作边界时，先更新本目录说明或 agent-skills/README.md，而不是在根目录重复写一份新文档。