# openclaw-cline-tools

这个项目用于在当前工作区内部署一层给 Cline 使用的本地工具层。

当前实现已经把关键运行时复制进当前仓库，不再依赖 Z:\openclaw_tools 挂载盘在线。

当前本地化的能力包括：

- Scrapling
- opencli
- BitBrowser Local API

## 当前部署结果

- 已创建独立项目目录 agent-projects/openclaw-cline-tools/。
- 已创建根目录 .clinerules/ 作为 Cline 可见入口。
- 已把 opencli 运行时复制到 vendor/opencli/。
- 已把 Scrapling 源码复制到 vendor/Scrapling/。
- 已把 Scrapling 安装到当前工作区自己的 .venv。
- 已提供 tools/openclaw_bridge.py 统一桥接本地工具。
- 已提供 config/toolchain.json 管理本地工具路径。

## 目录说明

- config/
  本地工具路径和 API 地址配置。
- tools/
  正式桥接脚本与后续长期维护的工具代码。
- vendor/
  本地复制的第三方工具运行时。
- scripts/generated/
  临时迁移脚本、探测脚本、转换脚本。
- runtime/
  抓取结果、日志、中间产物、缓存。

## 关键文件

- config/toolchain.json
  本地工具目录、解释器、CLI 入口和 BitBrowser API 地址。
- tools/openclaw_bridge.py
  统一入口，支持路径检查、Scrapling 转发、opencli 转发、BitBrowser API 调用。
- vendor/opencli/
  本地复制的 opencli 运行时。
- vendor/Scrapling/
  本地复制的 Scrapling 源码。
- ../../.clinerules/general.md
  当前工作区给 Cline 的总说明入口。

## 快速开始

先检查桥接路径：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py check
```

运行 Scrapling CLI：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py scrapling extract get https://example.com agent-projects/openclaw-cline-tools/runtime/example.md
```

运行 opencli：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py opencli list
```

检查 BitBrowser Local API：

```powershell
d:\ComfyUI-aki-v3\.venv\Scripts\python.exe agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py bitbrowser-health
```

## Cline 接入方式

当前仓库采用两层结构：

1. 实际工具桥接项目放在 agent-projects/openclaw-cline-tools/。
2. 给 Cline 的薄入口放在根目录 .clinerules/。

这样做的目的是让 Cline 能在工作区根目录直接看到规则，同时把真正的工具代码保持在 agent-projects 下，避免和技能层、启动器原区混在一起。

## 配置说明

默认配置现在指向以下本地路径：

- D:\ComfyUI-aki-v3\agent-projects\openclaw-cline-tools\vendor\Scrapling
- D:\ComfyUI-aki-v3\.venv\Scripts\scrapling.exe
- D:\ComfyUI-aki-v3\.venv\Scripts\python.exe
- D:\ComfyUI-aki-v3\agent-projects\openclaw-cline-tools\vendor\opencli\dist\main.js
- http://127.0.0.1:54345

如果本地路径变化，优先修改 config/toolchain.json，而不是直接改桥接脚本。

## 当前机器上的已知状态

- opencli 本地副本已实测可调用。
- BitBrowser API 桥接已接通检查逻辑，但当前 127.0.0.1:54345 没有服务在监听。
- Scrapling 已安装进当前工作区自己的 .venv，本地导入和 CLI 已实测可用。

如果后面要更新本地 Scrapling，可选两种方式：

1. 重新从外部源同步 vendor/Scrapling/ 后再执行本地安装。
2. 直接把 config/toolchain.json 指向别的本地 Python 环境。

## 后续扩展建议

1. 继续把数据库工具桥接进同一个入口脚本。
2. 按需要从外部 .clinerules/skills 中继续挑选并精简迁入当前仓库。
3. 为 vendor/ 增加同步脚本，方便后续从外部源更新本地副本。