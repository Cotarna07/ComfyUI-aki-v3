# 贡献指南

感谢您对 WhatDreamsCost-ComfyUI 项目的关注！我们欢迎任何形式的贡献。

## 如何贡献

### 报告问题
1. 在 GitHub Issues 中搜索是否已有类似问题
2. 如果没有，创建新的 Issue
3. 提供详细的问题描述
4. 包含复现步骤
5. 提供环境信息

### 提交代码
1. Fork 项目仓库
2. 创建功能分支
3. 编写代码
4. 添加测试
5. 提交 Pull Request

### 改进文档
1. 修复错别字
2. 添加示例
3. 翻译文档
4. 改进说明

## 开发环境

### 依赖安装
```bash
# 克隆仓库
git clone https://github.com/WhatDreamsCost/WhatDreamsCost-ComfyUI.git

# 进入项目目录
cd WhatDreamsCost-ComfyUI

# 安装依赖（如需要）
pip install -r requirements.txt
```

### 开发工具
- **Python**：3.8 或更高版本
- **Node.js**：14 或更高版本
- **Git**：版本控制

## 代码规范

### Python 代码
- 遵循 PEP 8 规范
- 添加类型注释
- 编写文档字符串
- 保持函数简洁

### JavaScript 代码
- 使用 ES6+ 语法
- 遵循 Airbnb 风格指南
- 添加注释
- 保持模块化

### 提交规范
- 使用清晰的提交信息
- 每个提交只做一件事
- 保持提交历史清晰

## 测试

### 运行测试
```bash
# 运行所有测试
python -m pytest

# 运行特定测试
python -m pytest tests/test_specific.py

# 运行覆盖率测试
python -m pytest --cov=.
```

### 编写测试
- 为新功能编写测试
- 为修复的 Bug 编写测试
- 保持测试覆盖率
- 使用描述性测试名称

## 文档

### 编写文档
- 使用清晰的标题
- 提供示例代码
- 包含截图（如适用）
- 保持文档更新

### 文档结构
- README.md：项目介绍
- DEPLOYMENT.md：部署说明
- USAGE_GUIDE.md：使用指南
- CHANGELOG.md：更新日志

## 社区

### 参与讨论
- GitHub Discussions：项目讨论
- Issues：问题报告
- Pull Requests：代码贡献

### 行为准则
- 尊重他人
- 保持专业
- 建设性反馈
- 包容性环境

## 发布流程

### 版本号
- 主版本号：重大变更
- 次版本号：新功能
- 修订号：Bug 修复

### 发布步骤
1. 更新版本号
2. 更新 CHANGELOG.md
3. 创建 Git 标签
4. 发布 GitHub Release

## 许可证

### 代码许可
- GPL-3.0 许可证
- 遵守许可证要求

### 贡献许可
- 贡献者许可协议
- 代码所有权

## 联系方式

### 获取帮助
- GitHub Issues：问题报告
- GitHub Discussions：项目讨论
- 邮件联系：项目维护者

### 反馈渠道
- 问题反馈
- 功能建议
- 改进建议
- 使用反馈

## 致谢

感谢所有贡献者的支持！您的贡献使这个项目变得更好。