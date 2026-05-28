# 工作流总目录

这个目录是当前工作区的唯一工作流总入口。

## 管理规则：命名约定即权限边界

目录名的**首字符**决定管理权归属。规则简单且自动适用——不需要为新目录更新文档。

| 前缀 | 归属 | 代理能做什么 |
|------|------|-------------|
| `01-shared/` | 代理管理区 | 自由读写、整理、晋升 |
| `02-project/` | 代理管理区 | 自由读写、按项目组织 |
| `03-source/` | 代理管理区 | 自由读写、导入分类归档 |
| **其他一切** | **用户区** | **只能读，禁止改** |

> 你新建 `my-experiments/`、`tmp/`、`scratch/` 或任何不以 `0` 开头的目录/文件——代理自动只读，不需要来这里登记。

### 三层管理区说明

- `01-shared/` — 跨项目复用、已验证、可直接自动化调用的正式模板。从 `03-source/` 晋升而来。
- `02-project/<project>/` — 只服务某个项目的稳定模板与 mapping。子目录按项目名。
- `03-source/` — 外部导入、供应商示例、UI 草稿、待整理生成稿、历史归档。
  - `vendor/<source>/`：第三方供应商工作流
  - `imported/<topic>/`：社区导入，按主题分目录
  - `drafts/`：草稿

### 放置规则

- 新导出的共享 API 工作流 → `01-shared/`
- 项目独占模板 → `02-project/<project>/`
- 外部下载、界面另存、脚本初稿 → `03-source/`，整理后再晋升
- `runtime/`（在 `agent-skills/comfyui/runtime/`）只放运行产物，不放模板

---

## 工作区其他工作流位置（交叉引用）

以下位置存放工作流但**不在本总目录管理范围内**：

| 位置 | 说明 |
|------|------|
| `ComfyUI/blueprints/` | ComfyUI 内置蓝图（50+），UI 面板直接读取 |
| `agent-projects/ComfyUI_examples-master/` | 官方示例，PNG 内嵌工作流元数据 |
| `agent-projects/manga-anime-pipeline/pipeline/` | Python 程序化工作流生成，非静态模板 |
| `agent-skills/comfyui/runtime/` | API 历史运行记录，运行产物 |