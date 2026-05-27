# comfyui-shared

跨项目共享的 ComfyUI 基础能力包。纯 Python 标准库实现，无第三方依赖。

## 包含能力

### `comfyui_shared.client.ComfyClient`

合并了仓库内三套独立 ComfyUI 客户端实现的最佳特性：

| 来源项目 | 贡献能力 |
|---|---|
| `manga-anime-pipeline/pipeline/comfy/client.py` | 基础 HTTP 请求层（stdlib urllib） |
| `lmstudio-comfyui-benchmark/comfyui.py` | `wait_for_result()` 轮询 |
| `comfyui-test-harness/preflight.py` | `check_server()` GPU/VRAM 信息、`get_node_inventory()` |

```python
from comfyui_shared import ComfyClient, ComfyClientConfig

client = ComfyClient(ComfyClientConfig(server="http://127.0.0.1:8188"))
stats = client.check_server()          # ServerStats
nodes = client.get_node_inventory()    # NodeInventory
pid   = client.submit_prompt(payload)  # str
result = client.wait_for_result(pid)   # PromptResult
```

### `comfyui_shared.json_utils.parse_json_object`

从 LLM/VLM 模型文本输出中提取 JSON 对象，合并自 `product-vlm-review` 和 `lmstudio-comfyui-benchmark` 的两套私有实现：

```python
from comfyui_shared import parse_json_object

obj, err = parse_json_object(llm_response_text)
```

## 安装（项目内使用）

在需要使用此包的项目 `.venv` 中执行：

```powershell
.venv\Scripts\pip install -e ..\comfyui-shared
```

## 适用范围

新建需要调用 ComfyUI 的项目时，优先从这里 import，不要另起一套。

现有项目（`manga-anime-pipeline`、`lmstudio-comfyui-benchmark`）保留自己的内部客户端；
`comfyui-test-harness` 已于 2026-05-27 迁移至本包。
