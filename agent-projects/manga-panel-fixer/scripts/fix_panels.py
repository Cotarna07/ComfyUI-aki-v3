"""
漫画分镜智能检测与合图工具（YOLO + 空白间距双引擎）

修复 picaweb 条漫下载时因固定高度切块导致的分镜割裂问题。

主引擎：YOLOv12x 漫画分镜检测模型（mosesb/best-comic-panel-detection, Apache-2.0）
  - 检测每张图中的分镜边界框
  - 如果分镜框跨越图片边界 → 分镜被切断 → 合并
副引擎：空白间距检测（无GPU回退方案）
  - 检测纵向空白间距作为分镜边界
  - 如果图片边界不对齐间距 → 需要合并

用法:
    # 单本漫画
    python scripts/fix_panels.py -i <images目录> -o <输出目录>

    # 批量模式（自动遍历漫画根目录下的所有子目录）
    python scripts/fix_panels.py -i <漫画根目录> -o <输出根目录> --batch

作者: agent-projects/manga-panel-fixer
模型: mosesb/best-comic-panel-detection (YOLOv12x, mAP50: 0.991)
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

try:
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "best.pt"
HF_REPO_ID = "mosesb/best-comic-panel-detection"

WEBTOON_WIDTH_THRESHOLD = 0.95
WEBTOON_MIN_HEIGHT = 200
GAP_BRIGHTNESS_THRESHOLD = 200
GAP_ROW_RATIO = 0.85
GAP_CONSECUTIVE_ROWS = 4
GAP_SEARCH_MARGIN = 0.15


def load_image(path: Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"无法读取图片: {path}")
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def save_image(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    success, encoded = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not success:
        raise RuntimeError(f"图片编码失败: {path}")
    encoded.tofile(str(path))


def is_blank_row(row: np.ndarray, threshold: int = GAP_BRIGHTNESS_THRESHOLD,
                 ratio: float = GAP_ROW_RATIO) -> bool:
    gray = np.mean(row, axis=1) if row.ndim == 2 else np.mean(row, axis=(1, 2))
    return (np.sum(gray > threshold) / len(gray)) >= ratio


def find_horizontal_gaps(img: np.ndarray, start_row: int = 0,
                         end_row: Optional[int] = None,
                         min_consecutive: int = GAP_CONSECUTIVE_ROWS) -> List[Tuple[int, int]]:
    if end_row is None:
        end_row = img.shape[0]
    gaps = []
    in_gap = False
    gap_start = 0
    for row_idx in range(start_row, end_row):
        blank = is_blank_row(img[row_idx])
        if blank and not in_gap:
            in_gap = True
            gap_start = row_idx
        elif not blank and in_gap:
            in_gap = False
            if row_idx - gap_start >= min_consecutive:
                gaps.append((gap_start, row_idx))
    if in_gap and (end_row - gap_start) >= min_consecutive:
        gaps.append((gap_start, end_row))
    return gaps


def has_gap_near_edge(gaps: List[Tuple[int, int]], edge_row: int,
                      margin_rows: int, is_bottom: bool = True) -> bool:
    ss = (edge_row - margin_rows) if is_bottom else edge_row
    se = edge_row if is_bottom else (edge_row + margin_rows)
    for gs, ge in gaps:
        if gs < se and ge > ss:
            return True
    return False


def vertical_stitch(img_top: np.ndarray, img_bottom: np.ndarray) -> np.ndarray:
    if img_top.shape[1] != img_bottom.shape[1]:
        raise ValueError(f"图片宽度不一致")
    return np.vstack([img_top, img_bottom])


def ensure_model(model_path: Optional[Path] = None) -> Path:
    path = model_path or DEFAULT_MODEL_PATH
    if path.exists():
        return path
    print(f"[model] 从 HuggingFace 下载: {HF_REPO_ID}")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError:
        raise RuntimeError("需要 huggingface_hub，请运行: pip install huggingface_hub")
    path.parent.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(HF_REPO_ID, "best.pt", local_dir=str(path.parent))
    return Path(downloaded)


class PanelDetector:
    """分镜检测器：根据漫画类型自动选择引擎。"""

    def __init__(self, model_path: Optional[Path] = None):
        self._yolo = None
        if HAS_YOLO:
            try:
                mp = ensure_model(model_path)
                self._yolo = YOLO(str(mp))
                print(f"[detector] YOLO 模型已加载（用于标准页漫）")
            except Exception as e:
                print(f"[detector] YOLO 加载失败: {e}")
        self._is_webtoon = False  # 由外部设置

    def set_mode(self, is_webtoon: bool):
        """设置漫画类型：True=条漫(用间距检测), False=页漫(用YOLO)。"""
        self._is_webtoon = is_webtoon
        if is_webtoon:
            print("[detector] 条漫模式：使用空白间距检测")
        elif self._yolo:
            print("[detector] 页漫模式：使用 YOLO 分镜检测")
        else:
            print("[detector] 页漫模式：回退到空白间距检测")

    @property
    def use_yolo(self) -> bool:
        return self._yolo is not None and not self._is_webtoon

    def detect_panels(self, img: np.ndarray) -> List[Tuple[int, int, int, int]]:
        if not self._yolo or self._is_webtoon:
            return []
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        results = self._yolo.predict(bgr, verbose=False, conf=0.3)
        panels = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                panels.append((x1, y1, x2, y2))
        return panels

    def has_panel_crossing_bottom(self, img: np.ndarray, margin_ratio: float = 0.1) -> bool:
        if self._yolo:
            panels = self.detect_panels(img)
            if panels:
                h = img.shape[0]
                margin = int(h * margin_ratio)
                for _, _, _, y2 in panels:
                    if y2 >= h - margin:
                        return True
                return False
        h = img.shape[0]
        gaps = find_horizontal_gaps(img)
        return not has_gap_near_edge(gaps, h, int(h * 0.15), is_bottom=True)

    def has_panel_crossing_top(self, img: np.ndarray, margin_ratio: float = 0.1) -> bool:
        if self._yolo:
            panels = self.detect_panels(img)
            if panels:
                h = img.shape[0]
                margin = int(h * margin_ratio)
                for _, y1, _, _ in panels:
                    if y1 <= margin:
                        return True
                return False
        h = img.shape[0]
        gaps = find_horizontal_gaps(img)
        return not has_gap_near_edge(gaps, 0, int(h * 0.15), is_bottom=False)


def detect_webtoon_splits(
    images: List[Tuple[Path, np.ndarray]],
    detector: Optional[PanelDetector] = None,
) -> List[List[int]]:
    if len(images) <= 1:
        return [[0]] if images else []

    stitch_groups = []
    current_group = [0]

    for i in range(len(images) - 1):
        _, img_curr = images[i]
        _, img_next = images[i + 1]
        h_curr, h_next = img_curr.shape[0], img_next.shape[0]

        same_width = abs(img_curr.shape[1] - img_next.shape[1]) / max(
            img_curr.shape[1], 1
        ) < (1.0 - WEBTOON_WIDTH_THRESHOLD)

        if detector:
            cut_bottom = detector.has_panel_crossing_bottom(img_curr)
            cut_top = detector.has_panel_crossing_top(img_next)
        else:
            gaps_curr = find_horizontal_gaps(img_curr)
            cut_bottom = not has_gap_near_edge(gaps_curr, h_curr, int(h_curr * 0.15), True)
            gaps_next = find_horizontal_gaps(img_next)
            cut_top = not has_gap_near_edge(gaps_next, 0, int(h_next * 0.15), False)

        is_stub = h_next < WEBTOON_MIN_HEIGHT or h_curr < WEBTOON_MIN_HEIGHT
        should_merge = same_width and (cut_bottom or cut_top or is_stub)

        if should_merge:
            current_group.append(i + 1)
        else:
            stitch_groups.append(current_group)
            current_group = [i + 1]

    stitch_groups.append(current_group)
    return stitch_groups


def process_manga_directory(
    input_dir: Path, output_dir: Path,
    csv_path: Optional[Path] = None,
    model_path: Optional[Path] = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)

    if csv_path and csv_path.exists():
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            ordered_files = []
            for row in reader:
                local = row.get("local_file", "")
                img_path = input_dir.parent / local
                if img_path.exists():
                    ordered_files.append(img_path)
    else:
        ordered_files = sorted(input_dir.glob("*.jpg"), key=lambda p: p.name)

    if not ordered_files:
        return {"error": "未找到任何图片"}

    detector = PanelDetector(model_path)

    images = []
    for fp in ordered_files:
        try:
            images.append((fp, load_image(fp)))
        except Exception as e:
            print(f"  跳过 {fp.name}: {e}")

    if len(images) <= 1:
        for fp, img in images:
            save_image(output_dir / fp.name, img)
        return {
            "detector": "copy",
            "total_original": len(images), "total_fixed": len(images),
            "merged_count": 0, "stitch_groups": [],
        }

    # 判断漫画类型：所有图片等宽 → 条漫（用间距检测）
    widths = {img.shape[1] for _, img in images}
    is_webtoon = len(widths) == 1
    detector.set_mode(is_webtoon)

    stitch_groups = detect_webtoon_splits(images, detector=detector)

    # 页漫不做纵向合图（每个页面是独立单元）
    if not is_webtoon:
        stitch_groups = [[i] for i in range(len(images))]

    report_groups = []
    fixed_idx = 0
    for group in stitch_groups:
        if len(group) == 1:
            fp, img = images[group[0]]
            out_name = f"fixed_{fixed_idx:04d}_{fp.name}"
            save_image(output_dir / out_name, img)
            report_groups.append({
                "group_id": fixed_idx, "source_files": [fp.name],
                "output_file": out_name, "merged": False,
            })
        else:
            merged = images[group[0]][1]
            source_names = [images[g][0].name for g in group]
            for g_idx in group[1:]:
                _, img = images[g_idx]
                merged = vertical_stitch(merged, img)
            out_name = f"fixed_{fixed_idx:04d}_{images[group[0]][0].name}"
            save_image(output_dir / out_name, merged)
            report_groups.append({
                "group_id": fixed_idx, "source_files": source_names,
                "output_file": out_name, "merged": True,
                "merged_height": merged.shape[0],
            })
        fixed_idx += 1

    return {
        "detector": "yolo" if detector.use_yolo else ("gap_webtoon" if detector._is_webtoon else "gap"),
        "total_original": len(images),
        "total_fixed": len(stitch_groups),
        "merged_count": sum(1 for g in stitch_groups if len(g) > 1),
        "stitch_groups": report_groups,
    }


def process_batch(manga_root: Path, output_root: Path,
                  model_path: Optional[Path] = None):
    manga_dirs = [d for d in manga_root.iterdir() if d.is_dir()
                  and (d / "images").exists()]
    for md in manga_dirs:
        img_dir = md / "images"
        out_dir = output_root / f"{md.name}_fixed"
        csv_path = md / "data" / "pages_index.csv"
        comic_name = md.name.split("__")[0][:30]
        print(f"\n{'='*50}\n处理: {comic_name}")
        report = process_manga_directory(
            img_dir, out_dir,
            csv_path=csv_path if csv_path.exists() else None,
            model_path=model_path,
        )
        if "error" not in report:
            print(f"  引擎: {report['detector']} | {report['total_original']}→{report['total_fixed']} | 合并{report['merged_count']}组")
            report_path = out_dir / "fix_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n全部完成，共处理 {len(manga_dirs)} 部漫画")


def main():
    parser = argparse.ArgumentParser(description="漫画分镜智能检测与合图工具")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--csv")
    parser.add_argument("--report", "-r")
    parser.add_argument("--model", "-m")
    parser.add_argument("--batch", action="store_true", help="批量遍历子目录")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    model_path = Path(args.model) if args.model else None

    if args.batch:
        process_batch(input_path, output_path, model_path)
    else:
        csv_path = Path(args.csv) if args.csv else None
        report = process_manga_directory(input_path, output_path, csv_path, model_path)
        if "error" in report:
            print(f"错误: {report['error']}")
            sys.exit(1)
        print(f"\n引擎: {report['detector']} | {report['total_original']}→{report['total_fixed']} | 合并{report['merged_count']}组")
        if args.report:
            rp = Path(args.report)
            rp.parent.mkdir(parents=True, exist_ok=True)
            with open(rp, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
