# WAN2.2 LOOP NATIVE UPSCALER GGUF 工作流拆解（证据版）

> 整理日期：2026-05-31  
> 对应工作流：agent-skills/comfyui/workflows/TEST/26-5-29/WAN2.2_LOOP_NATIVE_UPSCALER_GGUF.json  
> 目标：只保留可核验的参数、当前有效值、启停状态和测试入口

---

## 1. 证据口径

本文只使用下面四类来源：

1. 工作流 JSON 当前保存的节点值、连线、mode 状态。
2. 工作流里的数学节点和中间转换节点，推导真正生效的运行值。
3. 当前本机 ComfyUI 8188 端口的 /object_info 节点定义。
4. 插件源码或核心源码中明确写出的输入定义、默认值、可选项、tooltip、说明文字。

本文不把下面这些内容写成“确定结论”：

- 没有源码、README、/object_info 或工作流 JSON 支持的经验判断。
- 只根据 group 颜色猜测启用状态。
- 把 widgets 面板里残留的旧值，当成当前真正运行值。

如果某个参数当前没有官方推荐值，本文会明确写成：当前官方来源未给出统一推荐值。

---

## 2. 证据来源

### 2.1 工作流 JSON

- 文件：agent-skills/comfyui/workflows/TEST/26-5-29/WAN2.2_LOOP_NATIVE_UPSCALER_GGUF.json
- 结构统计：87 个节点、120 条连线、14 个分组

### 2.2 ComfyUI / 插件定义来源

- ComfyUI/custom_nodes/ComfyUI-GGUF/nodes.py
  - UnetLoaderGGUF
- ComfyUI/custom_nodes/RES4LYF/beta/samplers.py
  - ClownsharKSampler_Beta
- ComfyUI/custom_nodes/Comfyui-PainterFLF2V/painter_flf2v_nodes.py
  - PainterFLF2V
- ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/model_optimization_nodes.py
  - WanVideoEnhanceAVideoKJ
  - WanVideoNAG
- ComfyUI/comfy_extras/nodes_cfg.py
  - CFGZeroStar
- ComfyUI/comfy_extras/nodes_model_advanced.py
  - ModelSamplingSD3
- ComfyUI/custom_nodes/ComfyUI-GIMM-VFI/nodes.py
  - GIMMVFI_interpolate
- ComfyUI/custom_nodes/ComfyUI-Frame-Interpolation/vfi_models/rife/__init__.py
  - RIFE VFI
- ComfyUI/custom_nodes/ComfyUI_essentials/image.py
  - ImageResize+
- ComfyUI/custom_nodes/ComfyUI-KJNodes/nodes/image_nodes.py
  - ColorMatch
- ComfyUI/custom_nodes/ComfyUI-Florence2/nodes.py
  - DownloadAndLoadFlorence2Model
  - Florence2Run
- ComfyUI/custom_nodes/rgthree-comfy/src_web/comfyui/feature_group_fast_toggle.ts
- ComfyUI/custom_nodes/rgthree-comfy/src_web/comfyui/fast_groups_muter.ts
- ComfyUI/custom_nodes/rgthree-comfy/src_web/comfyui/fast_groups_bypasser.ts
- ComfyUI/custom_nodes/rgthree-comfy/src_web/comfyui/node_mode_relay.ts

### 2.3 工作流作者说明节点

这张工作流里没有抽出可直接引用的 Note / Label 作者说明文本，因此本文不使用“作者备注推荐值”这类证据。

---

## 3. 这张工作流当前能做什么

只按当前连线和当前启停状态看，这张图现在的能力可以概括为：

1. 读取一张起始图片作为 Start frame。
2. 先把这张图缩放到“高度由滑块控制、宽度自动保持比例”的尺寸。
3. 用同一张图同时作为 PainterFLF2V 的 start_image 和 end_image，生成首尾一致的 loop latent。
4. 走一套 High noise -> Low noise -> Low refine 的三段采样链。
5. Decode 后再做一次 ColorMatch，把结果往起始图的色彩参考靠拢。
6. 输出 4 路视频结果：
   - Output：基础输出。
   - Frame skip + last frame interpolation：首尾过渡处理分支。
   - Save Interpoled：GIMMVFI 插帧分支。
   - Save Upscaled：放大分支。

这不是“猜这个作者想干什么”，而是当前节点链路直接表现出的功能。

---

## 4. 当前启停状态

### 4.1 rgthree 的 mode 语义

根据 rgthree 源码：

- LiteGraph.NEVER 用作 MUTE。
- mode = 4 用作 BYPASS。
- LiteGraph.ALWAYS 用作 ACTIVE。

### 4.2 这张图当前哪些部分是启用的

当前工作流里，只有下面这些节点被序列化为 mode = 4：

- 473 DownloadAndLoadFlorence2Model
- 474 Text Find and Replace
- 475 Text Find and Replace
- 476 Text Find and Replace
- 477 Text Find and Replace
- 478 Text Find and Replace
- 479 easy showAnything
- 480 Florence2Run

这些节点都属于 Automatic prompt 分组，所以可以确认：

- Automatic prompt 当前是 BYPASS 状态，不是活动状态。

反过来，当前没有在非零 mode 列表中出现的节点，包括：

- Interpolation 分组
- upscaler 分组
- Video enhance / CFGZeroStar / speed regulation / Normalized Attention 分组

因此就“序列化出的节点 mode”而言，这些分支当前不是静音或旁路状态。

### 4.3 当前 LoRA 状态

两组 Power Lora Loader 当前 widgets_values 都只有空 dict 和 header：

- LoRA - High noise
- LoRA - Low noise

这意味着：

- 当前 JSON 里没有可直接列出的具体 LoRA 名称、开关和强度。
- 不能把“可能之前加载过某个 LoRA”写成当前事实。

---

## 5. 工作流结构与当前模型配置

### 5.1 分组

当前共有 14 个 group：

- WAN2.2 - Loop workflow
- Backend - Stage 1
- Sampler 2 low
- Optimisation
- Video enhance
- CFGZeroStar
- Normalized Attention
- speed regulation
- Automatic prompt
- Frame overlap
- Interpolation
- Sampler 3 low
- Decode
- upscaler

### 5.2 当前模型与基础节点

| 节点 | 当前值 | 说明 |
|---|---|---|
| UnetLoaderGGUF 高噪 | DasiwaWAN22I2V14BTastysinV8_q4High.gguf | 当前高噪 GGUF 模型 |
| UnetLoaderGGUF 低噪 | DasiwaWAN22I2V14BTastysinV8_q4Low.gguf | 当前低噪 GGUF 模型 |
| CLIPLoader | umt5_xxl_fp8_e4m3fn_scaled.safetensors / wan / cpu | 当前文本编码器 |
| VAELoader | wan_2.1_vae.safetensors | 当前 VAE |
| GIMMVFI 模型 | gimmvfi_f_arb_lpips_fp32.safetensors / fp16 / False | 当前插帧模型加载设置 |
| UpscaleModelLoader | 4x-AnimeSharp.pth | 当前放大模型 |

根据 UnetLoaderGGUF 的官方定义，它只要求 unet_name；源码没有给出“哪一对 GGUF 模型是推荐组合”的统一说明。

---

## 6. 当前真正生效的参数

这一节只写“当前真正影响运行结果的值”。如果 widgets 面板里有旧值、但输入口已经被连线覆盖，则以连线后的值为准。

### 6.1 总控滑块与有效值

| 控制入口 | 当前值 | 实际链路 | 当前真正生效结果 |
|---|---|---|---|
| Duration | 3 | Duration -> calculFrames -> toInt -> addFirst frame -> Painter length | 3 x 16 = 48；再 +1，Painter length = 49 |
| Frame rate | 16 | 直接进 Output / Frame skip 输出；也参与 calculFramesIn | 基础输出 fps = 16；插帧/放大输出 fps = 16 x 2 = 32 |
| Steps | 8 | 直接进 High / Sampler 2 low；另一路经 calculSteps | High steps = 8；Sampler 2 low steps = 8；High steps_to_run = 4 |
| CFG | 1 | 直接进 High / Sampler 2 low | High cfg = 1；Sampler 2 low cfg = 1 |
| Speed | 5 | 直接进两个 ModelSamplingSD3.shift | High / Low 两路 shift 都是 5 |
| Motion amplitude | 1 | 直接进 PainterFLF2V.motion_amplitude | Painter 当前 motion_amplitude = 1 |
| Height | 768 | 直接进 Resize First.height | Resize First 高度 = 768 |
| Frame overlap Interpolation | 2 | 直接进 RIFE VFI.multiplier | overlap 分支 RIFE multiplier = 2 |
| GIMMVFI Interpolation | 2 | 直接进 GIMMVFI_interpolate.interpolation_factor，并参与 calculFramesIn | GIMMVFI factor = 2；插帧/放大保存 fps = 32 |
| Start frame | 2 | 直接进 GetImageRangeFromBatch.start_index | overlap 截取起始偏移 = 2 |
| End frame | 2 | 参与 a-b-c 公式 | overlap 有效帧数 = image_count - 2 - 2 |
| Upscale ratio | 1 | 进 Calcul ratio，再进 ImageScaleBy.scale_by | ImageScaleBy.scale_by = 1 / 4 = 0.25 |

### 6.2 需要特别注意的“旧 widget 值不等于当前值”

下面这些地方，面板值和真正运行值不同：

| 节点 | 面板旧值 | 当前真正值 | 原因 |
|---|---|---|---|
| PainterFLF2V.length | 81 | 49 | 被 addFirst frame 连线覆盖 |
| Resize First.height | 800 | 768 | 被 Height 滑块覆盖 |
| Output.frame_rate | 24 | 16 | 被 Frame rate 滑块覆盖 |
| Save Interpoled.frame_rate | 35 | 32 | 被 calculFramesIn 覆盖 |
| Save Upscaled.frame_rate | 16 | 32 | 被 calculFramesIn 覆盖 |
| RIFE.multiplier | 3 | 2 | 被 overlap Interpolation 滑块覆盖 |
| GIMMVFI.interpolation_factor | 2 | 2 | 这里面板值和连线值一致，但真正值仍应按连线确认 |
| ImageScaleBy.scale_by | 1 | 0.25 | 被 Calcul ratio 覆盖 |

### 6.3 采样链当前值

#### ClownsharKSampler High

当前输入与运行值：

- eta = 0.5
- sampler_name = linear/euler
- scheduler = normal
- steps = 8
- steps_to_run = 4
- denoise = 1
- cfg = 1
- seed = 365139824204464
- sampler_mode = standard
- bongmath = True

#### Sampler 2 low

当前输入与运行值：

- eta = 0.5
- sampler_name = linear/euler
- scheduler = normal
- steps = 8
- steps_to_run = 当前未连线，保持节点自身值 -1
- denoise = 1
- cfg = 1
- seed = 当前未连线，节点自身值为 -1
- sampler_mode = resample
- bongmath = True

#### Sampler 3 low

当前输入与运行值：

- eta = 0
- sampler_name = linear/euler
- scheduler = beta
- steps = 1
- steps_to_run = -1
- denoise = 0.2
- cfg = 1
- seed = 0
- sampler_mode = standard
- bongmath = True

### 6.4 Prompt 当前值

#### 手工正向提示词

- Positive = girl dancing

#### 手工负向提示词

- Negative = 色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静 止，整体发灰，最差质量，低质量，JPEG压缩残留，丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走, blurry face, closed eyes, fast movements

#### 自动提示词链当前状态

自动提示词分支当前存着下面这些参数，但节点本身是 BYPASS：

- Florence 模型：MiaoshouAI/Florence-2-base-PromptGen-v2.0
- precision：fp16
- attention：sdpa
- Florence2Run.task：detailed_caption
- Florence2Run.max_new_tokens：1024
- Florence2Run.num_beams：3
- Florence2Run.do_sample：True
- Florence2Run.seed：777777777777777
- 文本替换链：photo -> video、image -> video、painting -> video、illustration -> video、drawing -> video、portrait -> video

当前能确认的事实只有两条：

1. 这条自动提示词链配置存在。
2. 当前这些节点是 BYPASS，不应把它当成正在活动的主提示词来源。

### 6.5 Painter / 优化 / 校色 / 插帧 / 放大当前值

#### PainterFLF2V

当前连线后可确认的值：

- width：来自 Resize First.width
- height：768
- length：49
- batch_size：1
- motion_amplitude：1

官方 tooltip 唯一明确写出的运动幅度说明是：

- 1.0 = Official Original
- 2.0 = High-Speed Dynamic

#### WanVideoEnhanceAVideoKJ

当前两路都是：

- weight = 1

官方说明只写明：weight 控制 enhance effect 的强度，没有给统一推荐值。

#### WanVideoNAG

当前两路都是：

- nag_scale = 11
- nag_alpha = 0.25
- nag_tau = 2.3730000000000007
- input_type = default

官方定义说明了参数名和输入类型，但当前官方来源未给出统一推荐值。

#### CFGZeroStar

当前两路都是：

- 只有 model 输入，没有额外数值参数。
- 它只是把输入 model patch 成 patched_model 再往后传。

#### ModelSamplingSD3

当前两路都是：

- shift = 5

官方实现是 set_parameters(shift=shift, multiplier=1000)，也就是这个滑块实质上在改 model sampling 的 shift。

#### ColorMatch

当前值：

- method = mkl
- strength = 1
- multithread = True

官方定义给出了 method 可选项，但没有给“哪种方法最好”的统一结论。

#### RIFE VFI

当前值：

- ckpt_name = rife47.pth
- clear_cache_after_n_frames = 10
- multiplier = 2
- fast_mode = True
- ensemble = True
- scale_factor = 1

#### GIMMVFI_interpolate

当前值：

- ds_factor = 1
- interpolation_factor = 2
- seed = 533662968663336
- output_flows = False

#### 放大链

当前值：

- Upscale 模型 = 4x-AnimeSharp.pth
- ImageScaleBy.upscale_method = nearest-exact
- ImageScaleBy.scale_by = 0.25

这里真正生效的数学关系是：

- Upscale ratio 滑块 -> Calcul ratio（除以 4）-> ImageScaleBy.scale_by

所以后续测试时，不应该直接改 ImageScaleBy 面板上的 1，而应该改上游 Upscale ratio 滑块。

---

## 7. 输出节点当前值

### 7.1 Output

当前值：

- images：来自 ColorMatch
- frame_rate：16
- filename_prefix：WAN/%date:yyyy-MM-dd%/%date:hhmmss%_OG
- format：video/h264-mp4
- pix_fmt：yuv420p
- crf：19
- save_metadata：True
- trim_to_audio：False
- pingpong：False
- save_output：True

### 7.2 Frame skip + last frame interpolation

当前值：

- images：来自 overlap 拼接分支
- frame_rate：16
- filename_prefix：WAN/%date:yyyy-MM-dd%/%date:hhmmss%_FS
- format：video/h264-mp4
- pix_fmt：yuv420p
- crf：19
- save_metadata：False
- save_output：False

### 7.3 Save Interpoled

当前值：

- images：来自 GIMMVFI 后截取分支
- frame_rate：32
- filename_prefix：WAN/%date:yyyy-MM-dd%/%date:hhmmss%_IN
- format：video/h264-mp4
- pix_fmt：yuv420p
- crf：19
- save_metadata：True
- save_output：True

### 7.4 Save Upscaled

当前值：

- images：来自 upscaler 分支
- frame_rate：32
- filename_prefix：WAN/%date:yyyy-MM-dd%/%date:hhmmss%_UP
- format：video/h264-mp4
- pix_fmt：yuv420p
- crf：19
- save_metadata：False
- save_output：True

VideoHelperSuite 的节点说明里，frame_rate 的官方说明非常明确：它决定输出视频的帧率；如果带音频而帧率设置不正确，会导致音频不同步。当前这张图虽然没有接音频，但这个字段仍然直接决定输出 fps。

---

## 8. 后续测试时该怎么调整参数

这一节不写“推荐值”，只写“如果你的测试目标是 X，当前最直接、最不容易误判的入口在哪里”。

### 8.1 想测试时长和帧数

优先改：

- Duration
- Frame rate

原因：

- Duration 不是直接改输出 fps，而是通过 calculFrames 和 addFirst frame 决定 Painter.length。
- Frame rate 一路决定基础输出 fps，一路和 GIMMVFI Interpolation 一起决定 545 / 611 的 fps。

当前公式：

- Painter length = Duration x Frame rate，再取整后 + 1
- Save Interpoled / Save Upscaled fps = Frame rate x GIMMVFI Interpolation

所以：

- 想改镜头总帧数，先动 Duration 和 Frame rate。
- 不要先去改 Painter 面板里显示的 81，因为它当前已被上游公式覆盖。

### 8.2 想测试运动强弱

优先改：

- Motion amplitude

原因：

- 它直接进 PainterFLF2V.motion_amplitude。
- 这是当前图里唯一被明确做成“运动幅度总控”的滑块。

目前官方 tooltip 只明确说明了两个锚点：

- 1.0 = Official Original
- 2.0 = High-Speed Dynamic

除此之外，当前官方来源未给出统一推荐值。

### 8.3 想测试采样预算

优先改：

- Steps
- CFG
- Seed

原因：

- Steps 同时喂给 High sampler 和 Sampler 2 low。
- High sampler 的 steps_to_run 不是独立滑块，而是当前由 Steps / 2 得到。
- Seed 当前只直接接到 High sampler。

这意味着：

- 如果你只想统一提高或降低主采样预算，先改 Steps。
- 如果你想测试 High sampler 的 steps_to_run 比例，就不能只盯着 High sampler 本体，要看上游 calculSteps。
- 如果你想固定复现当前 High sampler，当前种子是 365139824204464。

### 8.4 想测试速度调节对采样模型的影响

优先改：

- Speed

原因：

- 它直接同时驱动两个 ModelSamplingSD3.shift。
- High / Low 两条模型路由都会一起吃这个值。

所以这是当前图里最直接的“高低噪共同速度调节入口”。

### 8.5 想测试分辨率入口

优先改：

- Height

原因：

- 它直接接到 Resize First.height。
- Resize First.width 当前固定为 0，method = keep proportion，multiple_of = 32。

当前不能写成确定结论的地方是：

- 起始图片文件当前不在工作区内，所以本文无法从本地文件继续确认 Resize First 最终算出来的实际宽度。

因此测试时要注意：

- 你现在改的是“目标高度”，宽度仍然取决于输入图比例和 ImageResize+ 的 keep proportion 逻辑。

### 8.6 想测试提示词来源

先分两种情况：

- 如果你要测手工提示词：改 Positive / Negative 文本。
- 如果你要测自动提示词：先把 Automatic prompt 分组从 BYPASS 切回 ACTIVE，再测 Florence 链路。

原因：

- 当前自动提示词链的节点都是 mode = 4，也就是 BYPASS。
- 当前手工 Positive 和 Negative 仍然明确连到了 Positive Encode / Negative Encode。

### 8.7 想测试首尾过渡

优先改：

- Start frame
- End frame
- Frame overlap Interpolation

原因：

- overlap 分支的有效帧数公式是 image_count - start_frame - end_frame。
- RIFE multiplier 由 Frame overlap Interpolation 滑块直接控制。
- 这个分支对应的是单独的 Frame skip + last frame interpolation 输出，不是基础 Output。

所以：

- 想看首尾过渡，重点盯 541 这个输出，不要只看 398。

### 8.8 想测试插帧输出

优先改：

- GIMMVFI Interpolation
- Frame rate

原因：

- GIMMVFI Interpolation 直接决定 GIMMVFI_interpolate.interpolation_factor。
- 同时它还会和 Frame rate 一起决定 Save Interpoled / Save Upscaled 的输出 fps。

当前公式：

- 插帧输出 fps = Frame rate x GIMMVFI Interpolation

### 8.9 想测试放大输出

优先改：

- Upscale ratio
- 必要时再看 UpscaleModelLoader 和 ImageScaleBy

原因：

- 当前图里真正暴露给测试的入口是 Upscale ratio。
- 它不是直接进放大模型，而是先被 Calcul ratio 做除以 4，再送到 ImageScaleBy.scale_by。
- 当前放大模型是 4x-AnimeSharp.pth。

因此在当前工作流设计下：

- 如果你要测“最终放大倍率入口”，先动 Upscale ratio。
- 不要直接改 ImageScaleBy 面板里的 1，因为那不是当前实际生效值。

### 8.10 想测试色彩回拉

优先改：

- ColorMatch.method
- ColorMatch.strength

原因：

- 基础输出 398 直接吃的是 ColorMatch 的输出。
- 当前 method = mkl，strength = 1。

官方定义提供了 method 选项，但没有给“哪种方法更好”的统一推荐值。

---

## 9. 哪些地方现在不能写成确定结论

下面这些点，目前证据不够，不能写成确定推荐：

1. 当前起始图的真实尺寸。因为工作流引用的本地图文件当前不存在于工作区里，本文无法从文件本身确认 Resize First 的最终宽度。
2. 当前自动提示词 BYPASS 后，StringConcatenate.string_a 在运行时的精确旁路表现。能确认的是这条链被 BYPASS，不能把某一种具体旁路语义写成官方行为。
3. High / Low Enhance、NAG、ColorMatch、RIFE、GIMMVFI、Upscaler 的“最佳值”。当前官方来源给了参数定义，但没有统一推荐值。
4. 当前是否存在隐藏的 LoRA 配置。因为 Power Lora Loader 序列化结果是空结构，本文不能补猜历史配置。

---

## 10. 最短结论

如果你后续要做测试，当前最该盯住的不是节点面板里那些残留值，而是下面这些总入口：

- 时长：Duration + Frame rate
- 运动：Motion amplitude
- 采样预算：Steps + CFG + Seed
- 高低噪共同速度：Speed
- 分辨率入口：Height
- 手工提示词：Positive / Negative
- 自动提示词测试：先解除 Automatic prompt 的 BYPASS
- 首尾过渡：Start frame + End frame + overlap Interpolation
- 插帧：GIMMVFI Interpolation
- 放大：Upscale ratio

这几个入口之所以优先，不是经验判断，而是因为它们当前确实通过连线直接控制了后面的关键节点。