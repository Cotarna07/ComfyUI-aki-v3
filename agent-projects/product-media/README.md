# product-media

商品媒体域宿主项目。负责电商商品图优化、商品视频生成、营销创意广告视觉的**自动化代码与运行产物**统一管理。

## 职责范围

| 子域 | 说明 |
|---|---|
| 商品图优化 | 背景重绘、主体保留、多场景适配 |
| 商品视频 | 关键帧生成、Hero 视频、产品展示视频 |
| 营销创意 | 创意广告主视觉、Campaign Director |
| 商品真实性验收 | 与 `product-vlm-review` 对接，存放验收报告 |

## 与其他项目的边界

| 项目 | 关系 |
|---|---|
| `product-vlm-review` | 提供 VLM 事实核验能力；本项目调用它，验收报告存入 `runtime/inspection/` |
| `comfyui-shared` | 调用 ComfyUI 时使用共享客户端 |
| `agent-skills/comfyui/` | 工作流模板来源；本项目不再复制工作流文件 |

## 目录结构

```
product-media/
├── runtime/                    # 运行产物（图片/视频/记录/报告）
│   ├── product_image/          # 商品图优化批次
│   │   └── <batch_id>/
│   │       ├── outputs/        # 生成图
│   │       ├── inspection/     # VLM 验收记录
│   │       └── records/        # 运行 JSON 记录
│   ├── product_video/          # 商品视频批次
│   │   └── <batch_id>/
│   ├── campaign/               # 营销创意批次
│   │   └── <sku_id>/
│   │       └── <batch_id>/
│   └── locked_background/      # 固定背景板素材
├── scripts/                    # 可复用的自动化脚本
│   └── generated/              # 实验/一次性脚本
└── docs/                       # 项目内说明文档
```

## 现有产物说明

以下历史批次仍保留在 `agent-skills/comfyui/runtime/`，后续新批次统一写入本项目 `runtime/`：

| 历史目录 | 对应本项目路径 |
|---|---|
| `agent-skills/comfyui/runtime/product_image_optimization/` | `runtime/product_image/` |
| `agent-skills/comfyui/runtime/product_locked_background/` | `runtime/locked_background/` |
| `agent-skills/comfyui/runtime/product_image_locked_20260527/` | `runtime/product_image/20260527/` |
| `agent-skills/comfyui/runtime/product_campaign_director_20260527/` | `runtime/campaign/20260527/` |
| `agent-skills/comfyui/runtime/aliexpress_product_optimization_20260527/` | `runtime/product_image/aliexpress_20260527/` |
| `agent-skills/comfyui/runtime/product_video_test/` | `runtime/product_video/` |
| `agent-skills/comfyui/runtime/chatgpt_hero_video_test/` | `runtime/product_video/hero_test/` |
| `agent-skills/comfyui/runtime/creative_kontext_runs/` | `runtime/campaign/kontext/` |

## 脚本（scripts/）

| 脚本 | 方法 | 何时用 |
|---|---|---|
| `lock_foreground_compose.py` | RMBG-2.0 抠出商品原始像素 + 程序化影棚背景 + 合成接触阴影（`compose`/`detext` 两模式） | **默认方法**，尤其结构复杂、贴纸密集的 SKU（赛车、机甲等）。主体不重绘→保真无幻觉 |
| `optimize_product_images.py` | Flux.1 Kontext FP8 整图编辑 API 执行器 | 仅结构简单 SKU 的换背景，或明确标注的 `creative_campaign`。复杂结构会被熔化，勿用于真实展示 |

两者都用 jobs-file 驱动：`python <脚本> <jobs.json>`。jobs 示例见
`runtime/product_image/ferrari_sf24_20260527/jobs.json`（Kontext）与 `jobs_compose.json`（前景锁定）。
方法选型与失败经验见 `agent-skills/comfyui/skills/comfyui-product-image-integrity/references/tested-patterns.md`。

## 商品图质量规则

参见 `agent-skills/comfyui/skills/comfyui-product-image-integrity/SKILL.md`。

核心约束：
- 创意广告图与真实商品展示图必须明确区分
- 真实展示图的 SKU、配件数量、结构与包装须与原图一致
- 出现结构/配件/材质/颜色不一致时，必须标注为"创意广告图，不可用于实物核验"
