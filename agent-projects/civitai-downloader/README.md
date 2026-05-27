# Civitai 稳定下载工具链

这个项目现在面向本地 Windows 长期使用场景，目标是稳定下载 Civitai 模型并方便落到 ComfyUI 模型目录。

当前能力：

- 断点续传
- 失败自动重试
- 适配大文件下载
- 支持 Civitai API Token
- 支持代理环境
- 下载日志和任务汇总
- 下载完成后自动移动到 ComfyUI 对应模型目录
- 支持命令行批量下载

默认优先使用 aria2c 作为下载后端；如果本机暂时没有 aria2c，会自动回退到脚本内置的续传下载器。

## 目录约定

- 下载暂存目录：runtime/downloads/
- 下载日志目录：runtime/logs/
- 项目内置 aria2 安装目录：runtime/tools/aria2/
- 默认 ComfyUI 模型根目录：当前工作区下的 ComfyUI/models/

## 快速部署

### 1. 安装 aria2

在 PowerShell 中执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\install_aria2.ps1
```

如果希望把 aria2 写入当前用户 PATH，可以执行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\install_aria2.ps1 -AddToUserPath
```

### 2. 配置 Token

推荐直接设置环境变量：

```powershell
$env:CIVITAI_API_TOKEN = "你的 Token"
```

也支持以下配置来源，优先级从高到低：

1. --token
2. CIVITAI_API_TOKEN / CIVITAI_TOKEN
3. 项目内 config.local.json
4. ~/.civitai/downloader.json
5. ~/.civitai/config

可选的 JSON 配置示例：

```json
{
	"token": "你的 Token",
	"proxy": "http://127.0.0.1:7890",
	"output_dir": "D:/ComfyUI-aki-v3/agent-projects/civitai-downloader/runtime/downloads",
	"comfyui_root": "D:/ComfyUI-aki-v3/ComfyUI/models",
	"move_to_comfyui": true,
	"aria2c_path": "D:/ComfyUI-aki-v3/agent-projects/civitai-downloader/runtime/tools/aria2/aria2c.exe"
}
```

### 3. 单个模型下载

下面三种引用形式都支持：版本 ID、模型页面 URL、下载 URL。

```powershell
python .\download.py 46846
python .\download.py "https://civitai.com/models/1234567?modelVersionId=46846"
python .\download.py "https://civitai.com/api/download/models/46846"
```

如果你更习惯先运行脚本、再往终端里粘贴链接，可以直接使用交互入口：

```powershell
python .\scripts\generated\civitai\download_requested_models.py
```

启动后逐行粘贴模型链接或版本 ID，最后回车一次就会开始下载。默认会自动移动到 ComfyUI 模型目录，并优先使用带进度条的内置续传下载器。

兼容旧用法：

```powershell
python .\download.py 46846 D:\Downloads\Civitai
```

### 4. 下载后自动移动到 ComfyUI 模型目录

```powershell
python .\download.py 46846 --move-to-comfyui
```

脚本会根据 Civitai 模型类型自动映射到常见目录，例如：

- Checkpoint -> checkpoints
- LORA / LoCon / DoRA -> loras
- VAE -> vae
- ControlNet -> controlnet
- TextualInversion -> embeddings
- Upscaler -> upscale_models
- UNet -> diffusion_models

如果你想手动覆盖目录：

```powershell
python .\download.py 46846 --move-to-comfyui --target-subdir loras
```

### 5. 代理环境

显式指定代理：

```powershell
python .\download.py 46846 --proxy http://127.0.0.1:7890
```

也支持直接使用系统环境变量：

```powershell
$env:HTTP_PROXY = "http://127.0.0.1:7890"
$env:HTTPS_PROXY = "http://127.0.0.1:7890"
python .\download.py 46846
```

### 6. 批量下载

准备一个文本文件，例如 models.txt，每行一个版本 ID 或 URL：

```text
# checkpoint
46846

# lora
https://civitai.com/models/1234567?modelVersionId=987654
```

执行批量下载：

```powershell
python .\download.py --input-file .\models.txt --move-to-comfyui
```

也可以直接重复传入 --model-ref：

```powershell
python .\download.py --model-ref 46846 --model-ref 987654 --move-to-comfyui
```

## 日志与输出

每次运行都会生成两类日志：

- runtime/logs/<时间戳>.jsonl：逐条任务日志
- runtime/logs/<时间戳>.summary.json：本次运行汇总

如果使用 aria2，还会额外生成：

- runtime/logs/<时间戳>-<version_id>.aria2.log：aria2 原始日志

可以通过 --manifest-out 自定义汇总 JSON 的输出位置。

## 常用参数

```powershell
python .\download.py --help
```

重点参数：

- --retries：重试次数，默认 5
- --retry-wait：重试等待秒数，默认 10
- --timeout：网络超时秒数，默认 60
- --connections：aria2 单文件并发连接数，默认 8
- --split：aria2 分片数，默认 8
- --no-aria2：禁用 aria2，强制走内置下载器
- --dry-run：只解析元数据和目标路径，不下载
- --verbose：打印详细配置和 aria2 命令

## 适合你的长期使用方式

推荐你固定成下面这套流程：

1. 先运行 scripts/install_aria2.ps1，把 aria2 安装到项目内。
2. 在当前 PowerShell 会话里设置 CIVITAI_API_TOKEN。
3. 平时把待下载模型整理到文本清单里。
4. 用 --input-file 和 --move-to-comfyui 批量执行。
5. 遇到网络不稳时只要重新执行同一条命令，脚本会继续续传并保留日志。

