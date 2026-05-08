# ComfyUI PaddleOCR 节点

> **注意：本项目暂不考虑上传 ComfyUI Manager**

一个专为 ComfyUI 设计的高性能 OCR（光学字符识别）节点，基于 PaddleOCR 技术实现。

## 功能特性

- **高精度识别**：基于 PP-OCRv5 模型，支持中文、英文、日文、韩文识别
- **完整流水线**：启用文档图像方向分类、文本图像矫正、文本行方向分类、文本检测、文本识别五个模块
- **三种输出格式**：
  - 纯文本内容
  - 带标注的图像（使用 PaddleOCR 3.2.0 内置可视化引擎）
  - 完整的 JSON 数据（包含坐标、置信度等信息）
- **简洁界面**：精简的用户选项，操作简单直观
- **GPU 支持**：可选择使用 GPU 加速推理

## 系统要求

- Python 3.8+
- ComfyUI
- CUDA（可选，用于 GPU 加速）

## 安装方法

1. 将项目文件复制到 ComfyUI 的 `custom_nodes` 目录：
   ```
   ComfyUI/custom_nodes/Comfyui-ocr/
   ```

2. 安装依赖包：
   ```bash
   pip install -r requirements.txt
   ```

3. 重启 ComfyUI

## 使用方法

1. 在 ComfyUI 节点列表中找到 **OCR** 分类
2. 添加 **PaddleOCR 文字识别** 节点
3. 连接图像输入
4. 配置参数：
   - **图像**：输入要识别的图像
   - **语言**：选择识别语言（中文/英文/日文/韩文）
   - **使用GPU**：是否启用 GPU 加速
   - **置信度阈值**：过滤低置信度结果（0.0-1.0）

## 使用示例

![使用示例](https://raw.githubusercontent.com/VexMare/Comfyui-ocr/refs/heads/main/e9c0020ba4b1913d2f2512c25e9325f5.png)

上图展示了一个完整的 OCR 工作流：
- 输入包含中文文字的图像
- OCR 节点识别文字内容并生成标注图像
- 通过 Preview Text Node 查看识别结果

## 输出说明

节点提供三个输出端口：

### 1. 识别文本 (STRING)
包含所有识别到的文字内容，按行分隔。

### 2. 标注图像 (IMAGE) 
在原图上绘制文字检测框和识别结果，使用透明背景显示。采用 PaddleOCR 官方可视化引擎，确保标注位置准确。

### 3. JSON 数据 (STRING)
完整的识别结果数据，包含：
- `results`：识别结果数组
  - `text`：识别的文字内容
  - `confidence`：置信度分数
  - `box`：文字区域坐标（四个顶点）
- `total_count`：识别到的文字块总数

## 技术特点

- **PP-OCRv5 引擎**：采用最新的 PaddleOCR v5 模型
- **内置可视化**：使用 PaddleOCR 3.2.0 官方可视化功能
- **自动优化**：内置最佳参数配置，无需手动调节
- **高兼容性**：与 ComfyUI 工作流完美集成

## 许可证

本项目遵循开源协议，仅供学习和研究使用。
