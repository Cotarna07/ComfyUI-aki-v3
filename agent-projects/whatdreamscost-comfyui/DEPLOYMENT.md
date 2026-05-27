# WhatDreamsCost-ComfyUI 本地部署说明

## 项目信息
- **原始仓库**: https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
- **本地路径**: `D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui`
- **版本**: v1.3.9
- **部署时间**: 2026-05-27
- **部署状态**: ✅ 完成

## 更新日志
- 2026-05-27: 初始部署，克隆仓库并创建 junction 链接

## 项目简介
WhatDreamsCost-ComfyUI 是一个 ComfyUI 自定义节点集合，主要用于视频生成和编辑，特别是 LTX 视频模型的工作流。包含以下主要节点：

1. **LTX Director** - 完整的 LTX 2.3 时间线编辑器
2. **Multi Image Loader** - 图片加载器，支持图库和批量处理
3. **LTX Sequencer** - LTX 视频序列器
4. **LTX Keyframer** - LTX 关键帧编辑器
5. **Speech Length Calculator** - 语音长度计算器
6. **Load Video UI** - 视频加载界面
7. **Load Audio UI** - 音频加载界面

## 安装要求
根据官方 README，此项目需要：
1. 更新 ComfyUI-LTXVideo 到最新版本
2. 更新 ComfyUI-KJNodes 到最新版本

## 本地部署步骤
1. ✅ 已克隆仓库到 `agent-projects/whatdreamscost-comfyui`
2. ✅ 已创建 junction 链接到 ComfyUI 的 custom_nodes 目录
3. 需要更新 ComfyUI-LTXVideo 和 ComfyUI-KJNodes 到最新版本

## 链接到 ComfyUI
已创建 junction 链接（不需要管理员权限）：

```powershell
# 已执行的 junction 链接命令
cmd /c mklink /J "D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\WhatDreamsCost-ComfyUI" "D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui"
```

验证链接：
```powershell
# 检查链接是否存在
Test-Path "D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\WhatDreamsCost-ComfyUI"
```

## 后续管理
- 所有改动记录在 `agent-projects/whatdreamscost-comfyui` 目录
- 可以通过 Git 管理本地修改
- 如需更新，可以拉取官方最新版本

## Git 管理
- 当前远程仓库：https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI.git
- 如需记录本地改动，可以创建新的 Git 分支
- 如需推送改动到自己的仓库，可以添加新的远程仓库

## 相关依赖
- ComfyUI-LTXVideo（需要最新版本）
- ComfyUI-KJNodes（需要最新版本）

## 依赖状态检查
- ✅ ComfyUI-LTXVideo 已安装（最新提交：cd5d371）
- ✅ ComfyUI-KJNodes 已安装（最新提交：38cccde）
- ✅ 项目已链接到 ComfyUI custom_nodes 目录

## 验证步骤
1. 运行安装测试脚本：
   ```powershell
   cd "D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui"
   python test_installation.py
   ```
2. 启动 ComfyUI 并检查节点是否出现在节点列表中
3. 在节点列表中查找以下节点：
   - LTX Director
   - Multi Image Loader
   - LTX Sequencer
   - LTX Keyframer
   - Speech Length Calculator
   - Load Video UI
   - Load Audio UI
4. 加载示例工作流测试节点功能

## 依赖安装
如需安装依赖，可以使用以下命令：

```powershell
# 安装音频处理依赖
pip install av

# 其他依赖应该已经安装在 ComfyUI 环境中
```

## 注意事项
1. 此项目使用 AI 辅助生成代码，可能存在冗余代码
2. 需要确保 ComfyUI 环境正确配置
3. 示例工作流可在 `example_workflows/` 目录找到
4. 如遇问题，检查 ComfyUI 控制台日志

## 许可证
本项目使用 GPL-3.0 许可证，详见 [LICENSE](LICENSE) 文件。

## 总结
WhatDreamsCost-ComfyUI 项目已成功部署到本地工作区。项目提供了强大的视频生成和编辑功能，特别是 LTX 视频模型的工作流支持。通过 junction 链接，项目已集成到 ComfyUI 中，可以正常使用。

后续如需更新项目，可以拉取官方最新版本，或者在本地进行修改并记录更改。

## 快速参考
- **项目路径**: `D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui`
- **ComfyUI 链接**: `D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\WhatDreamsCost-ComfyUI`
- **测试命令**: `python test_installation.py`
- **更新命令**: `git pull origin main`
- **查看状态**: `git status`
- **启动脚本**: `start_comfyui.bat`
- **本地说明**: `LOCAL_README.md`
- **更新日志**: `CHANGELOG.md`
- **使用指南**: `USAGE_GUIDE.md`
- **项目概览**: `PROJECT_OVERVIEW.md`
- **贡献指南**: `CONTRIBUTING.md`
- **项目状态**: `PROJECT_STATUS.md`
- **项目路线图**: `ROADMAP.md`

## 项目结构
```
whatdreamscost-comfyui/
├── __init__.py              # 节点注册
├── ltx_director.py          # LTX Director 节点
├── ltx_director_guide.py    # LTX Director Guide 节点
├── multi_image_loader.py    # Multi Image Loader 节点
├── ltx_sequencer.py         # LTX Sequencer 节点
├── ltx_keyframer.py         # LTX Keyframer 节点
├── speech_length_calculator.py # Speech Length Calculator 节点
├── load_audio_ui.py         # Load Audio UI 节点
├── load_video_ui.py         # Load Video UI 节点
├── patches.py               # 模型补丁
├── prompt_relay.py          # Prompt Relay 功能
├── js/                      # 前端 JavaScript 代码
├── example_workflows/       # 示例工作流
├── test_installation.py     # 安装测试脚本
├── start_comfyui.bat        # ComfyUI 启动脚本
├── requirements.txt         # 依赖说明
├── config.json              # 项目配置
├── DEPLOYMENT.md            # 本地部署说明
├── LOCAL_README.md          # 快速参考指南
└── README.md                # 官方说明文档
```