# tools

这个目录用于存放长期维护的正式工具代码。

当前已部署：

- openclaw_bridge.py
	统一桥接外部 Scrapling、opencli 和 BitBrowser Local API。

建议按工具或上游项目单独建子目录，例如：

- tools/scrapling/
- tools/opencli/
- tools/bitbrowser/
- tools/db-tools/

如果某段脚本还处于一次性验证阶段，不要先放进这里，先放到 scripts/generated/。