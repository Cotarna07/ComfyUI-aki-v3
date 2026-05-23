# 漫画分镜参考资源项目

## 这是什么

这个目录用于集中留存本次“漫画切分、分镜排序、角色识别、带上下文故事内容生成”相关的第三方开源项目、ComfyUI 节点仓库、示例工作流来源和资源索引，供后续正式开发时统一参考。

这里不是直接跑业务逻辑的实现项目，而是一个“参考资源项目”。目的有两个：

1. 把检索过、确认有价值的外部仓库固定到当前工作区。
2. 统一交由工作区根目录 Git 仓库管理，避免每个第三方项目各自带一层 Git 元数据，后续版本来源混乱。

## 当前结构

- `scripts/`
  存放项目维护脚本，例如第三方参考仓库的一键刷新脚本。
- `resources/reference-projects/`
  存放已拉取的第三方参考仓库源码副本。
- `resources/reference-projects/manifest.json`
  记录每个第三方项目的来源 URL、分类、拉取时提交号、本地路径，以及 `.git` 是否已移除。
- `docs/`
  存放按功能阶段整理的资源索引文档。
- `runtime/`
  预留给后续扫描结果、比对结果或资源整理产物。

## Git 管理约定

本项目中的第三方仓库已经按以下方式处理：

1. 先从原始 GitHub 仓库拉取源码。
2. 记录来源 URL 和拉取时提交号。
3. 删除各自目录中的 `.git` 元数据。
4. 仅保留当前工作区根目录 Git 仓库作为唯一版本管理入口。

这意味着：

- 这些目录现在是“受根仓库管理的参考源码副本”。
- 如果后续要更新某个第三方项目，应重新从上游拉取并覆盖，同时更新 `manifest.json` 和索引文档。
- 不要在这些第三方目录内单独初始化新的 Git 仓库。

## 已纳入的资源类别

目前已经纳入以下资源：

1. 漫画分镜切割与版式相关仓库
2. 单图视觉理解与 VLM 相关 ComfyUI 节点仓库
3. 角色相似度分析与身份保持相关仓库
4. OCR 相关 ComfyUI 节点仓库
5. 漫画分镜分割研究类仓库

具体清单见 `docs/2026-05-08_资源索引.md`。

## 使用建议

1. 先看 `docs/2026-05-08_资源索引.md`，确定每个开发阶段优先参考哪一类仓库。
2. 需要核对某个仓库的来源和拉取版本时，查 `resources/reference-projects/manifest.json`。
3. 需要找示例 workflow、examples 或 sample layouts 时，优先从已归档的第三方目录中直接查看，不要重新全网检索。

## 一键刷新第三方仓库

已提供维护脚本：

- `scripts/refresh_reference_projects.ps1`

脚本行为：

1. 以 `resources/reference-projects/manifest.json` 为来源清单。
2. 重新从每个 `source_url` 拉取最新浅克隆。
3. 用新内容覆盖本地参考目录。
4. 删除各参考目录中的 `.git`，继续保持只由根仓库统一管理。
5. 更新 `manifest.json` 中的 `cloned_commit` 和 `refreshed_at`。

刷新全部参考仓库：

```powershell
& .\agent-projects\manga-pipeline-reference\scripts\refresh_reference_projects.ps1
```

只刷新指定仓库：

```powershell
& .\agent-projects\manga-pipeline-reference\scripts\refresh_reference_projects.ps1 -Name ComfyUI-QwenVL,ComfyUI-Florence2
```

保留临时克隆目录便于排查：

```powershell
& .\agent-projects\manga-pipeline-reference\scripts\refresh_reference_projects.ps1 -KeepTemp
```