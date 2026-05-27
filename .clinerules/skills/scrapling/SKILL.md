---
name: scrapling
description: >
  使用当前仓库内的桥接脚本调用本地部署的 Scrapling。
  当需要 HTTP 抓取、JS 渲染页面抓取、结构化内容提取时使用。
applyTo: "**"
---

# scrapling

当前工作区已经把 Scrapling 源码复制到本地，并安装到当前工作区自己的 .venv 中。

## 入口

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py scrapling -- <Scrapling 参数>
```

## 示例

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py scrapling extract get https://example.com agent-projects/openclaw-cline-tools/runtime/example.md
```

## 何时使用

- 网页内容抓取
- CSS 选择器提取
- JS 渲染页面抓取
- 需要调用 Scrapling 自带 CLI 时

如果路径失效，先运行 check 子命令，再修改 agent-projects/openclaw-cline-tools/config/toolchain.json。