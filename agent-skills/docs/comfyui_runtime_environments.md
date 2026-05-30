# ComfyUI 多运行环境规则

## 核心思路

本工作区不把所有节点都塞进主 ComfyUI。主环境负责稳定生产和已验证工作流；不同模型系列、不同依赖栈和局域网 API 调用放到命名测试环境里。这样一个实验节点启动失败时，不会拖垮日常可用的 `8188` 主服务。

所有命名环境都由 `agent-projects/comfyui-test-instance` 管理。模型目录共享，运行根目录、端口、`user` 数据库、输入输出目录和 `custom_nodes` 集合隔离。

## 当前环境

| 环境名 | 端口 | 用途 | 状态 |
|---|---:|---|---|
| `aki-main-py313-cu130` | 8188 | 当前秋叶主环境，稳定日常使用 | 已存在 |
| `wan-video-py313-cu130` | 8189 | Wan/LTX/视频节点测试 | 已创建 |
| `flux-kontext-py313-cu130` | 8190 | FLUX、Kontext、商品图编辑、抠图、放大 | 已创建 |
| `legacy-pmrf-py311-cu124` | 8191 | PMRF、NATTEN、RealESRGAN、BasicSR 老依赖 | 只建目录，需外部 Python |
| `api-bridge-py313` | 8192 | 调用局域网 TTS/LLM/翻译/字幕 API | 已创建 |

机器可读清单在：

```powershell
agent-projects/comfyui-test-instance/config/environments.json
```

## 使用原则

- 主环境 `aki-main-py313-cu130` 不作为新节点试验场。
- Wan、LTX、插帧、视频后处理优先走 `wan-video-py313-cu130`。
- FLUX Fill/Redux/Kontext、商品背景融合、LayerStyle、RMBG 相关工作流优先走 `flux-kontext-py313-cu130`。
- 局域网已有 IndexTTS、LLM、翻译、字幕服务时，本机走 `api-bridge-py313` 调 API，不重复部署 `IndexTTSRun` 或 `llama_cpp_*` 重依赖。
- PMRF/NATTEN/BasicSR 这类强绑定 Python/Torch/CUDA 的旧依赖，不要用主 Python 3.13/CUDA 13 硬装；等准备好 Python 3.11/CUDA 12.4 兼容运行时后，再补 `legacy-pmrf-py311-cu124` 的 `external_python`。

## 常用命令

列出环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\list_environments.ps1
```

创建所有可管理环境目录、共享模型链接和插件链接：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\setup_all_environments.ps1
```

同时创建每个可用环境的 overlay `.venv`：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\setup_all_environments.ps1 -CreateVenvs
```

启动指定环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start_environment.ps1 -Name wan-video-py313-cu130
```

也可以使用便捷入口：

```powershell
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-wan-video.ps1
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-flux-kontext.ps1
powershell -ExecutionPolicy Bypass -File .\agent-projects\comfyui-test-instance\scripts\start-api-bridge.ps1
```

## 给后续 agent 的判断顺序

1. 先查 `environments.json`，不要临时创造环境名或端口。
2. 再看工作流缺的是模型、后端节点、前端画布节点，还是外部 API 服务。
3. 能通过 API 调局域网服务解决的，不在本机重复安装重依赖。
4. 需要新 custom node 时，先加到对应测试环境插件集合；确认稳定后再考虑是否晋升到主环境。
5. 涉及主环境、秋叶启动器原文件或大规模依赖安装前，先向用户说明风险。
