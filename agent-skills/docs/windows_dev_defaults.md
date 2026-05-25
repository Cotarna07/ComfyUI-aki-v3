# Windows 开发默认值与文本安全

- 命令示例默认使用 PowerShell。
- 优先使用仓库或项目现有的 .venv。
- 如果项目已经使用 requirements.txt 或 pyproject.toml，优先沿用现有依赖管理方式，不强行迁移到 uv 或其他新工具。
- 不要假设 src/ 目录布局；先按真实项目结构组织代码、测试和校验范围。
- lint、type check、测试优先针对真实源码路径和本次改动范围执行。
- 不要用 PowerShell 默认编码管道直接改写包含中文的 .py、.md、.json、.yaml 等文本文件。
- 如需脚本化读写文本，必须显式使用 UTF-8。
- 修改 Python 文件后，优先运行最相关的校验，例如 python -m py_compile、pytest 或目标脚本自检。
- 临时日志、缓存和中间结果优先放在 agent 自有区的 runtime/、logs/ 或 generated 目录，不要继续堆在根目录。
