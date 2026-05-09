# Manga Panel Fixer

修复 picaweb 下载条漫中因固定高度切块导致的分镜割裂。

**双引擎**：条漫自动用空白间距检测，页漫用 YOLOv12x 分镜检测（自动下载）。

## 一键运行

```powershell
# 批量处理全部漫画
python scripts/fix_panels.py -i D:\openclaw_tools\downloads\picaweb_manga -o D:\openclaw_tools\downloads\picaweb_manga_fixed --batch
```

**约定**：原图不动，输出到同级 `_fixed` 目录。条漫自动合图，页漫直接复制。

## 模型

YOLOv12x: [mosesb/best-comic-panel-detection](https://huggingface.co/mosesb/best-comic-panel-detection) (Apache-2.0, mAP50: 0.991)，首次运行自动下载 119MB → `models/best.pt`（已 gitignore）。
