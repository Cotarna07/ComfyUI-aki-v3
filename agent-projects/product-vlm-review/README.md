# 商品图双 VLM 复核工具

本项目用于在商品图创意优化之前，使用两个视觉语言模型读取原始 SKU
图片，输出可核验的事实、允许进行的场景创意和不得改动的商品特征。
当前接入：

- `Qwen3-VL 8B`：复用本机 Ollama 中已安装的
  `huihui_ai/qwen3-vl-abliterated:8b-instruct-q4_K_M`，适合快速初审。
- `InternVL3.5-8B`：使用官方 `OpenGVLab/InternVL3_5-8B` 权重，
  按官方模型卡给出的 BNB 8-bit Transformers 方式独立加载，用作交叉复核。

注意：本机 Qwen 权重是社区修改的 Q4 版本，不等同于官方原版
`Qwen3-VL-8B-Instruct`，不可单独作为正式发布验收结论。

## 为什么独立部署

RTX 5070 Ti 只有 16 GB 显存，生成模型、Ollama VLM 和 InternVL 不应并行
驻留。本项目放在 `agent-projects/`，不安装 ComfyUI 自定义节点、不修改
ComfyUI Python 依赖，避免产品出图环境因 VLM 部署发生依赖漂移。

## 环境

InternVL 环境复用秋叶包中已经可用的 CUDA PyTorch，仅把 VLM 专属依赖安装
到项目虚拟环境：

```powershell
D:\ComfyUI-aki-v3\python\python.exe -m venv --system-site-packages .\.venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements-internvl.txt
```

本机已下载的官方 InternVL 模型位置为：

```text
D:\ComfyUI-aki-v3\models\InternVL3_5-8B
```

下载缓存默认写入 `runtime/hf_home/`，不会占用系统用户缓存目录。

## 使用

先运行已部署的 Qwen 基线：

```powershell
.\.venv\Scripts\python.exe -m product_vlm_review run `
  --backend ollama `
  --images "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\02.jpg" `
  --output .\runtime\1005007109462323\qwen_02.json
```

释放生成端显存后运行 InternVL：

```powershell
.\.venv\Scripts\python.exe -m product_vlm_review run `
  --backend internvl `
  --model "D:\ComfyUI-aki-v3\models\InternVL3_5-8B" `
  --images "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\02.jpg" `
  --output .\runtime\1005007109462323\internvl_02.json
```

对完整商品图组提取商品事实时，必须加 `--per-image`。这样 InternVL 只加载
一次，但逐张图片回答，避免整组上下文混淆“警员在车内”等关键关系：

```powershell
.\.venv\Scripts\python.exe -m product_vlm_review run `
  --backend internvl `
  --model "D:\ComfyUI-aki-v3\models\InternVL3_5-8B" `
  --per-image `
  --images "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\01.jpg" `
           "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\02.jpg" `
           "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\03.jpg" `
           "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\04.jpg" `
           "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\05.jpg" `
           "Y:\tiktok_ins_crawl\aliexpress\images\1005007109462323\06.jpg" `
  --output .\runtime\1005007109462323\internvl_per_image.json
```

每次执行均保存原始模型回答和可解析 JSON；不自动覆盖商品事实。

## 流程接入建议

1. 用 Qwen 逐图快速产出事实草稿与创意镜头候选。
2. 对涉及拆件、人物位置、文字规格或发布验收的图片逐图调用 InternVL 复核。
3. 仅将两个模型均能从原图指出的事实写入生成 prompt 的固定约束。
4. ComfyUI 生成结束后，对成片再用相同事实清单做验收；文字排版与精确规格使用确定性后期合成。

## 本机实测结论

- `02.jpg` 单图：Qwen 与 InternVL 均识别到警员坐在车内，且白色车顶/
  蓝色警灯已分离并悬置展示。
- 六图整组直接输入 InternVL：模型将 `02.jpg` 的警员位置误判为不在车内，
  因而整组回答只能作为镜头灵感，不能作为商品事实依据。
- Qwen 当前 Ollama 社区 Q4 模型在六图同传时出现截断和损坏 JSON，也必须
  使用逐图证据模式。
