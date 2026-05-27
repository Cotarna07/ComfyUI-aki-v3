# WhatDreamsCost-ComfyUI 本地部署

## 快速开始
1. 运行安装测试：
   ```powershell
   cd "D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui"
   python test_installation.py
   ```

2. 启动 ComfyUI：
   ```powershell
   cd "D:\ComfyUI-aki-v3\ComfyUI"
   python main.py
   ```

3. 在 ComfyUI 中查找 WhatDreamsCost 节点

## 项目特性
- LTX Director：完整的 LTX 2.3 时间线编辑器
- Multi Image Loader：图片加载器，支持图库和批量处理
- LTX Sequencer：LTX 视频序列器
- LTX Keyframer：LTX 关键帧编辑器
- Speech Length Calculator：语音长度计算器
- Load Video UI：视频加载界面
- Load Audio UI：音频加载界面

## 文件说明
- `DEPLOYMENT.md`：详细部署说明
- `test_installation.py`：安装测试脚本
- `start_comfyui.bat`：ComfyUI 启动脚本
- `requirements.txt`：依赖说明

## 常见问题
1. **节点不显示**：检查 junction 链接是否正确
2. **导入错误**：确保 ComfyUI 环境正确配置
3. **功能异常**：查看 ComfyUI 控制台日志

## 更新方法
```powershell
cd "D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui"
git pull origin main
```

## 联系方式
- 原始仓库：https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
- 本地路径：`D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui`