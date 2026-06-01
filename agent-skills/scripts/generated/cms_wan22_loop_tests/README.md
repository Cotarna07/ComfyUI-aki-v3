# CMS Wan2.2 Loop 120 帧参数测试方案

## 目标

基于用户区工作流：

`agent-skills/comfyui/workflows/TEST/26-5-31/CMS-26-5-31 WAN2.2_LOOP_NATIVE_UPSCALER.json`

保留当前提示词，固定 120 帧长度，测试 5 组参数对输出质量、运动幅度、稳定性、插帧和放大效果的影响。

## 执行原则

- 不修改原始 TEST 工作流，只在 runtime 中生成本次测试变体。
- 默认固定同一个 seed，确保差异主要来自参数。
- 每个 case 提交前后调用 ComfyUI `/free`，请求卸载模型和释放显存。
- 默认只跑原工作流的主输出 `OG`；RIFE 的 `Frame skip + last frame interpolation` 临时视频链默认关闭，否则即使 `save_output=false` 也会被输出节点触发计算。
- 默认扫描 `ComfyUI/output/WAN/agent_tests/cms_wan22_loop_120/`，已有 `*_OG_*.mp4` 的 case 会自动跳过，不重复测试已完成参数。
- 原工作流里禁用的 GIMMVFI 插帧与 native upscaler 输出链需要显式加 `-EnablePostprocess` 才开启；这条链更慢，并且当前环境可能因为 CUDA headers 缺失在 GIMMVFI 节点报错。
- 脚本串行提交 5 组任务，完成后生成 `report.html`。

## 5 组参数

| case | 目的 | 主要变化 |
|---|---|---|
| `p01_baseline` | 基线 | steps 8, cfg 1.2, motion 1.0, interpolation 2, upscale 1.0 |
| `p02_low_guidance` | 降低过强引导 | cfg 0.95, NAG 8.5/0.2/2.1, LoRA 0.75 |
| `p03_detail_push` | 推细节 | steps 10, cfg 1.35, enhance 1.2 |
| `p04_motion_push` | 推运动 | speed 7.0, motion 1.4 |
| `p05_smooth_motion` | 推稳定平滑 | speed 4.0, motion 0.8, cfg 1.05, NAG 9.5/0.22/2.2 |

## 一键运行

双击或命令行运行：

```powershell
agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.bat
```

默认输出文件较少，只保留报表、manifest 和日志。需要保留每组 UI/API/history JSON 快照时加 `-FullArtifacts`。
如果确实要重跑已经有输出的 case，加 `-RerunCompleted`。

PowerShell 直接运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1
```

只生成变体和 HTML 空报表、不提交 ComfyUI：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -DryRun
```

只跑基线：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -Only p01_baseline
```

只跑剩下三组参数：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -Only p03_detail_push,p04_motion_push,p05_smooth_motion
```

`-Only` 同时支持逗号分隔和空格分隔。

## 3 组模型 / LoRA 搭配矩阵

在本次 5 组参数基础上，可以额外展开 3 组模型 / LoRA profile；总共最多 15 个视频。
当前默认 3 组已经剔除之前的 `m01_current_q8_nsfw` 和 `m02_official_q4_lightx2v`，重点观察非官方 LoRA 搭配差异。

| profile | 模型 / LoRA 搭配 | 目的 |
|---|---|---|
| `m03_q8_svi_pro` | `DasiwaWAN22I2V14BTastysinV8_q8High/Low.gguf` + `WAN2.2\SVI_Wan2.2-I2V-A14B_*_lora_v2.0_pro.safetensors` | 非官方 Pro LoRA，对照动作、细节和主体稳定性 |
| `m04_q8_cumv2` | `DasiwaWAN22I2V14BTastysinV8_q8High/Low.gguf` + `WAN2.2\Wan22_CumV2_High/Low.safetensors` | 固定底模，测试另一组 LoRA 对画面倾向和动作强度的影响 |
| `m05_q8_g4gg1ng` | `DasiwaWAN22I2V14BTastysinV8_q8High/Low.gguf` + `WAN2.2\wan22-G4GG1NGv6-11epoc-high/low-i2v-k3nk.safetensors` | 固定底模，测试更明显风格/动作 LoRA 的差异 |

一键跑 3×5：

```powershell
agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_model_lora_matrix.bat
```

PowerShell 直接运行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -AllModelProfiles
```

只跑其中某一组 profile：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -ModelProfiles m04_q8_cumv2
```

只跑某些参数和某些 profile：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -ModelProfiles m04_q8_cumv2,m05_q8_g4gg1ng -Only p03_detail_push,p05_smooth_motion
```

旧的 `m01_current_q8_nsfw` 和 `m02_official_q4_lightx2v` 仍可用 `-ModelProfiles` 手动指定，但不会被 `-AllModelProfiles` 默认包含。

模型 profile 输出会按 profile 分目录保存：

`ComfyUI/output/WAN/agent_tests/cms_wan22_loop_120/<run-id>/<profile>/<case>_OG_00001.mp4`

默认仍会跳过已存在的同 profile + case 输出；如果要强制重跑，加 `-RerunCompleted`。

开启插帧 / 放大后处理链：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -EnablePostprocess
```

如果确实需要同时生成原工作流里的 FS 临时预览视频，再加：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\start_cms_wan22_loop_matrix.ps1 -EnableFrameSkipPreview
```

## 输出位置

每次运行会创建：

`agent-skills/comfyui/runtime/cms_wan22_loop_matrix/<run-id>/`

主要文件：

- `report.html`：最终 HTML 报表。
- `manifest.csv` / `manifest.json`：参数、任务 ID、输出文件记录。
- `workflow_variants/*.ui.json`：仅 `-FullArtifacts` 时保存。
- `api_prompts/*.api.json`：仅 `-FullArtifacts` 时保存。
- `run.stdout.log` / `run.stderr.log`：完整执行日志。
- `history/*.json`：仅 `-FullArtifacts` 时保存。

视频输出在：

`ComfyUI/output/WAN/agent_tests/cms_wan22_loop_120/<run-id>/`

## 音频建议

不要把音频加入这 5 组视觉参数测试里，否则会让测试耗时和变量变复杂。执行流程是：

1. 先跑视觉矩阵，选出最好的 1 个视频。
2. 再对选中的视频单独加音频。
3. 本脚本使用本地音频素材 + ffmpeg 循环/裁剪到视频长度，输出一个新 mp4。

按视频路径执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\add_audio_to_video.ps1 `
  -Video "D:\ComfyUI-aki-v3\ComfyUI\output\WAN\agent_tests\cms_wan22_loop_120\<run-id>\<case>_OG_00001.mp4" `
  -Audio "D:\path\to\bgm.mp3" `
  -Overwrite
```

按 run id 和 case 自动查找最新视频：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File agent-skills\scripts\generated\cms_wan22_loop_tests\add_audio_to_video.ps1 `
  -RunId "<run-id>" `
  -CaseId "p03_detail_push" `
  -Audio "D:\path\to\bgm.mp3" `
  -Overwrite
```

输出默认在原视频同目录，文件名追加 `_AUDIO.mp4`。
