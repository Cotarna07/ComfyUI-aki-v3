---
name: openclaw-toolkit
description: >
  当前工作区对本地部署 openclaw-cline-tools 工具集的统一桥接入口。
  通过本仓库内的 openclaw_bridge.py 转发本地 Scrapling、opencli 和 BitBrowser Local API。
  当任务涉及网页抓取、浏览器会话复用、BitBrowser 窗口管理时使用。
applyTo: "**"
---

# openclaw-toolkit

这个 Skill 是当前工作区里给 Cline 使用的统一本地工具入口。

## 入口脚本

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py check
```

## 覆盖能力

- Scrapling CLI 与 Scrapling Python 环境
- opencli CLI
- BitBrowser Local API

## 常用命令

### 检查桥接状态

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py check
```

### Scrapling 抓取页面

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py scrapling extract get https://example.com agent-projects/openclaw-cline-tools/runtime/example.md
```

### opencli 列出支持平台

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py opencli list
```

### BitBrowser 查看窗口列表

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-list --page 0 --page-size 20
```

## 使用原则

- 需要轻量 HTTP 抓取时，优先 Scrapling。
- 需要平台适配器或复用 Chrome 登录态时，优先 opencli。
- 需要指纹浏览器窗口管理时，优先 BitBrowser Local API。
- 运行产物默认写入 agent-projects/openclaw-cline-tools/runtime/。