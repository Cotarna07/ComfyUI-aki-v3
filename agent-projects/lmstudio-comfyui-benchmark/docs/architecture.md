# 全自动测评方案设计

## 流程

1. 启动后读取 TOML 配置，创建 `runtime/<run_id>/`。
2. 检查 LM Studio `/models` 与 ComfyUI `/system_stats` 可访问性。
3. 对每个 `model x parameters` 组合调用 LM Studio `/chat/completions`。
4. 记录原始响应、耗时、completion tokens、tokens/sec。
5. 提取 `positive_prompt`、`negative_prompt`、`notes`，并用固定规则计算质量分。
6. 按配置顺序把提示词注入同一个 ComfyUI API workflow。
7. 轮询 `/history/<prompt_id>`，写入每张图的任务状态。
8. 导出 `summary.csv`，供次日按模型、参数、速度、质量和出图状态对比。

## 控制变量

- 所有模型共享同一条 `fixed_instruction`。
- ComfyUI 使用同一个 API workflow。
- 出图参数通过 `[comfyui.overrides]` 固定，包括 seed、尺寸、steps、cfg、sampler 等。
- 模型侧只改变 `model` 与 `[[parameters]]` 中的采样参数。

## 无人值守能力

- 每个模型调用与 ComfyUI 出图任务都有超时和重试。
- `checkpoint.json` 保存已完成的 LLM 组合和 ComfyUI 任务，重复运行会自动跳过。
- 结果采用 JSONL 增量写入，程序中断后不会丢失已经完成的记录。
- 单个模型失败会记录为 failed，不阻断后续模型。

## 质量评分

当前版本使用可解释的启发式评分，满分 100：

- JSON / 字段可解析：20
- 正面提示词长度达标：15
- 负面提示词长度达标：10
- 正面提示词包含配置要求词：20
- 负面提示词包含配置要求词：15
- 提示词像逗号分隔的可用 tag：10
- 英文比例与重复度健康：10

这个评分只用于自动筛选和横向排序，最终视觉效果仍以 ComfyUI 出图结果为准。

## 产物

- `llm_results.jsonl`：每次模型输出和评分。
- `image_jobs.jsonl`：每次 ComfyUI 提交、prompt_id、状态和 history 摘要。
- `summary.csv`：次日优先查看的汇总表。
- `checkpoint.json`：续跑依据。
- `run.log`：排查长时间运行失败原因。

## 后续可扩展

- 增加多条固定场景，但每轮仍保持所有模型使用同一场景。
- 增加人工评分 CSV 回填字段，用于合并自动分和人工视觉分。
- 增加 HTML 报告，把提示词、速度、评分和出图文件缩略图放到同一页面。
