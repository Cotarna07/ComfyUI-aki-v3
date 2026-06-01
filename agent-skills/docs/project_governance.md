# 项目治理规范

> 适用于 `agent-skills/` 和 `agent-projects/` 下所有代理协作资产。
> 与 AGENTS.md 配合使用：AGENTS.md 说明权限边界，本文说明放置与扩展规则。

---

## 零、目录结论：不合并

`agent-skills/` 和 `agent-projects/` 不合并。它们解决的是两类问题：

- `agent-skills/` 是技能层：放跨代理规则、ComfyUI 注册表、工作流模板、技能维护脚本和技能维护产物。
- `agent-projects/` 是项目层：放独立业务项目、项目代码、项目测试、项目文档和项目运行产物。

两者通过引用协作，而不是通过合并目录协作。典型关系是：项目代码调用 `agent-skills/comfyui/workflows/` 里的模板，项目产物仍写入自己的 `runtime/`。

判断时先问一句：这个文件离开某个业务项目后是否仍然是跨项目技能资产？

- 是：放 `agent-skills/`。
- 否：放对应的 `agent-projects/<project>/`。

例如，WAN2.2/CMS 工作流拆解、节点兼容测试、模型/LoRA 参数矩阵属于 ComfyUI 技能维护，可以放 `agent-skills/scripts/generated/<topic>/` 与 `agent-skills/comfyui/runtime/<topic>/`。速卖通商品图优化、商品视频、营销图和真实性验收属于商品媒体业务，放 `agent-projects/product-media/`。

---

## 一、四类资产，先判后放

每次新建文件前，必须先确认归属类型：

| 类型 | 放哪里 | 判定标准 |
|---|---|---|
| **技能层资产** | `agent-skills/` | ComfyUI 注册表、工作流模板、技能规则、节点/模型/工作流维护测试 |
| **共享基础能力** | `agent-projects/comfyui-shared/` | 已被 2 个以上不同项目实际复用的逻辑（首次实现先留在业务项目） |
| **独立业务代码** | `agent-projects/<project>/` | 只服务于某一个业务域的代码 |
| **运行产物** | `agent-projects/<project>/runtime/` 或 `agent-skills/comfyui/runtime/` | 项目产物进项目 runtime；技能维护产物进技能 runtime |

**未判定类型之前，不允许落文件。**

### 工作流总目录管理规则（命名约定即权限边界）

ComfyUI 工作流统一以 `agent-skills/comfyui/workflows/` 作为总入口。**目录命名前缀决定管理权归属**：

| 前缀 | 归属 | 代理权限 | 说明 |
|------|------|----------|------|
| `01-shared/` | 代理管理区 | 可读写 | 跨项目复用、已验证、可直接自动化调用的正式模板 |
| `02-project/<project>/` | 代理管理区 | 可读写 | 仅服务某个项目的稳定模板与 mapping |
| `03-source/` | 代理管理区 | 可读写 | 外部导入、供应商示例、UI 草稿、待整理生成稿、历史归档 |
| **其他所有顶层目录/文件** | **用户区** | **只读** | 用户自行创建的任何目录和文件 |

**用户区规则**（适用于 `workflows/` 下所有不以 `0` 开头的顶层目录和文件）：

- 代理**可以读取**用户区内容，用于了解上下文
- 代理**不得**在用户区新建、删除、移动、重命名任何文件或目录
- 代理**不得**将用户区的文件"整理"到管理区
- 只有用户**明确指示**操作某个用户区路径时，代理才可执行
- 用户新建的任何目录自动受此规则保护，无需更新本文档
- 代理自己的新测试工作流不要继续写入 `TEST/`、`api/`、`imported/` 等用户区；草稿写入 `03-source/drafts/<topic>/`，外部导入写入 `03-source/imported/<topic>/`，稳定项目模板写入 `02-project/<project>/`

当前已知用户区目录（示例，非完整列表）：`TEST/`、`api/`、`imported/`

**管理区内部规则**：

- `01-shared/`：新导出的共享 API 工作流直接进入；晋升自 `03-source/` 的成熟模板
- `02-project/<project>/`：项目独占模板，子目录按项目名命名
- `03-source/` 内部结构：
  - `vendor/<source>/`：第三方供应商工作流
  - `imported/<topic>/`：从外部导入的社区工作流，按主题分目录
  - `drafts/`：草稿与待整理

补充约束：

- `example_workflows/` 这类目录如果被 ComfyUI 或 custom node 直接扫描，原位可保留兼容入口，但规范化后的管理副本仍进入总目录。
- 项目代码若需要固定引用工作流，应指向总目录中的 canonical 路径，而不是继续向项目内部新增平行模板副本。
- `runtime/`（位于 `agent-skills/comfyui/runtime/`）不再作为正式工作流模板的长期存放位置。

---

## 二、项目域归属表

新需求先找宿主项目，找到就扩展，找不到才新建：

| 业务域 | 宿主项目 | 说明 |
|---|---|---|
| 商品图 / 商品视频 / 营销创意 / 商品验收 | `product-media` | 新批次产物写入 `runtime/`；业务脚本写入 `scripts/` |
| 商品图 VLM 预审核（SKU 特征提取 / 不可改清单） | `product-vlm-review` | 独立 VLM 双模型审核，调用方是 `product-media` |
| ComfyUI 工作流拆解 / 节点兼容 / 模型参数矩阵 | `agent-skills/comfyui/` + `agent-skills/scripts/generated/<topic>/` | 技能维护任务；若演变为长期测试平台，再迁入 `comfyui-test-harness` |
| 漫画前置预处理（分镜割裂修复） | `manga-panel-fixer` | 修复 picaweb 固定高度切图；输出接 `manga-anime-pipeline` 输入 |
| 漫画动画化（OCR / 分格 / 翻译 / 动画） | `manga-anime-pipeline` | 子功能加模块，不单独建新项目 |
| 漫画流水线参考资源 | `manga-pipeline-reference` | 纯档案库：15 个第三方仓库元数据 + 设计文档；无业务代码，不扩展，只维护 manifest |
| ComfyUI 基础设施（节点体检 / 工作流校验 / 模型清单） | `comfyui-test-harness` | 体检逻辑加模块，不单独建新项目 |
| ComfyUI 实例隔离 / 测试沙箱 | `comfyui-test-instance` | 实例管理逻辑在此；与 `comfyui-test-harness` 配合使用 |
| LM Studio 大模型 × ComfyUI 测评 | `lmstudio-comfyui-benchmark` | 多模型提示词质量 / 速度基准，产物为 CSV 报告 |
| Civitai 模型资源（下载 / 元数据） | `civitai-data-manager` | 下载脚本亦统一归入此项目 |

### ComfyUI 多环境例外

`comfyui-test-instance` 的 `runtime/environments/` 是测试实例运行根目录，允许包含 `.venv`、`custom_nodes` Junction、独立 `user/input/output/temp/logs` 与共享 `models` Junction。这是为了隔离 ComfyUI 节点依赖和端口，不按普通业务 runtime 的“只放产物”规则处理。

环境名称、端口、插件集合和 Python 策略统一登记在 `agent-projects/comfyui-test-instance/config/environments.json`。后续 agent 不要临时发明端口或环境名。

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
| `cms_wan22_loop_matrix/` | WAN2.2/CMS 工作流参数、模型和 LoRA 矩阵测试报告 |
| `workflow_api_validation/<topic>/` | API 工作流导出、图结构校验和自动化提交验证产物 |
| `model_inventory/<topic>/` | 模型清单、缺失模型检查和节点可用性记录 |

如果主题产物开始服务某个业务项目，而不是维护工作流或技能层，应从下一批次起迁入对应项目的 `runtime/`。

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
