# 视觉验收门禁工作流

## 适用范围

用于 `factual_product` 轨道下的背景生成、前景锁定合成和最终发布验收。目标是
在提高场景与灯光表现力时，主动发现新增商品类物体、配件丢失、悬浮和文字污染。

## 不可替代规则

- VLM 输出只能产生风险证据和重试建议，不能单独批准真实商品发布。
- 底板审查必须发生在商品合成之前；合成后的主体可能遮住背景模型生成的伪物体。
- 规则冲突时按最严格结果处理：任一检测器、VLM 证据字段或人工检查报告禁物，
  即使布尔字段为通过也必须拒绝。
- `factual_product` 优先使用原图像素前景；如果主体被扩散模型重绘，则需要重新
  完成整套身份验收，不能沿用像素锁定的结论。

## 分层门禁

| 阶段 | 输入 | 检查 | 通过后输出 |
|------|------|------|------------|
| 身份清单 | 多张原图 | 类别、轮廓、人物/附件/轮胎数量、颜色与特殊件 | `identity_manifest.json` |
| 前景锁定 | 选定原图、掩膜 | 所有关键部件是否在前景内，边缘是否截断 | `foreground_audit.png`、`mask.png` |
| 背景底板 | 未合成背景 | 是否出现商品、同类物体、配件、包装、文字、logo | 允许合成的 `background_plate.png` |
| 最终合成 | 成片、清单、前景审计图 | 接地、遮挡、伪文字、配件完整性 | `candidate` 或拒绝原因 |
| 发布终验 | 原图与候选图 | 人工逐项核对 | `factual_product` 标签 |

## 背景底板 VLM 提问原则

提问必须具体到商品类目和禁物，不要问泛化的“好不好看”或“是否真实”。例如：

```text
This is an empty background plate before compositing a red brick-built Formula 1 toy car.
Studio walls, floor and lights are allowed. Determine whether the image already contains
any vehicle, racing car, wheel, car body, toy, block-built item, product packaging, text
or logo. Return JSON with has_forbidden_object, objects, locations and evidence.
If any vehicle-like silhouette is visible, has_forbidden_object must be true.
```

解析时不得仅依赖 `has_forbidden_object`。如果 `objects` 或 `evidence` 提到
禁物，也必须按失败处理。

## 重试路由

| 发现问题 | 回退阶段 | 操作 |
|----------|----------|------|
| 背景出现另一辆车/人仔/玩具 | 背景生成 | 更换 seed，收紧负提示词，必要时退回空棚 |
| 商品悬浮或台面透视错误 | 选图/背景/阴影 | 选择落地视角；改台面布局和接触阴影 |
| 小配件未进入掩膜 | 前景锁定 | 换清晰原图或用分割工具细化掩膜 |
| 主体被模型重绘 | 路线选择 | 拒绝真实展示标签，回退到锁前景流程 |
| 候选出现文本/包装伪造 | 背景生成或遮罩 | 禁止发布，重新生成无文案场景 |

## 本机执行约束

RTX 5070 Ti 16 GB 下，扩散生成与 Qwen3-VL 审查不得并行驻留。执行次序为：

```text
ComfyUI 生成 -> /free 释放模型 -> VLM 审查 -> 合成/重试 -> /free -> 最终审查
```

本机先验证高质量路线是否可用；需要更大视觉模型或生成模型时，将同一验收规则
带到云端，不通过降低生成质量来规避显存压力。
