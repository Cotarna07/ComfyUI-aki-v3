# CMS26-5-30 Wan 2.2 SVI 2 Pro Long Video 工作流拆解（证据版）

> 整理日期：2026-05-30  
> 对应工作流：agent-skills/comfyui/workflows/TEST/CMS26-5-30 -wan 2.2 NSFW svi 2 pro long video (merged SVI model).json  
> 目标：只保留可核验的数据，不把经验判断写成结论

---

## 1. 证据口径

本文只使用下面三类来源：

1. 工作流 JSON 本身的实际值。
2. 节点插件源码或插件 README 中明确写出的参数定义、默认值、可选项、tooltip、description。
3. 这张工作流自带 Note 节点中的作者原始说明。

本文不再把下面这些内容写成“确定结论”：

- 我个人对“哪个值更好”的推断。
- 没有源码、README 或作者 Note 支持的调参经验。
- 没有从工作流 JSON 直接读出来的隐藏状态猜测。

如果某个参数当前没有官方推荐值，本文会明确写成：当前官方来源未给出统一推荐值。

---

## 2. 证据来源

### 2.1 工作流 JSON

- 文件：agent-skills/comfyui/workflows/TEST/CMS26-5-30 -wan 2.2 NSFW svi 2 pro long video (merged SVI model).json
- 顶层字段：id、revision、last_node_id、last_link_id、nodes、links、groups、config、extra、version
- 结构统计：321 个节点、439 条连线、12 个分组

### 2.2 ComfyUI 核心节点源码

- ComfyUI/nodes.py
  - VAELoader
  - UNETLoader
  - CLIPLoader
  - KSamplerAdvanced

### 2.3 KJNodes 插件源码

- ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/nodes.py
  - WanImageToVideoSVIPro
- ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/image_nodes.py
  - ImageBatchExtendWithOverlap
- ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/model_optimization_nodes.py
  - PathchSageAttentionKJ

### 2.4 LoRA Manager 插件源码与 README

- ComfyUI/custom_nodes/ComfyUI-Lora-Manager/README.md
- ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/prompt.py
- ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/trigger_word_toggle.py
- ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/lora_loader.py

### 2.5 rgthree 插件源码

- ComfyUI/custom_nodes/rgthree-comfy/py/ksampler_config.py

### 2.6 工作流作者 Note 节点

- 节点 363：Recomendation
- 节点 364：Models and .whl files
- 节点 365：Notes For NSFW

---

## 3. 这张工作流的事实数据

### 3.1 整体结构

这张工作流由 12 个批次分组组成：

- Batch 1 (5 sec)
- Batch 2 (10 sec)
- Batch 3 (15 sec)
- Batch 4 (20 sec)
- Batch 5 (25 sec)
- Batch 6 (30 sec)
- Batch 7 (35 sec)
- Batch 8 (40 sec)
- Batch 9 (45 sec)
- Batch 10 (50 sec)
- Batch 11 (55 sec)
- Batch 12 (60 sec)

按节点类型统计，数量最多的部分是：

- 144 个 GetNode
- 24 个 Lora Loader (LoraManager)
- 24 个 KSamplerAdvanced
- 13 个 VHS_VideoCombine
- 12 个 WanImageToVideoSVIPro
- 12 个 CLIPTextEncode
- 12 个 VAEDecode
- 12 个 Prompt (LoraManager)
- 12 个 SetNode
- 11 个 ImageBatchExtendWithOverlap

这说明它本质上是“少量全局节点 + 12 组重复模板”的长视频工作流，而不是 321 个完全不同功能的节点。

### 3.2 当前全局实际值

下表全部来自工作流 JSON 当前 widgets_values 或连线状态：

| 项目 | 当前值 | 证据来源 |
|---|---|---|
| High Noise 模型 | WAN2.2/DasiwaWAN22I2V14BLightspeed_synthseductionHighV9.safetensors | 节点 377 |
| Low Noise 模型 | WAN2.2/DasiwaWAN22I2V14BLightspeed_synthseductionLowV9.safetensors | 节点 376 |
| Text Encoder | umt5_xxl_fp8_e4m3fn_scaled.safetensors | 节点 15 |
| CLIP 类型 | wan | 节点 15 |
| VAE | wan_2.1_vae.safetensors | 节点 378 |
| 参考图 | 1713279344578.jpg | 节点 17 |
| 分辨率 | 672 x 896 | 节点 48 |
| resize 方法 | lanczos | 节点 48 |
| keep_proportion | crop | 节点 48 |
| crop_position | center | 节点 48 |
| resize 设备 | cpu | 节点 48 |
| 全局 Steps | 8 | 节点 370 -> 39 |
| 全局 Sampler | uni_pc | 节点 370 -> 65 |
| 全局 Scheduler | normal | 节点 370 -> 66 |
| 单批帧数 | 81 | 节点 95 -> 96 |
| 高低噪分界 | 4 | 节点 30 -> 40 |
| CFG High | 2.0 | 节点 69 -> 70 |
| CFG Low | 1.0 | 节点 72 -> 71 |
| overlap | 5 | 各 overlap 节点 |
| overlap_side | source | 各 overlap 节点 |
| overlap_mode | linear_blend | 各 overlap 节点 |
| 输出 fps | 16 | 各 VideoCombine 节点 |
| 输出格式 | video/h264-mp4 | 各 VideoCombine 节点 |
| pix_fmt | yuv420p | 各 VideoCombine 节点 |
| crf | 19 | 各 VideoCombine 节点 |

### 3.3 当前实际时长怎么算

这部分不是猜测，是根据 JSON 当前值直接计算：

- 每批长度：81 帧
- 批次数量：12
- 批次间 overlap：5 帧
- 输出帧率：16 fps

总帧数公式：

- 第 1 批提供 81 帧
- 后面 11 批每批新增 81 - 5 = 76 帧
- 总帧数 = 81 + 11 x 76 = 917

总时长公式：

- 917 / 16 = 57.3125 秒

所以，这张图当前全开时的理论总时长是约 57.31 秒。分组标题写到 60 sec，但当前 JSON 配置严格换算后不是整 60 秒。

### 3.4 当前哪些批次真的填了内容

这部分来自各批次 Prompt、Negative 和 LoRA 节点的 widgets_values：

| 批次 | Positive 已填 | Negative 已填 | High LoRA 已启用 | Low LoRA 已启用 |
|---|---|---|---|---|
| Batch 1 | 是 | 是 | 是（2 个） | 是（2 个） |
| Batch 2 | 是 | 是 | 是（2 个） | 是（2 个） |
| Batch 3 | 否 | 否 | 否 | 否 |
| Batch 4 | 否 | 否 | 否 | 否 |
| Batch 5 | 否 | 否 | 否 | 否 |
| Batch 6 | 否 | 否 | 否 | 否 |
| Batch 7 | 否 | 否 | 否 | 否 |
| Batch 8 | 否 | 否 | 否 | 否 |
| Batch 9 | 否 | 否 | 否 | 否 |
| Batch 10 | 否 | 否 | 否 | 否 |
| Batch 11 | 否 | 否 | 否 | 否 |
| Batch 12 | 否 | 否 | 否 | 否 |

结论只基于 JSON 当前值：这张图现在只把前两批明确配置好了，后十批目前还是空模板。

---

## 4. 节点官方定义与当前接线

### 4.1 UNETLoader

来源：ComfyUI/nodes.py

官方输入定义：

- unet_name：来自 diffusion_models 目录
- weight_dtype：可选 default、fp8_e4m3fn、fp8_e4m3fn_fast、fp8_e5m2

当前工作流实际值：

- 节点 377：High Noise 模型，weight_dtype = default
- 节点 376：Low Noise 模型，weight_dtype = default

可直接证实的事：

- 这张图用了两个单独的 UNet 模型。
- 两个节点都没有显式启用 fp8_e4m3fn / fp8_e5m2 之类的 weight_dtype 选项，而是保留 default。

当前官方来源没有给出“这两个模型必须怎样搭配才最优”的统一推荐值；源码只定义了输入项和可选 dtype。

### 4.2 CLIPLoader

来源：ComfyUI/nodes.py

官方输入定义：

- clip_name：来自 text_encoders 目录
- type：包含 stable_diffusion、sd3、wan 等类型
- device：default 或 cpu

源码 DESCRIPTION 对 wan 的说明是：wan: umt5 xxl。

当前工作流实际值：

- 节点 15：clip_name = umt5_xxl_fp8_e4m3fn_scaled.safetensors
- type = wan
- device = default

### 4.3 VAELoader

来源：ComfyUI/nodes.py

官方输入定义只有一个：

- vae_name

当前工作流实际值：

- 节点 378：vae_name = wan_2.1_vae.safetensors

### 4.4 KSamplerAdvanced

来源：ComfyUI/nodes.py

官方输入定义：

- add_noise：enable / disable
- noise_seed：INT，默认 0
- steps：INT，默认 20
- cfg：FLOAT，默认 8.0
- sampler_name：采样器列表
- scheduler：调度器列表
- positive
- negative
- latent_image
- start_at_step：默认 0
- end_at_step：默认 10000
- return_with_leftover_noise：disable / enable

源码里 sample 的明确行为：

- return_with_leftover_noise = enable 时，force_full_denoise = False
- add_noise = disable 时，disable_noise = True
- 最终调用 common_ksampler，把 start_step 和 last_step 传进去

当前工作流实际接线：

- 每个批次都有 2 个 KSamplerAdvanced
- 高噪采样器接入：全局 Steps、CFG High、Sampler、Scheduler、end_at_step = 4
- 低噪采样器接入：全局 Steps、CFG Low、Sampler、Scheduler、start_at_step = 4

可直接证实的事：

- 这张图是双阶段采样。
- 高噪和低噪不是两个完全独立流程，而是在同一个 total steps 里分段运行。
- 当前 steps 的实际值是 8，不是 KSamplerAdvanced 的 core 默认 20。

### 4.5 rgthree 的 KSampler Config

来源：ComfyUI/custom_nodes/rgthree-comfy/py/ksampler_config.py

官方输入定义：

- steps_total：默认 30
- refiner_step：默认 24
- cfg：默认 8.0
- sampler_name
- scheduler

官方输出定义：

- STEPS
- REFINER_STEP
- CFG
- SAMPLER
- SCHEDULER

当前工作流实际值：

- 节点 370：8 / 1 / 0 / uni_pc / normal

当前工作流实际使用方式：

- STEPS 输出被用到了
- SAMPLER 输出被用到了
- SCHEDULER 输出被用到了
- 高低噪 CFG 没有直接使用这个节点的 CFG 输出，而是用了节点 69 和 72 的两个 PrimitiveFloat
- 高低噪分界也没有直接使用这个节点的 REFINER_STEP 输出，而是用了节点 30 的独立 INTConstant

这个结论来自 JSON 连线，不是推断。

### 4.6 WanImageToVideoSVIPro

来源：ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/nodes.py

官方 schema：

- positive
- negative
- length：默认 81，min 1，step 4
- anchor_samples
- prev_samples：optional
- motion_latent_count：默认 1，min 0，max 128

官方 execute 行为：

- 如果 prev_samples 不存在，或 motion_latent_count = 0：只使用 anchor_samples 构造 image_cond_latent
- 否则：从 prev_samples 末尾截取 motion_latent_count 个 latent，拼到 anchor_samples 后面
- 然后创建空 latent：形状中的时间长度是 ((length - 1) // 4) + 1
- 最后把 concat_latent_image 和 concat_mask 写回正负 conditioning

当前工作流实际值：

- 每个 SVI 节点的 widgets_values 都是 [81, 1]
- Batch 1：prev_samples 未连接
- Batch 2 到 Batch 12：prev_samples 已连接上一批的 low-noise latent

可直接证实的事：

- 这张图确实使用了 anchor_samples + prev_samples 的双来源延长机制。
- 当前 motion_latent_count 就是 1，不是别的值。

### 4.7 ImageBatchExtendWithOverlap

来源：ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/image_nodes.py

官方 DESCRIPTION：

- 这是一个用于视频延长的 helper node
- 先输入 source 和 overlap，取出延长起始帧
- 再在另一份节点中提供 newly generated frames，并选择 overlap 方式

官方输入定义：

- source_images
- overlap：默认 13，min 1
- overlap_side：source 或 new_images
- overlap_mode：cut、linear_blend、ease_in_out、filmic_crossfade、perceptual_crossfade
- optional new_images

官方输出定义：

- source_images
- start_images
- extended_images

当前工作流实际值：

- Batch 2 到 Batch 12 的 overlap 节点全部是 [5, source, linear_blend]

源码里可直接证实的事：

- linear_blend：按线性 alpha 混合重叠帧
- ease_in_out：使用 3t^2 - 2t^3
- filmic_crossfade：先转 gamma 2.2 的线性空间再混合
- perceptual_crossfade：先转 LAB 空间再混合
- cut：直接拼接，不做混合

### 4.8 PathchSageAttentionKJ

来源：ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/model_optimization_nodes.py

官方输入定义：

- model
- sage_attention
- allow_compile：默认 False，tooltip 说明需要 sageattn 2.2.0 或更高

官方 DESCRIPTION：

- Experimental node for patching attention mode
- 不使用 model patching system
- 不能靠普通方式禁用，想恢复要再跑一次 disabled

当前工作流实际值：

- 节点 5 和 6：sage_attention = disabled，allow_compile = disabled

### 4.9 Lora Loader (LoraManager)

来源：ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/lora_loader.py

官方输入定义：

- required：model、text
- text tooltip：Format: <lora:lora_name:strength> separated by spaces or punctuation
- optional：clip、lora_stack 等动态输入

官方输出定义：

- MODEL
- CLIP
- trigger_words
- loaded_loras

load_loras 的明确行为：

- 读取 text / lora_stack / widget 中的 LoRA 条目
- 应用到 model 和 clip
- 返回合并后的 trigger_words_text

当前工作流实际结构：

- 每个批次各有 1 个 High Noise LoRA Loader 和 1 个 Low Noise LoRA Loader
- Batch 1 和 Batch 2 的这两类节点已经填了 LoRA 文本并启用了条目
- Batch 3 到 Batch 12 当前没有启用项

### 4.10 TriggerWord Toggle (LoraManager)

来源：ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/trigger_word_toggle.py

官方输入定义：

- group_mode：默认 True，tooltip 明确说把一组 trigger words 作为一个整体开关
- default_active：默认 True，tooltip 明确说新增 trigger words 时的初始开关状态
- allow_strength_adjustment：默认 False，tooltip 明确说允许滚轮调节每个 trigger word 的 strength

当前工作流实际值：

- Batch 1 和 Batch 2 当前都是 true / true / false

### 4.11 Prompt (LoraManager)

来源：ComfyUI/custom_nodes/ComfyUI-Lora-Manager/py/nodes/prompt.py

官方输入定义：

- required：text、clip
- optional：seed、trigger_words1，以及动态 trigger_words 输入

官方行为：

- 先做 wildcard 展开
- 再收集所有 trigger_words 输入
- 最终 prompt = trigger_words + expanded_text
- 然后调用 CLIPTextEncode 生成 conditioning

可直接证实的事：

- TriggerWord Toggle 输出接到 Prompt (LoraManager) 时，触发词会被拼到正文前面一起编码。

---

## 5. 工作流作者在 Note 节点里写了什么

这部分不是我总结，是工作流作者自己写在 JSON 里的文本。

### 5.1 Note 363：Recomendation

作者原文里明确写了这些建议：

- wan 2.2 可以用 480p 到 720p 的分辨率
- 也可以用 1024x576
- 可以按需要开关 batch group
- 不要在 first batch 放 SVI Loras
- cfg1 in High noise gives faster result
- cfg2 + negative prompt 会得到 better result
- 需要到 UnetLoader、Clip、Vae 和 Lora loaders 里选择你本地路径中的模型
- 现在已经把 Power Lora Loader 改成了 Lora Manager 节点
- High Noise LoRA 只放到 High Lora Loader，Low Noise LoRA 只放到 Low Lora Loader
- try writing prompt better and clearly
- 作者原话：in my opinion, 10-15 seconds videos is optimal choice for generation, but you can generate longer one

作者还在同一个 Note 里给了两套分辨率表：

576p 档：

- 1:1 -> 768x768
- 4:3 -> 896x672
- 3:2 -> 944x632
- 16:9 -> 1024x576
- 21:9 -> 1248x536
- 2.39:1 -> 1280x536
- 4:5 -> 688x864
- 3:4 -> 672x896
- 2:3 -> 632x944
- 9:16 -> 576x1024
- 9:21 -> 536x1248

720p 档：

- 1:1 -> 960x960
- 4:3 -> 1104x832
- 3:2 -> 1176x784
- 16:9 -> 1280x720
- 21:9 -> 1472x624
- 2.39:1 -> 1488x616
- 4:5 -> 856x1072
- 3:4 -> 832x1104
- 2:3 -> 784x1176
- 9:16 -> 720x1280
- 9:21 -> 624x1472

### 5.2 Note 364：Models and .whl files

这个 Note 节点给了：

- SVI 2 PRO 8 steps 模型下载地址
- Text Encoder 下载地址
- VAE 下载地址
- 一长串 LoRA 地址
- 模型目录放置结构
- SageAttention.whl 安装说明
- Triton 安装说明
- 一个 SageAttention 报错时的启动建议

这部分是作者给这张工作流准备依赖时的原始清单，可以当成“作者随工作流附带的依赖说明”，不是我额外整理的。

### 5.3 Note 365：Notes For NSFW

这个 Note 节点主要列的是各个 LoRA 的 trigger words 或“去看 CivitAI 描述”的提示。

因为这些内容本身已经完整存放在工作流 JSON 里，这里不重复抄写成第二份；需要原文时，直接看节点 365 即可。

---

## 6. 批次定位表

这部分同样直接来自 JSON 节点 ID，不是推断。

| 批次 | High LoRA | Low LoRA | Trigger | Positive | Negative | SVI | High Sampler | Low Sampler | Decode | Overlap | Preview |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Batch 1 (5 sec) | 75 | 79 | 76 | 77 | 81 | 82 | 84 | 85 | 86 | - | 102 |
| Batch 2 (10 sec) | 103 | 117 | 107 | 113 | 115 | 112 | 108 | 118 | 123 | 126 | 124 |
| Batch 3 (15 sec) | 127 | 140 | 131 | 136 | 138 | 135 | 132 | 141 | 148 | 149 | 146 |
| Batch 4 (20 sec) | 150 | 163 | 154 | 159 | 161 | 158 | 155 | 164 | 171 | 172 | 169 |
| Batch 5 (25 sec) | 173 | 186 | 177 | 182 | 184 | 181 | 178 | 187 | 194 | 195 | 192 |
| Batch 6 (30 sec) | 196 | 209 | 200 | 205 | 207 | 204 | 201 | 210 | 217 | 218 | 215 |
| Batch 7 (35 sec) | 219 | 232 | 223 | 228 | 230 | 227 | 224 | 233 | 240 | 241 | 238 |
| Batch 8 (40 sec) | 242 | 255 | 246 | 251 | 253 | 250 | 247 | 256 | 263 | 264 | 261 |
| Batch 9 (45 sec) | 265 | 278 | 269 | 274 | 276 | 273 | 270 | 279 | 286 | 287 | 284 |
| Batch 10 (50 sec) | 288 | 301 | 292 | 297 | 299 | 296 | 293 | 302 | 309 | 310 | 307 |
| Batch 11 (55 sec) | 311 | 324 | 315 | 320 | 322 | 319 | 316 | 325 | 332 | 333 | 330 |
| Batch 12 (60 sec) | 335 | 348 | 339 | 344 | 346 | 343 | 340 | 349 | 355 | 356 | 354 |

---

## 7. 目前官方来源没有给出的内容

为了避免把经验值写成“官方数据”，下面这些结论本文不写：

- 哪个 shift 一定最好
- 哪个 CFG 一定最优
- 哪个 steps 一定最优
- 哪个 motion_latent_count 一定最优
- 哪个 overlap 一定最优

当前仓库里的官方来源能明确给出的，只有：

- 节点默认值和可选项
- 当前工作流 JSON 的实际设置
- 工作流作者在 Note 节点写下的建议

如果你接下来要做“调参建议版”，应该单独标注为：

- 作者建议
- 当前模板实际值
- 个人或经验建议

三者不能混成一种口径。

---

## 8. 目前这个工作流在当前配置下能实现什么效果

下面这部分只描述当前 JSON 已经配置好的能力，不把“理论上可以做什么”和“现在已经配好什么”混在一起。

### 8.1 当前已经能确定的能力

根据节点类型、连线和当前值，这张工作流当前已经明确具备这些能力：

- 它是一张 Wan 2.2 的图生视频工作流，不是文生视频工作流。
- 它使用一张参考图作为 anchor，并通过 WanImageToVideoSVIPro 做分段延长。
- 它使用高噪 / 低噪双阶段采样。
- 它使用 overlap 节点把后续批次平滑拼接到前一批上。
- 它最终会把拼好的图像序列送入最终导出节点 357。

最终导出链路这一点可以直接从连线看出来：

- 最终输出链接是 [463,356,2,357,0,"IMAGE"]
- 含义是：节点 356 的第 3 个输出 extended_images，接到了节点 357 的 images 输入

### 8.2 当前画面规格

根据当前全局节点设置，这张图当前会按下面这些规格生成：

- 输入类型：单张参考图
- 当前参考图：1713279344578.jpg
- 当前分辨率：672 x 896
- 画幅：3:4 竖版
- 当前帧率：16 fps
- 当前导出格式：video/h264-mp4
- 当前像素格式：yuv420p
- 当前 crf：19

### 8.3 当前已经明确写好的内容范围

根据前两批的 Prompt 和 LoRA 当前值，这张图现在已经明确写好的，是一个成人向 NSFW 的前两段连续视频模板：

- Batch 1 和 Batch 2 使用相同的 Positive Prompt
- Batch 1 和 Batch 2 使用相同的 Negative Prompt
- Batch 1 和 Batch 2 启用的是同一组 High/Low LoRA 组合
- 启用中的 LoRA 分别是：
  - High：NSFW-22-H-e8、reverse_suspended_congress_I2V_high
  - Low：NSFW-22-L-e8、reverse_suspended_congress_I2V_low

因此，当前这张图已经能确定实现的是：

- 一张参考图驱动的竖版 Wan 2.2 I2V 视频
- 前两批是同一主题、同一 LoRA 组合的连续段落
- 通过 SVI 的 prev_samples 和图像 overlap 做续接

### 8.4 当前已经写好的时长是多少

这张图全部 12 批全开时的理论总时长，前文已经算过是：

- 917 帧
- 57.3125 秒

但“当前已经明确写好内容”的只有前两批，所以更适合单独算前两批：

- 第 1 批：81 帧
- 第 2 批新增：81 - 5 = 76 帧
- 前两批合计：157 帧
- 前两批理论时长：157 / 16 = 9.8125 秒

也就是说，如果你只看当前已经明确填好的 Prompt / LoRA 内容，这张图目前已经配好的，是约 9.81 秒的两段连续模板；后面 10 批还是空模板。

---

## 9. 这张工作流怎么使用

这里的“怎么使用”，只写当前工作流结构直接支持的操作步骤，以及作者 Note 明确写到的事项。

### 9.1 使用前要确认的节点

先确认这些资源节点都指向你本地实际存在的模型：

- 节点 377：High Noise UNet
- 节点 376：Low Noise UNet
- 节点 15：CLIP
- 节点 378：VAE

这一步也和作者 Note 363 的原话一致：

- Also click through UnetLoader, Clip, Vae and Lora loaders nodes to choose models in your path

### 9.2 基本使用顺序

按当前结构，推荐的使用顺序可以直接写成下面几步：

1. 在节点 17 换成你的输入图。
2. 在节点 48 设定输出分辨率。
3. 在节点 370、95、30、69、72 设定全局参数。
4. 只打开你需要的 Batch 分组。
5. 对你要用的批次，填写或检查对应的 High/Low LoRA、Prompt、Negative。
6. 运行工作流。
7. 查看每批预览输出，或直接看最终输出节点 357 的结果。

### 9.3 这张图当前最实际的使用方式

因为 Batch 3 到 Batch 12 现在还是空模板，所以按当前文件状态，最实际的用法是：

- 先只用 Batch 1 和 Batch 2
- 把它当成一个约 9.81 秒的两段连续模板去测试
- 确认前两批能跑通之后，再把 Batch 2 的结构复制到后续批次继续扩展

这不是经验推断，而是因为当前 JSON 里只有前两批真的填了内容，后十批没有。

### 9.4 作者 Note 里明确提到的使用注意项

作者在 Note 363 里直接写过这些点：

- 可以按需要开关 batch group
- 不要在 first batch 放 SVI Loras
- High Noise LoRA 只放到 High Lora Loader，Low Noise LoRA 只放到 Low Lora Loader
- Prompt 要尽量写清楚

这些都属于作者原始说明，不是我补充出来的规则。

---

## 10. 这张工作流怎么调整参数

这里不写“哪个值一定最好”，只写“改哪个节点，会影响哪一类结果”。

### 10.1 调整输出尺寸

入口节点：48

可调项：

- width
- height
- upscale_method
- keep_proportion
- crop_position
- device

会直接影响：

- 输出分辨率
- 输入图的裁切方式
- 输入图缩放方式

作者 Note 363 明确给了 576p 和 720p 两套常用尺寸表；当前工作流使用的是其中的 3:4 竖版 672x896。

### 10.2 调整每批时长和总时长

入口节点：95、各 overlap 节点、各 VideoCombine 节点

可调项：

- 节点 95：每批帧数
- overlap 节点：overlap 帧数
- VideoCombine：fps

会直接影响：

- 单批长度
- 拼接后净新增帧数
- 最终理论总时长

当前总时长公式可以直接复用：

- 总帧数 = 第一批帧数 + (批次数 - 1) x (每批帧数 - overlap)
- 总时长 = 总帧数 / fps

### 10.3 调整采样强度和采样阶段划分

入口节点：370、30、69、72、各批次的 2 个 KSamplerAdvanced

可调项：

- 节点 370：steps_total、sampler_name、scheduler
- 节点 30：高低噪分界
- 节点 69：CFG High
- 节点 72：CFG Low

它们在当前工作流中的实际作用是：

- 所有批次共享同一套 steps、sampler、scheduler
- 节点 30 控制高噪阶段在哪一步结束，低噪阶段从哪一步开始
- 节点 69 和 72 分别给高噪 / 低噪采样器提供 cfg

如果你想改“采样节奏”，优先看这 4 个入口，而不是先逐个批次点 KSamplerAdvanced 面板里的本地显示值。

### 10.4 调整分段续接强度

入口节点：各 WanImageToVideoSVIPro、各 ImageBatchExtendWithOverlap

可调项：

- WanImageToVideoSVIPro 的 motion_latent_count
- overlap 节点的 overlap
- overlap_side
- overlap_mode

它们的源码定义已经明确了作用：

- motion_latent_count：决定从 prev_samples 末尾拿多少个 latent 参与续接
- overlap：决定图像级拼接重叠多少帧
- overlap_side：决定以 source 还是 new_images 一侧作为 overlap 参考
- overlap_mode：决定是 cut、linear_blend、ease_in_out、filmic_crossfade 还是 perceptual_crossfade

### 10.5 调整具体段落内容

入口节点：每个批次的 LoRA / Trigger / Prompt / Negative

对每个批次，最直接的内容入口就是：

- High LoRA Loader
- Low LoRA Loader
- TriggerWord Toggle
- Prompt (LoraManager)
- Negative

它们控制的是该批次的：

- LoRA 组合
- 触发词开关
- 正向文本条件
- 负向文本条件

如果你要改“这段视频具体拍什么”，主要改的是这组节点，而不是全局采样节点。

### 10.6 调整导出格式

入口节点：各 VHS_VideoCombine，尤其是最终节点 357

可调项：

- frame_rate
- format
- pix_fmt
- crf
- save_metadata
- trim_to_audio
- pingpong
- save_output

它们控制的是导出封装和压缩，不改变前面生成出的图像内容本身。

---

## 11. 最直接的结论

如果只用一句话概括当前状态：

- 这张图目前已经能做的是：一张参考图驱动的 Wan 2.2 竖版 I2V 分段延长视频模板，前两批约 9.81 秒内容已经明确配置好，整张图的 12 批结构可以扩展到约 57.31 秒。

如果只用一句话概括怎么调：

- 改画面规格看节点 48，改时长看节点 95 和 overlap，改采样看节点 370/30/69/72，改具体内容看每批的 LoRA / Prompt / Negative。