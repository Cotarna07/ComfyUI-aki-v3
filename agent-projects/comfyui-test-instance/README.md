# ComfyUI 第二测试实例

这个项目用于在当前工作区里启动一套与主实例并行的 ComfyUI 测试实例。

目标是隔离以下内容：

- 端口
- user 目录
- input / output / temp 目录
- custom_nodes 启用集合

默认共享以下内容：

- ComfyUI 主代码：`D:\ComfyUI-aki-v3\ComfyUI`
- 模型目录：`D:\ComfyUI-aki-v3\ComfyUI\models`

## 目录说明

- `config/plugins.json`
  测试实例要启用的插件清单。
- `scripts/setup_instance.ps1`
  初始化测试实例目录、模型共享链接、插件链接；可选创建项目自己的 overlay `.venv`。
- `scripts/start_instance.ps1`
  启动测试实例，默认监听 `127.0.0.1:8190`。
- `scripts/install_plugin_requirements.ps1`
  把清单里的插件依赖安装到项目自己的 `.venv`，不污染主实例运行时。
- `runtime/instance/`
  第二实例的实际 base directory。

## 推荐用法

首次初始化：

```powershell
pwsh -File .\agent-projects\comfyui-test-instance\scripts\setup_instance.ps1
```

如果你要给第二实例单独准备一个 overlay Python 环境：

```powershell
pwsh -File .\agent-projects\comfyui-test-instance\scripts\setup_instance.ps1 -CreateOverlayVenv
pwsh -File .\agent-projects\comfyui-test-instance\scripts\install_plugin_requirements.ps1 -ContinueOnError
```

启动第二实例：

```powershell
pwsh -File .\agent-projects\comfyui-test-instance\scripts\start_instance.ps1
```

启动后默认地址：

- 主实例：`http://127.0.0.1:8188`
- 第二实例：`http://127.0.0.1:8190`

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
