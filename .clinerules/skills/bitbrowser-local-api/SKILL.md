---
name: bitbrowser-local-api
description: >
  使用当前仓库内的桥接脚本调用 BitBrowser Local API。
  当需要检查健康状态、列窗口、打开窗口、关闭窗口时使用。
applyTo: "**"
---

# bitbrowser-local-api

这个 Skill 使用 agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py 调用 BitBrowser Local API。

## 常用命令

检查 API：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-health
```

列窗口：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-list --page 0 --page-size 20
```

打开窗口：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-open <窗口ID>
```

关闭窗口：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-close <窗口ID>
```

## 说明

- 默认 API 地址来自 agent-projects/openclaw-cline-tools/config/toolchain.json。
- 如果 API 端口变化，优先更新配置文件。