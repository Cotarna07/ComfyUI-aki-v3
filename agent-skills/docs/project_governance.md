# 项目治理规范

> 适用于 `agent-skills/` 和 `agent-projects/` 下所有代理协作资产。
> 与 AGENTS.md 配合使用：AGENTS.md 说明权限边界，本文说明放置与扩展规则。

---

## 一、四类资产，先判后放

每次新建文件前，必须先确认归属类型：

| 类型 | 放哪里 | 判定标准 |
|---|---|---|
| **技能层资产** | `agent-skills/comfyui/` | ComfyUI 注册表、工作流模板、跨项目适配器、技能文档 |
| **共享基础能力** | `agent-projects/comfyui-shared/` | 已被 2 个以上不同项目实际复用的逻辑（首次实现先留在业务项目） |
| **独立业务代码** | `agent-projects/<project>/` | 只服务于某一个业务域的代码 |
| **运行产物** | `agent-projects/<project>/runtime/` 或 `agent-skills/comfyui/runtime/` | 图片、JSON 记录、Markdown 报告、日志、快照输入 |

**未判定类型之前，不允许落文件。**

---

## 二、项目域归属表

新需求先找宿主项目，找到就扩展，找不到才新建：

| 业务域 | 宿主项目 | 说明 |
|---|---|---|
| 商品图 / 商品视频 / 营销创意 / 商品验收 | `product-media` | 新批次产物写入 `runtime/`；业务脚本写入 `scripts/` |
| 商品图 VLM 预审核（SKU 特征提取 / 不可改清单） | `product-vlm-review` | 独立 VLM 双模型审核，调用方是 `product-media` |
| 漫画前置预处理（分镜割裂修复） | `manga-panel-fixer` | 修复 picaweb 固定高度切图；输出接 `manga-anime-pipeline` 输入 |
| 漫画动画化（OCR / 分格 / 翻译 / 动画） | `manga-anime-pipeline` | 子功能加模块，不单独建新项目 |
| 漫画流水线参考资源 | `manga-pipeline-reference` | 纯档案库：15 个第三方仓库元数据 + 设计文档；无业务代码，不扩展，只维护 manifest |
| ComfyUI 基础设施（节点体检 / 工作流校验 / 模型清单） | `comfyui-test-harness` | 体检逻辑加模块，不单独建新项目 |
| ComfyUI 实例隔离 / 测试沙箱 | `comfyui-test-instance` | 实例管理逻辑在此；与 `comfyui-test-harness` 配合使用 |
| LM Studio 大模型 × ComfyUI 测评 | `lmstudio-comfyui-benchmark` | 多模型提示词质量 / 速度基准，产物为 CSV 报告 |
| Civitai 模型资源（下载 / 元数据） | `civitai-data-manager` | 下载脚本亦统一归入此项目 |

---

## 三、共享基础能力：晋升门槛

```
首次实现 → 放在第一个使用它的业务项目内部
第二个项目需要同一能力 → 可以晋升到 comfyui-shared
晋升条件：① 接口稳定  ② 无业务专用逻辑  ③ 两个项目均实际调用
```

`comfyui-shared` 目前包含：

- `comfyui_shared.client.ComfyClient` —— ComfyUI HTTP 客户端（stdlib urllib，支持轮询与节点清单）
- `comfyui_shared.json_utils.parse_json_object` —— LLM/VLM 文本 JSON 提取

安装方式（在目标项目 .venv 中）：
```powershell
.venv\Scripts\pip install -e ..\comfyui-shared
```

---

## 四、runtime 目录只放产物

**允许放入 runtime**：
- 图片、视频帧（.png / .jpg / .webp / .mp4）
- JSON 审核记录、验收报告
- Markdown 摘要
- 日志文件（.log）
- 快照输入（供回溯的原图副本）

**禁止放入 runtime**：
- Python 源码（.py）—— 放 `scripts/` 或业务包
- Python 包 / 依赖目录（site-packages 风格）—— 放 `.venv/`
- 第三方插件副本 —— 禁用的 custom node 存档放 `agent-skills/comfyui/disabled-custom-nodes/`
- 可复用脚本 —— 放 `scripts/generated/<topic>/`

---

## 五、`agent-skills/comfyui/runtime/` 只承接技能维护产物

技能层 runtime 主题目录应反映"ComfyUI 技能维护任务"：

| 允许的主题 | 说明 |
|---|---|
| `cms_missing_nodes_smoke/` | 节点兼容性冒烟测试产物 |

以下商品媒体业务产物**后续新批次**统一写入 `agent-projects/product-media/runtime/`：

| 历史保留目录（不移动，只停止写入） | 新批次对应路径 |
|---|---|
| `product_image_optimization/` | `product-media/runtime/product_image/` |
| `product_locked_background/` | `product-media/runtime/locked_background/` |
| `product_image_locked_20260527/` | `product-media/runtime/product_image/` |
| `product_campaign_director_20260527/` | `product-media/runtime/campaign/` |
| `aliexpress_product_optimization_20260527/` | `product-media/runtime/product_image/` |
| `product_video_test/` | `product-media/runtime/product_video/` |
| `chatgpt_hero_video_test/` | `product-media/runtime/product_video/` |
| `creative_kontext_runs/` | `product-media/runtime/campaign/` |

---

## 六、调用 ComfyUI 前的检查顺序

新项目或新模块需要调用 ComfyUI 时，按此顺序检查：

1. 当前项目内是否已有客户端 → 复用
2. `comfyui-shared` 是否已安装 → 使用 `ComfyClient`
3. 都没有 → 参考 [manga-anime-pipeline/pipeline/comfy/client.py](../../agent-projects/manga-anime-pipeline/pipeline/comfy/client.py) 新写，用 stdlib urllib

需要轮询时参考 `comfyui-shared.client.ComfyClient.wait_for_result()`。

---

## 七、接手前任代码的 Owner 查找步骤

1. 搜索 `agent-projects/` 是否有同域宿主项目
2. 搜索该项目内是否有相同功能的模块
3. 搜索 `agent-skills/comfyui/runtime/` 是否有相关主题目录（前任运行记录）
4. 搜索 `scripts/generated/` 是否有可升级复用的实验脚本

找到 owner → 扩展；找不到 → 新建。**不从空白处重写已有逻辑。**

---

## 八、项目模块边界说明要求

每个正式项目的 README.md 必须写明：
- 目标：解决什么问题
- 输入 / 输出
- 依赖的其他项目或共享包
- 可扩展点（哪里加新模块最合适）

---

## 变更记录

| 日期 | 变更内容 |
|---|---|
| 2026-05-27 | 初始版本：提炼自五个项目的重复逻辑分析 |
| 2026-05-27 | `comfyui-test-harness/preflight.py` 去除 requests 依赖，对齐 stdlib urllib |
| 2026-05-27 | `lmstudio-comfyui-benchmark/prompt_quality.py` JSON 提取算法对齐规范版本 |
| 2026-05-27 | `agent-skills/comfyui/runtime/disabled-custom-nodes/` 迁移至 `agent-skills/comfyui/disabled-custom-nodes/` |
| 2026-05-27 | 新建 `agent-projects/comfyui-shared/` 共享基础包 |
| 2026-05-27 | 新建 `agent-projects/product-media/` 商品媒体域宿主项目 |
| 2026-05-27 | 补全项目域归属表：新增 product-vlm-review、manga-panel-fixer、manga-pipeline-reference、lmstudio-comfyui-benchmark、comfyui-test-instance |
