# Skills 功能说明

这份文档按学习路径解释当前本地 skill pack 中每个技能的用途、所需输入、当前状态，以及它适合帮助你理解哪一类 ComfyUI 能力。

## 状态说明

- ready：现在就能通过 generate_video.py 直接执行，不需要先导出 API 工作流
- export-needed：已经注册好了，但还需要先把 UI 工作流导出一次到 agent-skills/comfyui/workflows/01-shared/

## 学习路径

### 入门

这一组适合先上手，因为要么已经可以直接运行，要么概念非常清晰。

#### wan22_t2v_fast

- 状态：ready
- 模式：文生视频
- 输入：prompt，可选 negative_prompt、width、height、length、fps、seed
- 功能：运行内置的 Wan 2.2 Lightx2v 4 步文生视频工作流。
- 你能学到：本地视频生成的最小闭环、双阶段采样、外部模型包管理。
- 适合场景：基线质量检查、提示词试验、整套环境是否可用的第一条验证链路。

#### video_upscale_gan_api

- 状态：ready
- 模式：视频超分
- 输入：video，可选 model_name、video_start_time、video_duration
- 功能：加载原视频，默认只切前 2 秒做预览，再做 GAN x4 超分，并重新编码成 mp4。
- 你能学到：视频后处理、帧拆解与重组、为什么视频链路必须控制内存占用。
- 适合场景：先快速判断某段视频是否值得做超分，而不是一上来就整段处理。

#### video_stitch_api

- 状态：ready
- 模式：视频拼接对比
- 输入：video、video_1，可选 direction、match_image_size、spacing_width、spacing_color、video_start_time、video_duration
- 功能：加载两条视频，提取帧后左右或上下拼接，再重新生成一条对比视频。
- 你能学到：前后对比工作流、逐帧后处理、如何构建 before/after 评审视频。
- 适合场景：比较不同模型、不同提示词、不同参数、不同超分或修复结果。

#### lotus_depth_map_api

- 状态：export-needed
- 模式：图像分析
- 输入：image，可选 depth_intensity
- 功能：把单张图片转成深度图。
- 你能学到：结构条件准备、深度提取，以及分析节点如何服务后续生成节点。
- 适合场景：后续想做深度引导的图像或视频生成之前，先准备结构参考。

### 进阶

这一组开始进入真正的受控生成、多输入条件和图像编辑。

#### wan22_i2v_api

- 状态：export-needed
- 模式：图生视频
- 输入：prompt、image
- 功能：用 Wan 2.2 把参考图动画化。
- 你能学到：图生视频和文生视频在条件注入、运动锚定上的区别。
- 适合场景：把插画、渲染图、照片转成短动画镜头。

#### ltx2_t2v_api

- 状态：export-needed
- 模式：文生视频
- 输入：prompt
- 功能：运行 LTX-2 蒸馏版文生视频工作流。
- 你能学到：第二套视频模型家族和 Wan 的差异，尤其是速度和提示词风格差别。
- 适合场景：对比 Wan 和 LTX 的成片风格、运动特征和速度。

#### ltx2_i2v_api

- 状态：export-needed
- 模式：图生视频
- 输入：prompt、image
- 功能：用 LTX-2 做参考图动画。
- 你能学到：LTX 在参考帧条件和时间结构上的处理方式。
- 适合场景：需要测试 LTX 风格图生视频时。

#### ltx2_canny_to_video_api

- 状态：export-needed
- 模式：控制图生视频
- 输入：prompt、image，可选 first_frame、strength、width、height、length
- 功能：把 canny 边缘图作为结构控制信号来驱动 LTX 视频生成。
- 你能学到：显式结构控制、边缘引导运动、控制图如何约束构图。
- 适合场景：草图动画、线稿驱动视频、轮廓一致性要求高的镜头。

#### ltx2_depth_to_video_api

- 状态：export-needed
- 模式：视频到视频
- 输入：prompt、video，可选 first_frame、strength、width、height、length
- 功能：用深度参考来引导 LTX 的视频生成或变换。
- 你能学到：时序结构约束和深度驱动的一致性控制。
- 适合场景：希望保留原视频结构，但重新解释风格或内容。

#### ltx2_pose_to_video_api

- 状态：export-needed
- 模式：控制图生视频
- 输入：prompt、control_image，可选 first_frame、strength、width、height、length
- 功能：用姿态图或控制图来驱动主体动作。
- 你能学到：动作约束与外观约束如何拆开处理。
- 适合场景：人物动作迁移、角色动画、姿态驱动镜头。

#### qwen_image_edit_api

- 状态：export-needed
- 模式：图像编辑
- 输入：image、prompt，可选 image2、image3
- 功能：用 Qwen Image 2511 对一张或多张参考图进行编辑。
- 你能学到：指令式图像编辑、多参考图条件混合。
- 适合场景：概念图迭代、风格迁移、参考图混合。

#### qwen_image_inpaint_api

- 状态：export-needed
- 模式：图像局部重绘
- 输入：image、mask、prompt
- 功能：用 Qwen Image 加局部修补控制网络，对掩码区域进行替换或修复。
- 你能学到：局部编辑、掩码驱动修改、区域替换而不推翻整张图。
- 适合场景：修手、改物体、局部换细节。

#### qwen_image_outpaint_api

- 状态：export-needed
- 模式：图像外扩
- 输入：image，可选 prompt、left、top、right、bottom、feathering
- 功能：向画布四周扩展并补全新内容。
- 你能学到：扩图、边缘融合、画布扩展型提示词控制。
- 适合场景：改构图、加留白、做更宽画幅。

### 高阶

这一组更适合在前面都熟悉之后再学，因为它们涉及视频修补、多模态理解或 3D 输出。

#### wan_vace_api

- 状态：export-needed
- 模式：视频修补
- 输入：video、mask
- 功能：对整段视频里的掩码区域进行时序一致的重绘或修补。
- 你能学到：视频局部重绘、视频掩码、跨帧一致性修复。
- 适合场景：去物体、修局部瑕疵、替换镜头局部内容。

#### ltx2_v2v_detailer_api

- 状态：export-needed
- 模式：视频到视频细化
- 输入：video，可选 prompt
- 功能：对已有视频做二次细化和增强。
- 你能学到：后处理型视频 refinement 流程。
- 适合场景：一条片子已经差不多可用，但还想做第二遍打磨。

#### video_caption_gemini_api

- 状态：ready
- 模式：视频分析
- 输入：video，可选 prompt、analysis_model、system_prompt、video_start_time、video_duration、seed
- 功能：把视频喂给 Gemini，并把分析文本直接保存为 txt 文件。
- 你能学到：ComfyUI 里的多模态视频理解，以及本地编排和云端推理的边界。
- 适合场景：视频解说、镜头总结、内容分析、复盘现有素材。
- 注意：需要当前 ComfyUI 环境已经配置好 Gemini 凭据。

#### image_caption_gemini_api

- 状态：ready
- 模式：图像分析
- 输入：image，可选 prompt、analysis_model、system_prompt、seed
- 功能：把图片喂给 Gemini，并把分析文本直接保存为 txt 文件。
- 你能学到：图像理解、提示词提取、参考图拆解。
- 适合场景：做参考图分析、草拟提示词、整理素材说明。
- 注意：需要当前 ComfyUI 环境已经配置好 Gemini 凭据。

#### prompt_enhance_api

- 状态：ready
- 模式：提示词增强
- 输入：prompt，可选 image、analysis_model、system_prompt、seed
- 功能：用 Gemini 把一段原始提示词改写成更适合图像或视频生成模型理解的版本，并保存为 txt。
- 你能学到：提示词重写，以及语言模型如何嵌入 ComfyUI 工作流前处理。
- 适合场景：把一句很短的想法扩写成更完整的生成提示词。
- 注意：需要当前 ComfyUI 环境已经配置好 Gemini 凭据。

#### hunyuan3d_image_to_model_api

- 状态：export-needed
- 模式：图像转 3D
- 输入：image
- 功能：用 Hunyuan3D 2.1 从单张图重建 3D 网格。
- 你能学到：2D 到 3D 的资产生成链路。
- 适合场景：概念转 mesh、轻量级 3D 试验。

## 接下来最值得优先打通的技能

如果你想继续把 export-needed 逐步变成 ready，建议按这个顺序推进：

1. wan22_i2v_api
2. ltx2_t2v_api
3. qwen_image_inpaint_api
4. lotus_depth_map_api
5. wan_vace_api

这个顺序能兼顾动画化、替代视频模型、局部修复、结构分析和视频修补。

## 如何把 export-needed 变成 ready

1. 在 ComfyUI 界面里打开源工作流。
2. 从界面导出 API JSON。
3. 把导出的文件保存到 agent-skills/comfyui/workflows/01-shared/ 中，对应 registry.json 里声明的路径。
4. 重新运行 generate_video.py --list-skills，确认状态从 export-needed 变成 ready。