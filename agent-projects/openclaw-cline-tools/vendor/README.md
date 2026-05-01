# vendor

这个目录用于存放已经复制到当前仓库内的第三方工具运行时。

当前包含：

- opencli/
  本地复制的 opencli dist、node_modules、扩展目录和基础说明文件。
- Scrapling/
  本地复制的 Scrapling 源码与基础元数据文件。

如果后续需要更新这些本地副本，优先做增量同步，不要再把桥接脚本改回依赖外部挂载盘。