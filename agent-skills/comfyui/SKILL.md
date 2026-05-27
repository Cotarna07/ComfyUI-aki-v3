# ComfyUI 跨代理技能包说明

这个工作区提供了一层本地、与代理实现无关的 ComfyUI skill 层，供 GitHub Copilot、Codex 以及其他编码代理共同使用。

## 适用范围

当任务涉及以下内容时，应优先使用这套 skill 包：

- 运行 ComfyUI 的图像或视频工作流
- 检查或下载缺失模型
- 把工作流整理成可重复执行的自动化形式
- 自动覆写提示词、seed、图片或视频输入
- 排查这套本地 Aki 包上的工作流执行问题

## 首要动作

1. 先读取 agent-skills/comfyui/registry.json。
2. 确认服务可通过 http://127.0.0.1:8188 访问。
3. 不要假设节点类名、模型文件名或节点编号，必要时通过 /object_info 和 /system_stats 查询。
4. 自动化优先使用 API 格式工作流。
5. 模型统一使用 ComfyUI 原生目录 D:/ComfyUI-aki-v3/ComfyUI/models。

## 本地关键路径

- 模型根目录：D:/ComfyUI-aki-v3/ComfyUI/models
- 生成文件目录：D:/ComfyUI-aki-v3/ComfyUI/output
- 注册表：agent-skills/comfyui/registry.json
- 总工作流目录：agent-skills/comfyui/workflows/
- 共享正式层：agent-skills/comfyui/workflows/01-shared/
- 项目模板层：agent-skills/comfyui/workflows/02-project/
- 来源草稿层：agent-skills/comfyui/workflows/03-source/
- 源蓝图目录：ComfyUI/blueprints/

## 工作流规则

- 内置直跑目前至少包括 wan22_t2v_fast、video_upscale_gan_api、video_stitch_api，以及 Gemini 相关分析技能。
- 对于完整 UI 工作流，优先采用“导出一次 API JSON”模式；跨项目复用模板保存到 agent-skills/comfyui/workflows/01-shared/，项目专用模板保存到 agent-skills/comfyui/workflows/02-project/<project>/。
- 外部导入、供应商示例和待整理草稿先落到 agent-skills/comfyui/workflows/03-source/，不要直接混入正式层。
- 如果 /workflow/convert 不稳定或不可用，不要把它作为生产链路依赖。
- 对用户提供的 API JSON，先检查图结构，再决定如何覆写 prompt、seed 或媒体输入。

## 质量优先任务规则

- 用户要求质量优先时，第一阶段必须在当前设备上选择任务适配、可稳定执行的最高质量配置，产出可评价的实用效果，不因节省时间而无依据降低质量。
- 本地可使用适配显存的 fp8/量化、较小同系模型或受控尺寸作为实测配置；必须记录模型、精度、尺寸、采样、提示词与质量短板，并与已运行基线比较。
- 第二阶段仅在本地路线已经证明有效后进行：记录同系更大/更高精度模型、VAE、LoRA、控制节点和预计云算力，以云端提高质量上限，而不是以未验证的大模型下载替代本机测试。
- 对商品类输入，必须分别评估画面美术质量与商品结构忠实度；不能用“保真”掩盖画面低质，也不能用“好看”掩盖商品结构被错误改写。
- 涉及商品图优化、商品广告主视觉或真实性验收时，额外读取 `agent-skills/comfyui/skills/comfyui-product-image-integrity/SKILL.md`，按真实展示与创意主视觉分流执行并通过商品身份检查。

## API 队列可见性

- ComfyUI 已安装 Queue Manager：ComfyUI/custom_nodes/comfyui-queue-manager，用于统一查看网页队列和代理后台提交的任务。
- 代理调用 /prompt API 时，必须使用可识别的 client_id，例如 agent:<代理名>|workflow:<工作流名>|run:<短ID>。
- 调用 /prompt API 时，extra_data 建议至少包含 agent、workflow_name、source、notes，方便 Queue Manager 或 history 页面显示来源。
- 临时覆写 prompt、seed、模型、LoRA、尺寸、帧数或输入媒体时，必须写入 extra_data.notes，并在最终回复里告知用户。
- 后台 API 排队不会自动改变 Chrome 画布；用户要求界面同步时，先保存或加载对应工作流，再执行。

## 常用命令

列出技能：

```powershell
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe generate_video.py --list-skills
```

检查或下载模型包：

```powershell
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe download_models.py --check --all-packs
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe download_models.py --all-packs
```

运行内置 Wan 2.2 文生视频技能：

```powershell
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe generate_video.py --skill wan22_t2v_fast --prompt "一只狐狸在雪地中奔跑"
```

运行需要先导出 API 的图生视频技能：

```powershell
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe generate_video.py --skill wan22_i2v_api --prompt "电影感缓慢推进镜头" --image d:/path/to/reference.png
```

## 导出一次模式

对于后续更多技能，推荐流程如下：

1. 在 ComfyUI 界面中加载源工作流。
2. 从界面导出 API JSON。
3. 共享模板保存到 agent-skills/comfyui/workflows/01-shared/；项目模板保存到 agent-skills/comfyui/workflows/02-project/<project>/。
4. 在 agent-skills/comfyui/registry.json 中新增或更新 skill 条目。

## 排障规则

- 缺模型：运行 download_models.py，并指定 skill 名或 workflow 路径。
- 缺节点：查看失败节点的 class_type，并核对 ComfyUI/custom_nodes/ 中对应插件是否存在且已加载。
- 显存不足：先选择本机可运行的同系高质量配置并标记参数与限制，用其验证方案是否实用；已验证可行后，再将同路线迁移到足够显存/算力的环境提高最终质量。
- 新增模型文件或调整原生 models 目录内容后：重启 ComfyUI，让模型下拉列表和节点缓存刷新干净。
