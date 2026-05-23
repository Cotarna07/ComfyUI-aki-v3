# LM Studio + ComfyUI 全自动测评工具

这个项目用于一键批量测评 LM Studio 中部署的多款大模型在 ComfyUI 提示词生成场景下的表现，并把模型输出自动注入 ComfyUI API 工作流批量出图。

## 目标

- 使用同一条固定指令测试所有模型，保证变量可控。
- 自动遍历模型与参数组合，记录生成耗时、Token 速度、输出内容与质量评分。
- 按顺序把正面 / 负面提示词注入 ComfyUI，使用统一基础参数批量出图。
- 支持无人值守、失败重试、checkpoint 续跑，适合过夜运行。

## 快速开始

1. 确认 LM Studio 已启动 OpenAI Compatible Server，例如 `http://localhost:1234/v1`。
2. 确认 ComfyUI 已启动 API 服务，例如 `http://127.0.0.1:8188`。
3. 准备一个 ComfyUI API 工作流 JSON，并在配置中填写正面 / 负面提示词要替换的节点输入路径。
4. 复制示例配置：

```powershell
Copy-Item .\config\benchmark.example.toml .\config\benchmark.toml
```

5. 按实际模型名、工作流路径和节点字段修改 `config/benchmark.toml`。
6. 启动测评：

```powershell
python -m lmstudio_comfyui_benchmark --config .\config\benchmark.toml
```

运行结果会写入 `runtime/<run_id>/`，包括：

- `checkpoint.json`：续跑状态
- `llm_results.jsonl`：所有模型输出
- `image_jobs.jsonl`：ComfyUI 出图任务
- `summary.csv`：速度与质量汇总
- `run.log`：运行日志

## 续跑

同一个 `run_id` 再次运行会跳过已经完成的模型参数组合与出图任务：

```powershell
python -m lmstudio_comfyui_benchmark --config .\config\benchmark.toml --run-id overnight-001
```

## 设计说明

更完整的流程、配置字段、评分规则和风险控制见 [docs/architecture.md](docs/architecture.md)。
