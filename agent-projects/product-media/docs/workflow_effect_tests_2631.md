# 26-5-31 工作流效果测试方案

本方案面向 `agent-skills/comfyui/workflows/TEST/26-5-31` 下导入的 UI 工作流。测试目标是“效果优先，但不把商品事实改错”：同一批产品先建立可复跑的测试矩阵，再由脚本转换 API、生成提示词、提交队列和沉淀报告。

## 当前结论

- 这些文件不是原生 API 工作流；脚本会通过 ComfyUI `/workflow/convert` 转换后再测试。
- `image_flux2_klein_image_edit_4b_distilled.json` 是当前最适合先测的整图编辑路线。它需要裁剪到 `SaveImage 9` 分支，并把 VAE 改为 `FLUX2\flux2-vae.safetensors`。
- `locked_foreground_baseline` 是真实性基线：用 RMBG 抠出商品前景，只换程序化背景，不重绘商品像素。
- `templates-qwen_image_edit-crop_and_stitch-fusion.json` 暂不作为默认测试路线：本地还缺 Qwen Image Edit 主模型、Fusion LoRA 或模型位置整理。脚本会把“目标目录缺失但在别处找到”的模型写进 `found_elsewhere`，例如 LoRA 被放在 `diffusion_models` 时会明确标出。
- `image_flux2_fp8.json` 暂不作为默认测试路线：本地缺 Flux2 full route 的主模型和 LoRA。
- 两个 LTX workflow 是视频字幕/水印处理方向，不适合静态商品图优化首轮测试。
- `gsl_starter_1_3.json` 转换后的 API 图很小，主流程处于折叠/绕过状态，默认只做诊断记录。

## VLM 提示词设计

批量产品图差异较大时，VLM 生成专属优化提示词是必要功能。原因不是为了“放权给模型判断成片好坏”，而是为了高效抽取每个产品的事实约束：

- 商品身份、主色、材质、轮廓。
- 必须保留的配件、人物、透明件、印刷/贴纸、数量和相对位置。
- 允许强化的场景、灯光和镜头语言。
- 不得用于真实商品展示的创意改动。

脚本支持 `--use-vlm`，默认使用 `product-vlm-review` 的 Ollama Qwen3-VL 接口逐图识别，并按产品缓存到：

```text
agent-projects/product-media/runtime/product_image/<batch_id>/vlm/
agent-projects/product-media/runtime/product_image/<batch_id>/prompts/
```

同一产品只识别一次，多个工作流、多个 seed 复用同一份 prompt plan。需要重新识别时再加 `--refresh-vlm`。

如果不用 VLM，脚本会生成保守通用提示词：强调只改背景、地面、光影和接触阴影，不允许增删配件、改颜色、改材质、改结构或生成文字。

## 自动选源（多图列表）

速卖通商品常有多张列表图，且多为带营销文字/角标/包装盒的拼图。脚本新增 `select` 阶段：用 qwen3-vl 给每个商品的候选图打分，自动挑出"成品占比大、无压字遮挡、非包装盒/拼图"的一张做主图原料，按产品缓存到 `<batch>/source_select/`。

- 商品在 `test_plan` 写 `auto_select_source: true` 且只给 `images`（不钉 `primary_image`）即自动选源；命中后多工作流多 seed 复用。
- 开关：`--select-source` 强制 / `--no-select-source` 关闭 / `--refresh-source` 忽略缓存。
- 选源前会把候选图缩到 768 长边再喂模型，避免多图 + 长提示撑爆 Ollama 上下文。
- 真实测试结果与坑见 `docs/2026-05-31_工作流效果测试交接.md`（locked 基线零漂移、flux2 整图重绘会加人偶/虚构包装、16GB 卡 Ollama 与 ComfyUI 抢显存）。

## 一键脚本

脚本位置：

```powershell
agent-projects/product-media/scripts/test_2631_workflows.py
```

先生成默认测试计划：

```powershell
D:\ComfyUI-aki-v3\.venv\Scripts\python.exe .\agent-projects\product-media\scripts\test_2631_workflows.py `
  --init-plan .\agent-projects\product-media\runtime\product_image\workflow_effect_tests_20260531\test_plan.json
```

只做预检和准备，不提交生成：

```powershell
D:\ComfyUI-aki-v3\.venv\Scripts\python.exe .\agent-projects\product-media\scripts\test_2631_workflows.py `
  --plan .\agent-projects\product-media\runtime\product_image\workflow_effect_tests_20260531\test_plan.json `
  --stage all `
  --dry-run
```

正式一键测试并等待脚本收集输出：

```powershell
D:\ComfyUI-aki-v3\.venv\Scripts\python.exe .\agent-projects\product-media\scripts\test_2631_workflows.py `
  --plan .\agent-projects\product-media\runtime\product_image\workflow_effect_tests_20260531\test_plan.json `
  --stage all
```

启用批量 VLM 专属提示词：

```powershell
D:\ComfyUI-aki-v3\.venv\Scripts\python.exe .\agent-projects\product-media\scripts\test_2631_workflows.py `
  --plan .\agent-projects\product-media\runtime\product_image\workflow_effect_tests_20260531\test_plan.json `
  --stage all `
  --use-vlm
```

只排队、不等待输出：

```powershell
D:\ComfyUI-aki-v3\.venv\Scripts\python.exe .\agent-projects\product-media\scripts\test_2631_workflows.py `
  --plan .\agent-projects\product-media\runtime\product_image\workflow_effect_tests_20260531\test_plan.json `
  --stage all `
  --no-wait
```

## 验收口径

- `factual_product`：任何关键结构、配件数量、颜色、材质、人物/配件关系、印刷、比例变化都判为失败。
- `creative_campaign`：允许更强叙事和场景，但必须标注为创意广告图，不能替代真实商品展示。
- VLM 可以提高批量提示词和风险初筛效率，但不能单独放行真实商品图；最终仍要对照原图验收。
