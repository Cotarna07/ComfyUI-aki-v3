# WhatDreamsCost-ComfyUI 使用指南

## 快速开始

### 1. 启动 ComfyUI
```powershell
cd "D:\ComfyUI-aki-v3\ComfyUI"
python main.py
```

### 2. 查找节点
在 ComfyUI 节点列表中查找 "WhatDreamsCost" 分类，包含以下节点：

- **LTX Director** - 完整的 LTX 2.3 时间线编辑器
- **Multi Image Loader** - 图片加载器
- **LTX Sequencer** - LTX 视频序列器
- **LTX Keyframer** - LTX 关键帧编辑器
- **Speech Length Calculator** - 语音长度计算器
- **Load Video UI** - 视频加载界面
- **Load Audio UI** - 音频加载界面

### 3. 加载示例工作流
示例工作流位于 `example_workflows/` 目录，可以直接拖拽到 ComfyUI 中使用。

## 主要功能

### LTX Director
完整的 LTX 2.3 时间线编辑器，支持：
- 时间线编辑
- 关键帧设置
- 音频同步
- 多种视频模式

### Multi Image Loader
图片加载器，支持：
- 图库浏览
- 批量加载
- 图片调整
- 格式转换

### LTX Sequencer
LTX 视频序列器，支持：
- 序列创建
- 帧率设置
- 过渡效果
- 批量处理

### Speech Length Calculator
语音长度计算器，支持：
- 实时计算
- 多种语速
- 时间预测
- 帧数计算

## 常见任务

### 创建第一个视频
1. 添加 LTX Director 节点
2. 配置视频参数
3. 添加关键帧
4. 设置时间线
5. 运行生成

### 图片到视频
1. 添加 Multi Image Loader 节点
2. 加载图片序列
3. 添加 LTX Sequencer 节点
4. 配置序列参数
5. 运行生成

### 音频同步视频
1. 添加 Load Audio UI 节点
2. 加载音频文件
3. 添加 LTX Director 节点
4. 配置音频同步
5. 运行生成

## 技巧和提示

### 性能优化
- 使用合适的分辨率
- 控制关键帧数量
- 优化音频长度
- 使用预览模式

### 质量提升
- 使用高质量图片
- 合理设置关键帧
- 调整过渡效果
- 优化音频质量

### 工作流程
- 保存常用配置
- 创建模板工作流
- 使用批处理功能
- 定期备份项目

## 故障排除

### 节点不显示
- 检查 junction 链接
- 验证依赖安装
- 查看控制台日志

### 功能异常
- 检查节点配置
- 验证输入数据
- 查看错误信息

### 性能问题
- 降低分辨率
- 减少关键帧
- 优化音频
- 使用预览模式

## 获取帮助

### 官方资源
- GitHub 仓库：https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI
- 示例工作流：`example_workflows/` 目录
- 官方文档：README.md

### 本地资源
- 部署说明：DEPLOYMENT.md
- 快速参考：LOCAL_README.md
- 更新日志：CHANGELOG.md

### 社区支持
- GitHub Issues：报告问题和建议
- ComfyUI 社区：交流经验
- 示例工作流：学习最佳实践