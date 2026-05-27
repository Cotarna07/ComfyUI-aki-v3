# ComfyUI 测试框架

对 ComfyUI 工作流和模型进行自动化校验和测试。

## 功能

- **预检**：服务器连接、节点清单、模型目录全景
- **工作流校验**：节点类型、模型引用、参数范围、链接完整性
- **模型检查**：新增模型文件存在性
- **默认重点模式**：只测试 2026-05-16 新增的 MMAudio 工作流和近期 API 工作流
- **离线模式**：ComfyUI 未启动时仍可执行静态校验

## 使用

```powershell
# 重点资源测试（默认，推荐）
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe agent-projects/comfyui-test-harness/scripts/run_tests.py

# 全库巡检（会包含大量历史工作流，输出不代表本次重点资源质量）
d:/ComfyUI-aki-v3/.venv/Scripts/python.exe agent-projects/comfyui-test-harness/scripts/run_tests.py --all
```

## 输出

- 控制台：实时测试进度和结果
- Markdown 报告：`runtime/reports/test-report-YYYYMMDD-HHMMSS.md`
