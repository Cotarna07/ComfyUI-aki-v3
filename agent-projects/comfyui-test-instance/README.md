# ComfyUI 测试实例与多环境管理

这个项目用于在当前工作区里启动与主实例并行的 ComfyUI 测试环境。它最早只管理一套“第二实例”，现在扩展为按环境名管理多套测试实例。

目标是隔离这些内容：

- 端口
- user 目录
- input / output / temp 目录
- custom_nodes 启用集合
- 可选 overlay `.venv`

默认共享以下内容：

- ComfyUI 主代码：`D:\ComfyUI-aki-v3\ComfyUI`
- 模型目录：`D:\ComfyUI-aki-v3\ComfyUI\models`

## 当前命名环境

| 环境名 | 端口 | 用途 |
|---|---:|---|
| `aki-main-py313-cu130` | 8188 | 当前秋叶主环境，只登记，不由本项目创建 |
| `wan-video-py313-cu130` | 8189 | Wan 视频工作流测试 |
| `flux-kontext-py313-cu130` | 8190 | FLUX/Kontext/商品图编辑测试 |
| `legacy-pmrf-py311-cu124` | 8191 | PMRF/NATTEN/RealESRGAN 旧依赖沙箱，需外部 Python |
| `api-bridge-py313` | 8192 | 调用局域网 TTS/LLM/翻译/字幕 API |
| `ltx-video-py313-cu130` | 8193 | LTX/LX 视频、导演、修复、音频潜空间工作流测试 |

## 目录说明

- `config/plugins.json`
  旧版第二实例要启用的插件清单，保留兼容。
- `config/environments.json`
  多环境清单：环境名、端口、运行根目录、Python 策略、插件集合。
- `scripts/setup_instance.ps1`
  旧版单实例初始化脚本，保留兼容。
- `scripts/start_instance.ps1`
  旧版单实例启动脚本，保留兼容。默认端口也是 `8190`，不要和 `flux-kontext-py313-cu130` 同时启动。
- `scripts/setup_environment.ps1`
  按环境名初始化运行根目录、模型共享链接、插件链接；可选创建环境自己的 overlay `.venv`。
- `scripts/start_environment.ps1`
  按环境名启动 ComfyUI。
- `scripts/list_environments.ps1`
  打印当前登记的环境清单。
- `scripts/launch_environment_panel.ps1`
  Windows 按钮式启动面板。
- `scripts/install_environment_requirements.ps1`
  用指定环境的 Python 安装该环境插件清单中的 `requirements.txt`，避免误装到主环境。
- `scripts/install_plugin_requirements.ps1`
  旧版单实例依赖安装脚本，保留兼容。
- `runtime/environments/<env-name>/`
  多环境实际 base directory。该目录被 Git 忽略，允许包含 `.venv`、`custom_nodes` Junction、独立数据库和运行产物。

## 推荐用法

列出环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\list_environments.ps1
```

初始化所有可管理环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\setup_all_environments.ps1
```

如果要同时创建 overlay `.venv`：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\setup_all_environments.ps1 -CreateVenvs
```

启动环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start_environment.ps1 -Name wan-video-py313-cu130
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start_environment.ps1 -Name flux-kontext-py313-cu130
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start_environment.ps1 -Name api-bridge-py313
```

便捷启动入口：

双击这个文件可以打开按钮式启动面板：

```text
agent-projects/comfyui-test-instance/ComfyUI-Environment-Launcher.vbs
```

命令行启动方式仍然保留：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-wan-video.ps1
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-ltx-video.ps1
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-flux-kontext.ps1
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-api-bridge.ps1
```

给指定环境安装插件依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\install_environment_requirements.ps1 -Name flux-kontext-py313-cu130 -PluginName ComfyUI_LayerStyle
```

先只打印会安装到哪里，不真正执行 pip：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\install_environment_requirements.ps1 -Name flux-kontext-py313-cu130 -PluginName ComfyUI_LayerStyle -DryRun
```

## 当前已验证状态（2026-05-17）

- `scripts/setup_instance.ps1` 已实测创建 `runtime/instance/`，并建立共享 `models` Junction 与按清单生成的 `custom_nodes` Junction。
- Windows PowerShell 5.1 对脚本中的中文提示字符串存在解析风险；当前 `setup_instance.ps1` 与 `start_instance.ps1` 的控制台提示已统一改为 ASCII 文本。
- `scripts/start_instance.ps1` 现已显式传入 `--database-url`，第二实例使用 `runtime/instance/user/comfyui.db`，避免与主实例争用 `ComfyUI/user/comfyui.db`。
- 已实测同一会话中主实例 `http://127.0.0.1:8188/system_stats` 与第二实例 `http://127.0.0.1:8190/system_stats` 均返回 `200`，说明两套实例可以并行在线。
- 当前默认仍复用主嵌入式 Python；项目自己的 overlay `.venv` 仍是可选增强项，只有在执行 `setup_instance.ps1 -CreateOverlayVenv` 时才会创建。

## 是否能同时运行

可以。

前提是：

- 端口不同
- 两套实例不要同时跑重视频任务抢同一块 GPU 显存

## 当前方案的隔离级别

当前脚本默认是“中隔离”方案：

- 主代码共享
- 模型共享
- custom_nodes 按清单链接
- user / input / output / temp 独立
- 数据库独立（`runtime/instance/user/comfyui.db`）
- 可选 overlay `.venv`

如果后续需要更强隔离，可以把第二实例再迁移到单独的 Python 解释器或单独的 ComfyUI 副本，但当前这一步已经足够做插件测试和工作流冒烟。

## 多环境规则（2026-05-30）

- `aki-main-py313-cu130` 是当前主环境，不作为新节点试验场。
- `wan-video-py313-cu130` 用来测 Wan 视频类工作流。
- `ltx-video-py313-cu130` 用来测 LTX/LX 视频、导演、IC-LoRA、音频潜空间和修复类工作流。
- `flux-kontext-py313-cu130` 用来测 FLUX/Kontext/商品图编辑类工作流。
- `api-bridge-py313` 用来接局域网音频、LLM、翻译、字幕服务，不重复部署本地 `IndexTTSRun` 或 `llama_cpp_*`。
- `legacy-pmrf-py311-cu124` 只先创建目录和插件链接；必须准备好兼容 Python/Torch/CUDA 后再配置 `external_python` 启动。
- 从 ComfyUI Manager 或插件 prestartup 触发的自动安装，会安装到“当前正在运行的 ComfyUI 使用的 Python”。要装到测试环境，必须先启动对应端口的环境，再在那个页面里安装。
- 详细规则见 `agent-skills/docs/comfyui_runtime_environments.md`。
