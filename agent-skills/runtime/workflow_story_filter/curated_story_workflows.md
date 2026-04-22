# 剧情向工作流筛选结果

扫描时间：2026-04-21  
扫描目录：`D:/ComfyUI-Models/comfyui_workflow`  
扫描结果：311 个 JSON，机器粗筛出 82 个“优先测试”、10 个“候选”。下面是人工二次筛后的剧情向清单。

## 筛选标准

剧情向优先级从高到低：

1. 首尾帧/关键帧：适合按分镜推进故事。
2. 长视频/续帧：适合把多个镜头接成片段。
3. 图生视频/文生视频：适合单镜头生成。
4. 动作/表情/角色迁移：适合保持人物一致性。
5. 音频/口型：适合台词、独白和数字人。
6. VACE/视频转绘/高清修复：适合后期统一风格和补救。

## 当前环境判断

当前 ComfyUI 已可见的关键模型：

- `wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_t2v_low_noise_14B_fp8_scaled.safetensors`
- `wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors`
- `wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors`
- `wan_2.1_vae.safetensors`
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`

当前常见缺口：

- GGUF 工作流需要 `wan2.2_*_Q4/Q8.gguf`，当前 `UnetLoaderGGUF` 可用，但下拉列表为空。
- 很多 WanVideoWrapper 示例引用 `Wan2_1-*`、`umt5-xxl-enc-bf16`、`Wan2_1_VAE_bf16`，文件在资料包内，但没放到 ComfyUI 模型目录，所以当前下拉不可见。
- 首尾帧和高级 I2V 常缺 `clip_vision_h.safetensors`。
- Sonic 口型缺 Sonic 节点和 `unet.pth`、`svd_xt_1_1.safetensors`。
- FantasyTalking 缺 `fantasytalking_fp16.safetensors`。

## 第一梯队：最值得优先改造成剧情链路

| 推荐 | 工作流 | 剧情价值 | 当前状态 | 建议用途 |
| --- | --- | --- | --- | --- |
| 1 | `4.工作流/workflows/5.图生视频类/04.MEGA Merge-WAN2.2-AllInOne-首尾帧-好用.json` | 首尾帧推进，最适合分镜到分镜 | 缺 `wan2.2-rapid-mega-aio-v4.safetensors`，缺 `Load Image Batch` 节点 | 主剧情镜头过渡 |
| 2 | `4.工作流/workflows/5.图生视频类/02.wan2.2首尾帧-好用.json` | 首尾帧 + WanVideoWrapper，适合角色从 A 动作过渡到 B 动作 | 缺 GGUF I2V 高低噪、GGUF T5、LightX2V LoRA，缺 3 个辅助节点 | 关键动作过渡 |
| 3 | `4.工作流/workflows/4.文生视频类/03.Wan2.2-AllInOne文生视频流-NF.json` | 最轻的文生视频剧情起手式 | 缺 `wan2.2-t2v-rapid-aio-v10-nsfw.safetensors`，缺 `LayerUtility: PurgeVRAM` | 建立空镜、环境、开场镜头 |
| 4 | `4.工作流/workflows/4.文生视频类/02.wan2.2文生视频.json` | 结构干净，节点基本可识别 | 缺 Q4 GGUF T2V 高低噪和一个 LightX2V LoRA | 文生视频基线 |
| 5 | `VACE14b工作流/节点/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_long_T2V_example_01.json` | 长视频 T2V 示例，适合长镜头测试 | 节点全识别；缺 `wan2.1_t2v_1.3B_fp16.safetensors` | 长镜头/连续动作 |
| 6 | `VACE14b工作流/节点/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_480p_I2V_example_02.json` | 图生视频结构清楚，适合人物静帧动起来 | 节点全识别；缺 `umt5_xxl_fp16`、`clip_vision_h` | 人物单镜头 |
| 7 | `VACE14b工作流/节点/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_vid2vid_example_01.json` | 视频生视频，适合已有片段重绘/延续 | 节点全识别；缺 `wan2.1_t2v_1.3B_fp16` | 续镜/风格统一 |
| 8 | `4.工作流/workflows/6.视频生视频/03.Wan2.2-Animate-动作迁移.json` | 动作迁移直接服务剧情人物表演 | 节点全识别；缺 DWPose、ClipVision、WanAnimate、Relight LoRA 等模型 | 人物动作复刻 |

## 第二梯队：剧情能力强，但补包成本更高

| 工作流 | 剧情价值 | 主要缺口 | 建议 |
| --- | --- | --- | --- |
| `4.工作流/workflows/6.视频生视频/05.WanAnimate动作+表情迁移.json` | 动作 + 表情迁移，非常适合角色表演 | SAM2、DWPose、ClipVision、WanAnimate、LoRA | 人物戏份多时再补 |
| `4.工作流/workflows/6.视频生视频/06.WanAnimate 人物A的动作+B的表情混合迁移.json` | 把动作和表情拆开迁移，剧情价值很高 | 同上，另有 GGUF Animate 模型缺口 | 适合精细表演 |
| `4.工作流/workflows/6.视频生视频/11.视频续帧GGUFQ4A.json` | 视频续帧，适合把镜头拉长 | 缺 GGUF I2V 高低噪、Lightning LoRA、`LoaderGGUF` 类名差异 | 补 GGUF 后测试 |
| `4.工作流/workflows/6.视频生视频/12.视频续帧GGUFQ8A.json` | 同上，质量可能更好，资源更重 | 同上 | 显存够再试 |
| `4.工作流/workflows/5.图生视频类/17.Wan2.2+SmoothMix首尾帧视频高动态.json` | 高动态首尾帧 | 缺 SmoothMix LoRA、ClipVision、`SimpleMath+` 等 | 做动作镜头备选 |
| `VACE14b工作流/节点/ComfyUI-WanVideoWrapper/example_workflows/wanvideo_I2V_FantasyTalking_example_01.json` | 图像 + 音频说话，适合台词镜头 | 缺 FantasyTalking 模型、ClipVision、辅助节点 | 比 Sonic 更贴 WanVideoWrapper |
| `4.工作流/workflows/7.音生视频类/01.Sonic-对口型.json` | 经典对口型数字人 | 缺 Sonic 节点和 Sonic 模型 | 只在需要口型同步时补 |
| `电商，换脸，转绘，老照片修复等等工作流/视频转绘（vace）/Wan2.1_VACE视频转绘工作流.json` | 视频转绘/修补，适合后期统一风格 | 缺 VACE GGUF、DWPose、Depth、LoRA | 后期链路，不做首发 |

## 不建议作为剧情主流程

- `8.高清放大类/*`：适合后期增强，不负责剧情生成。
- `9.依赖三方类/Ollama反推/*`：适合提示词反推，不负责视频生成。
- `FramePack超长图生视频工作流.json`：概念上适合长视频，但当前依赖 RunningHub/FramePack 专用节点，缺节点较多，本机不适合马上跑。
- 名称中带 `不太好用` 的 `15.Wan+Animate2.2主体混合mix魔改加速版V2（不太好用）.json`：先放弃。
- 明显 NSFW 命名的工作流：可以做结构参考，但剧情测试应改成安全提示词和安全素材。

## 推荐测试顺序

1. 先选一个文生视频：`02.wan2.2文生视频.json` 或 `03.Wan2.2-AllInOne文生视频流-NF.json`，做 2 秒开场镜头。
2. 再选一个首尾帧：`04.MEGA Merge-WAN2.2-AllInOne-首尾帧-好用.json`，做 A 图到 B 图的剧情转场。
3. 再选一个 I2V：`wanvideo_480p_I2V_example_02.json`，用角色静帧生成可控单镜头。
4. 再选一个续帧/V2V：`wanvideo_vid2vid_example_01.json` 或 `11/12.视频续帧GGUF`，测试能不能把镜头延长。
5. 如果人物表演是核心，再补 WanAnimate 相关模型，测试 `03.Wan2.2-Animate-动作迁移.json`。
6. 如果有对白，再测试 `wanvideo_I2V_FantasyTalking_example_01.json` 或 Sonic。

## 最终推荐组合

剧情短片不要押宝单个工作流，建议按链路组合：

1. Copax 或 Flux 先出角色关键帧。
2. 首尾帧工作流生成每个镜头的动作过渡。
3. WanVideoWrapper I2V 生成稳定人物单镜头。
4. V2V/续帧工作流把镜头延长。
5. F5-TTS 生成旁白，FantasyTalking/Sonic 只在需要口型时加入。
6. VACE/高清化放到最后做统一风格和修补。
