# General Rules

- 当任务涉及本地部署的抓取工具时，先读取 agent-projects/openclaw-cline-tools/README.md。
- 优先通过 agent-projects/openclaw-cline-tools/tools/openclaw_bridge.py 调用本地 Scrapling、opencli 和 BitBrowser，不要把 Z: 挂载盘路径硬编码到临时脚本里。
- 当前桥接配置集中放在 agent-projects/openclaw-cline-tools/config/toolchain.json；路径变化时先改配置，不要先改规则文档。
- 抓取结果、缓存和中间文件统一放到 agent-projects/openclaw-cline-tools/runtime/ 下。
- 如果需要新增 Cline 技能规则，优先放到 .clinerules/skills/；如果需要新增长期维护代码，优先放到 agent-projects/openclaw-cline-tools/。