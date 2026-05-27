# 本轮已验证模式与失败经验

## 基线环境

- 实测日期：`2026-05-26` 至 `2026-05-27`
- 本机服务：ComfyUI `0.20.1`
- 本机设备：`NVIDIA GeForce RTX 5070 Ti`，约 `16 GB VRAM`
- 已运行静态基线：`Flux.1 Kontext FP8`
- 共用静态测试参数：`steps=28`、`cfg=1.0`、`sampler=euler`、`scheduler=simple`，guidance 主要为 `2.8`

完整测试记录与精确输出位置见 `agent-skills/docs/2026-05-26_产品图展示视频排障优化报告.md`。

## 结果模式

| 素材特征 | 可靠做法 | 已观察风险 |
|----------|----------|------------|
| 白底完整套装 | 保持全套摆位，只改地面、背景、夕阳灯光与接触阴影 | 提示词要求角色行动后会重排套装 |
| 红色亮色载具已有环境图 | 去文字后换为湿地赛道/广告灯光 | 仍需检查车翼、轮毂与砖块外形 |
| 包装与产品同图 | 尽量换用干净产品图；否则只作为创意图输入 | 配件可能被模型删减 |
| 深灰/黑色载具 | 先裁去文案，采用浅色雨后平台与柔和明亮光 | 夜景压黑；过度提亮会重绘为真实车辆 |
| 角色关系或动作海报 | 明确标为 `creative_campaign` | 人物/怪物常被替换为通用卡通造型 |

## 已验证输出示例

| 输出 | 轨道建议 | 经验 |
|------|----------|------|
| `ComfyUI/output/agent_tests/product_image_crossset/kontext_racecar_00001_.png` | 真实展示候选，仍需细查车体 | 湿地反射与低机位适合亮色载具 |
| `ComfyUI/output/agent_tests/product_image_crossset/kontext_outpost_00001_.png` | 真实展示候选 | 干净白底整套输入对保真最友好 |
| `ComfyUI/output/agent_tests/product_image_crossset/kontext_spaceship_00001_.png` | 创意广告主视觉 | 场景出色但配件完整性不足 |
| `ComfyUI/output/agent_tests/product_image_crossset/kontext_armored_car_cropped_locked_00001_.png` | 真实展示候选，需逐件核验 | 文案裁切与亮背景有助于深色产品 |
| `ComfyUI/output/agent_tests/product_image_crossset/kontext_armored_car_daylight_00001_.png` | 拒绝 | 变成近似真实装甲车，属于结构/材质漂移 |
| `ComfyUI/output/agent_tests/product_image_local_quality/bright_action_poster_00001_.png` | 创意广告主视觉 | 广告感增强，但角色和积木材质漂移 |

## 提示词模式

真实展示提示词应包含四块内容：

```text
Preserve the same recognizable [product]: keep [silhouette, color, components, quantity and relationships].
Edit only [background / floor / lighting / non-product graphic removal].
Keep the product bright, sharp and clearly [material]-built with grounded contact shadows.
Do not add, remove, redesign, reposition, recolor, change material, generate text, packaging, logo overlay or watermark.
```

创意主视觉提示词可以描述叙事、动作与镜头，但必须另存并标注：

```text
creative_campaign; not for factual SKU verification
```

## 工作流选择经验

- `Flux.1 Kontext FP8` 在本机可进行一分钟级静态迭代，适合验证产品图方向和提示词边界。
- SDXL 乐高/塑料玩具 LoRA 是独立创意生成分支，不能挂到 Kontext 或 Qwen Image Edit 后比较。
- 本机下一项编辑 A/B 候选为 `Flux.2 Klein 4B`；云端大模型仅在本机已证实路线有效后用于提高同路线质量上限。
- 对视频，不让积木主体主动运动；优先使用通过真实性验收的静态主视觉做推拉、景深、光雾、粒子与剪辑。

## 2026-05-27 锁前景与视觉门禁实测

- 新路线：`RMBG-2.0` 抽取前景，SDXL 仅生成背景，再以原商品像素合成并生成柔和接触阴影。
- 优点：Creeper 的 TNT 与粉色小角色、警车的人仔、魔法教室的三名角色和瓶罐、两辆赛车的完整车体均可保留，不再由生成模型重新发明。
- 风险：`staged` 展示背景仍可能生成商品类伪物体；F1 的底板曾出现额外黑色汽车，属于 `factual_product` 一票否决。
- 风险：原素材构图呈俯视或悬浮展示时，即使主体像素锁定，合成图仍会显得悬浮。此类问题应更换原图视角或背景承托关系，而不是重画商品。
- VLM 结论：本机 `Qwen3-VL` 对“原图 + 最终 F1 合成图”的宽泛验收曾漏判额外汽车；对独立背景底板提出聚焦禁物问题时，能检出该汽车，并将普通空棚判为无车辆。
- 流程规则：背景底板验收先于合成；VLM 证据与布尔字段冲突时严格拒绝；发布前仍保留人工逐项核验。
- 显存规则：本机 16 GB 下，ComfyUI 背景生成与 Ollama VLM 审查需错峰执行，生成后先调用 `/free` 再运行审查。

## 2026-05-27 多视角 VLM 导演层与警车创意镜头实测

- 输入商品：`1005007109462323`，LEGO City 警车；源图 `01` 至 `06`，并以四张网页端成片仅作为广告风格参照。
- 分析模型：本机 Ollama `huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M`。新增脚本
  `agent-skills/scripts/generated/product-image-optimizer/direct_product_campaign_vlm.py`，
  分三段执行：逐张源图事实抽取、风格参照摘要、带确定性门禁的镜头规划。
- 证据收益：VLM 正确识别 `02.jpg` 为“警员已坐在车内，并且白色车顶/蓝色警灯模块悬浮拆开展示”；
  `03.jpg` 与 `04.jpg` 则为警员在车外、车顶已安装。因而“车内警员 + 拆顶功能镜头”不是网页端凭空改造，
  而是可以从原始销售图取证后进入创意主视觉分支。
- 门禁要求：`factual_product` 必须保持单一源图中的视角、人物位置和装配状态；包装与规格图只能作为
  验证或确定性排版来源，不能让编辑模型重画。新增生成桥
  `agent-skills/scripts/generated/product-image-optimizer/render_directed_kontext_campaign.py`
  只接收 `creative_campaign` brief，向其传入保真 brief 时会拒绝执行。
- 已观察 VLM 局限：一次宽泛提问曾漏掉 `02` 的拆顶状态，拆分为聚焦问题后能读出；对 `06` 包装小字曾
  误读出 `999` 件，与 `01` 清晰可见的 `94` 件冲突，脚本会生成需人工复核的规格警告；对创意输出中
  残留的白色拆解箭头也曾漏判，发布终验仍需人工查看。
- 工作流修复：`kontext_product_edit.json` 曾误用 `EmptyFlux2LatentImage` 运行 `Flux.1 Kontext FP8`，
  警车测试实际只输出 `512x512`；改为 `EmptySD3LatentImage` 后，同类任务恢复为 `1024x1024`。
- 创意输出：
  `ComfyUI/output/agent_runs/vlm_directed_campaign_20260527/1005007109462323/rain_city_feature_exploded_inside_fixed_latent_00001_.png`
  与 `.../rain_city_feature_exploded_inside_bright_clean_00001_.png`。两张均保留了车内警员和悬浮车顶的主要
  可识别关系，并生成雨夜路面与光斑氛围；仍存在偏暗、箭头污染或材质精细度低于网页端结果的问题。
- 结论：VLM 导演层能够减少选错视角和虚构产品状态的问题，修复 latent 节点能恢复基础分辨率；但
  `Flux.1 Kontext FP8` 仍不足以达到网页端在镜头亮度、清洁编辑、材质统一和商业成片感上的上限。
  下一项本机生成 A/B 应测试更强编辑模型，而不是继续仅靠提示词压榨同一模型。
