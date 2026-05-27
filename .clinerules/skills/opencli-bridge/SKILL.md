---
name: opencli-bridge
description: >
  使用当前仓库内的桥接脚本调用本地部署的 opencli。
  当需要 opencli 的平台适配器、Chrome 登录态复用或 list 命令时使用。
applyTo: "**"
---

# opencli-bridge

当前工作区通过 bridge 脚本把命令转发到本地 vendor/opencli/dist/main.js。

## 入口

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py opencli -- <opencli 参数>
```

## 示例

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py opencli list
```

## 说明

- opencli 当前使用本地 agent-projects/openclaw-cline-tools/vendor/opencli/dist/main.js。
- Node 命令默认读取 config/toolchain.json 里的 node_command。
- 如果目标命令依赖 Chrome 扩展或登录态，仍需保证外部 opencli 的运行前提已经满足。