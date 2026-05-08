# -*- coding: utf-8 -*-
"""
将 Markdown 深度解析文档转换为 PDF
使用 fpdf2 原生 API 逐段渲染（避免 HTML 解析兼容性问题）
字体：Windows 系统 SimHei（黑体）
"""
import sys
import os
import re
import textwrap
from pathlib import Path

from fpdf import FPDF

# 路径配置
DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"
MD_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.md"
PDF_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.pdf"

FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


class ChinesePDF(FPDF):
    """支持中文的 PDF 类，逐段渲染 Markdown 内容"""

    def __init__(self):
        super().__init__("P", "mm", "A4")
        self._setup_fonts()
        self.section_number = 0

    def _setup_fonts(self):
        simhei = FONT_DIR / "simhei.ttf"
        if not simhei.exists():
            raise RuntimeError("SimHei font not found")

        for style in ["", "B", "I", "BI"]:
            self.add_font("CJK", style, str(simhei))
        self.font_name = "CJK"

        # 等宽字体
        mono_file = None
        for name in ["CascadiaCode.ttf", "consola.ttf", "cour.ttf"]:
            p = FONT_DIR / name
            if p.exists():
                mono_file = p
                break
        if mono_file:
            self.add_font("Mono", "", str(mono_file))
            self.mono_font = "Mono"
        else:
            self.mono_font = self.font_name  # 使用中文字体作为等宽回退

        print(f"  Fonts: CJK=SimHei, Mono={self.mono_font}")

    # ─── 页眉页脚 ───
    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font(self.font_name, "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 4, "ComfyUI Wan2.2 — 专有名词功能逻辑深度解析", align="C")
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"— {self.page_no()} —", align="C")

    # ─── 排版辅助 ───
    def _content_width(self):
        return self.w - self.l_margin - self.r_margin

    def _write_body(self, text, size=9.5, bold=False, italic=False):
        style = ""
        if bold and italic:
            style = "BI"
        elif bold:
            style = "B"
        elif italic:
            style = "I"
        self.set_font(self.font_name, style, size)
        self.set_text_color(34, 34, 34)
        self.multi_cell(self._content_width(), size * 0.58, text, align="L")

    def _write_mono(self, text, size=7.5):
        self.set_font(self.mono_font, "", size)
        self.set_text_color(50, 50, 50)
        self.multi_cell(self._content_width(), size * 0.52, text, align="L")

    def _write_title(self, text, size=14, color=(22, 33, 62)):
        self.set_font(self.font_name, "B", size)
        r, g, b = color
        self.set_text_color(r, g, b)
        self.multi_cell(self._content_width(), size * 0.62, text, align="L")

    def _add_separator(self):
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(self.l_margin, y, self.w - self.r_margin, y)
        self.ln(4)

    def _ensure_space(self, mm_needed=30):
        """确保有足够空间，不足则换页"""
        if self.get_y() > self.h - self.b_margin - mm_needed:
            self.add_page()

    # ─── 块级元素渲染 ───
    def render_h1(self, text):
        self._ensure_space(25)
        self.ln(3)
        self.set_draw_color(233, 69, 96)
        self.set_line_width(1.5)
        y = self.get_y()
        self.line(self.l_margin, y + 9, self.w - self.r_margin, y + 9)
        self._write_title(text, size=16, color=(26, 26, 46))
        self.ln(2)

    def render_h2(self, text):
        self._ensure_space(20)
        self.ln(2)
        self.set_draw_color(15, 52, 96)
        self.set_line_width(0.8)
        y = self.get_y()
        self.line(self.l_margin, y + 7.5, self.l_margin + 60, y + 7.5)
        self._write_title(text, size=13, color=(22, 33, 62))
        self.ln(1)

    def render_h3(self, text):
        self._ensure_space(15)
        self.ln(1)
        self._write_title(text, size=11.5, color=(51, 51, 51))
        self.ln(1)

    def render_h4(self, text):
        self._ensure_space(12)
        self._write_body(text, size=10.5, bold=True)
        self.ln(1)

    def render_p(self, text):
        if not text.strip():
            self.ln(3)
            return
        # 处理行内格式
        parts = self._parse_inline(text)
        self._ensure_space(10)
        x_start = self.get_x()
        self.set_text_color(34, 34, 34)
        for txt, style in parts:
            fam = self.mono_font if style == 'code' else self.font_name
            st = ""
            if style == 'bold':
                st = "B"
            elif style == 'italic':
                st = "I"
            elif style == 'bold_italic':
                st = "BI"
            sz = 8 if style == 'code' else 9.5
            self.set_font(fam, st, sz)
            self.write(sz * 0.55, txt)
        self.ln(5)

    def render_blockquote(self, text):
        self._ensure_space(10)
        # 左侧红线
        self.set_draw_color(233, 69, 96)
        self.set_line_width(1.2)
        x = self.l_margin + 2
        y0 = self.get_y()
        self.set_font(self.font_name, "I", 9)
        self.set_text_color(80, 80, 80)
        self.set_x(self.l_margin + 6)
        self.multi_cell(self._content_width() - 6, 5, text)
        y1 = self.get_y()
        self.line(x, y0, x, y1)
        self.set_text_color(34, 34, 34)
        self.ln(3)

    def render_code_block(self, text):
        self._ensure_space(15)
        self.ln(2)
        x0 = self.l_margin
        self.set_fill_color(245, 245, 245)
        # 使用 CJK 字体渲染代码块（支持代码中的中文注释和字符串）
        self.set_font(self.font_name, "", 7.5)
        self.set_text_color(60, 60, 60)
        lines = text.split('\n')
        for line in lines:
            self.set_x(x0 + 3)
            # 截断过长的行
            max_chars = int(self._content_width() / 3.0)
            if len(line) > max_chars:
                line = line[:max_chars - 2] + '..'
            self.cell(self._content_width() - 6, 4.2, line, fill=True)
            self.ln()
        self.set_text_color(34, 34, 34)
        self.ln(3)

    def render_table(self, rows):
        """rows: list of lists (first row = header)"""
        self._ensure_space(len(rows) * 7 + 10)
        self.ln(2)
        w = self._content_width()
        ncols = max(len(r) for r in rows)
        col_w = w / ncols
        fs = 7.5

        for i, row in enumerate(rows):
            self.set_x(self.l_margin)
            if i == 0:
                # Header
                self.set_fill_color(22, 33, 62)
                self.set_text_color(255, 255, 255)
                self.set_font(self.font_name, "B", fs)
            else:
                self.set_fill_color(248, 249, 250) if i % 2 == 0 else self.set_fill_color(255, 255, 255)
                self.set_text_color(34, 34, 34)
                self.set_font(self.font_name, "", fs)

            for j, cell in enumerate(row):
                self.cell(col_w, 5.5, cell.strip(), border=0, fill=True)
            self.ln()
        self.set_text_color(34, 34, 34)
        self.ln(3)

    def render_list(self, items, ordered=False):
        for idx, item in enumerate(items):
            self._ensure_space(8)
            prefix = f"{idx + 1}. " if ordered else "- "
            self.set_font(self.font_name, "", 9.5)
            self.set_text_color(34, 34, 34)
            self.set_x(self.l_margin + 4)
            self.cell(6, 5, prefix)
            self._write_body(item.strip(), size=9.5)
        self.ln(2)

    def render_hr(self, _content=""):
        self.ln(2)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        y = self.get_y()
        self.line(self.l_margin + 30, y, self.w - self.r_margin - 30, y)
        self.ln(4)

    # ─── 行内解析 ───
    def _parse_inline(self, text):
        """解析行内 Markdown 格式，返回 [(text, style), ...]"""
        parts = []
        # 保护行内代码
        text = re.sub(r'`([^`]+)`', r'⟨code⟩\1⟨/code⟩', text)
        # 粗斜体
        text = re.sub(r'\*\*\*(.+?)\*\*\*', r'⟨bi⟩\1⟨/bi⟩', text)
        # 粗体
        text = re.sub(r'\*\*(.+?)\*\*', r'⟨b⟩\1⟨/b⟩', text)
        # 斜体
        text = re.sub(r'\*(.+?)\*', r'⟨i⟩\1⟨/i⟩', text)
        text = re.sub(r'_(.+?)_', r'⟨i⟩\1⟨/i⟩', text)

        # 分割
        segments = re.split(r'(⟨/?\w+⟩)', text)
        current_style = 'normal'
        for seg in segments:
            if seg == '⟨code⟩':
                current_style = 'code'
            elif seg == '⟨/code⟩':
                current_style = 'normal'
            elif seg == '⟨b⟩':
                current_style = 'bold'
            elif seg == '⟨/b⟩':
                current_style = 'normal'
            elif seg == '⟨i⟩':
                current_style = 'italic'
            elif seg == '⟨/i⟩':
                current_style = 'normal'
            elif seg == '⟨bi⟩':
                current_style = 'bold_italic'
            elif seg == '⟨/bi⟩':
                current_style = 'normal'
            elif seg:
                parts.append((seg, current_style))
        return parts


def parse_markdown(md_text: str):
    """将 Markdown 解析为块级元素列表"""
    blocks = []
    lines = md_text.split('\n')
    i = 0

    while i < len(lines):
        line = lines[i]

        # 空行
        if not line.strip():
            i += 1
            continue

        # 代码块
        if line.strip().startswith('```'):
            lang = line.strip()[3:].strip()
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append(('code', '\n'.join(code_lines)))
            continue

        # 表格
        if '|' in line and line.strip().startswith('|'):
            table_rows = []
            while i < len(lines) and '|' in lines[i]:
                row = [c.strip() for c in lines[i].split('|')[1:-1]]
                # 跳过分隔行
                if not all(re.match(r'^[-: ]+$', c) for c in row):
                    table_rows.append(row)
                i += 1
            if table_rows:
                blocks.append(('table', table_rows))
            continue

        # 标题
        m = re.match(r'^(#{1,4})\s+(.+)$', line)
        if m:
            level = len(m.group(1))
            blocks.append((f'h{level}', m.group(2).strip()))
            i += 1
            continue

        # 水平线
        if re.match(r'^[-*_]{3,}\s*$', line.strip()):
            blocks.append(('hr', ''))
            i += 1
            continue

        # 引用块
        if line.startswith('>'):
            quote_lines = []
            while i < len(lines) and lines[i].startswith('>'):
                quote_lines.append(lines[i][1:].strip())
                i += 1
            blocks.append(('blockquote', ' '.join(quote_lines)))
            continue

        # 无序列表
        if re.match(r'^[\s]*[-*+]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[\s]*[-*+]\s+', lines[i]):
                items.append(re.sub(r'^[\s]*[-*+]\s+', '', lines[i]))
                i += 1
            blocks.append(('ul', items))
            continue

        # 有序列表
        if re.match(r'^[\s]*\d+[.)]\s+', line):
            items = []
            while i < len(lines) and re.match(r'^[\s]*\d+[.)]\s+', lines[i]):
                items.append(re.sub(r'^[\s]*\d+[.)]\s+', '', lines[i]))
                i += 1
            blocks.append(('ol', items))
            continue

        # 普通段落
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].startswith('```') and not lines[i].startswith('|') and not re.match(r'^(#{1,4}\s|>|[-*+]\s|\d+[.)]\s|^[-*_]{3,})', lines[i]):
            para_lines.append(lines[i].strip())
            i += 1
        blocks.append(('p', ' '.join(para_lines)))

    return blocks


def _make_cover(pdf: ChinesePDF):
    """生成封面页"""
    pdf.add_page()
    pdf.ln(45)
    w = pdf._content_width()

    pdf.set_font(pdf.font_name, "B", 26)
    pdf.set_text_color(26, 26, 46)
    pdf.cell(w, 13, "ComfyUI Wan2.2 工作流", align="C")
    pdf.ln(16)
    pdf.set_font(pdf.font_name, "B", 18)
    pdf.cell(w, 11, "专有名词功能逻辑深度解析", align="C")
    pdf.ln(14)

    pdf.set_draw_color(233, 69, 96)
    pdf.set_line_width(0.8)
    xc = pdf.w / 2
    pdf.line(xc - 50, pdf.get_y(), xc + 50, pdf.get_y())
    pdf.ln(14)

    pdf.set_font(pdf.font_name, "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(w, 8, "适用环境：ComfyUI-aki-v3  +  RTX 5070 Ti (16GB VRAM)", align="C")
    pdf.ln(7)
    pdf.cell(w, 8, "核心模型：Wan2.2 T2V / I2V 14B  +  NSFW LoRA", align="C")
    pdf.ln(7)
    pdf.cell(w, 8, "生成日期：2026-05-07", align="C")
    pdf.ln(20)

    pdf.set_font(pdf.font_name, "", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(w, 7, "本文档从底层数学原理出发，逐项解析 ComfyUI Wan2.2 工作流中", align="C")
    pdf.ln(6)
    pdf.cell(w, 7, "每个专有名词的功能逻辑、设计动机与参数调优策略。", align="C")
    pdf.ln(6)
    pdf.cell(w, 7, "面向需要深入理解模型机制的高级用户与开发者。", align="C")


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    print(f"Reading: {md_path.name}")
    md_text = md_path.read_text(encoding="utf-8")

    print("Parsing Markdown structure...")
    # 替换字体不支持的 Unicode 符号
    md_text = md_text.replace('\u26a0\ufe0f', '[!]')   # ⚠️
    md_text = md_text.replace('\u274c', '[X]')          # ❌
    md_text = md_text.replace('\u2705', '[OK]')         # ✅
    md_text = md_text.replace('\u2713', '[v]')          # ✓
    md_text = md_text.replace('\u2717', '[x]')          # ✗
    md_text = md_text.replace('\u2022', '-')            # •
    blocks = parse_markdown(md_text)
    print(f"  Found {len(blocks)} blocks")

    print("Generating PDF...")
    pdf = ChinesePDF()
    pdf.set_auto_page_break(True, margin=18)

    # 封面
    _make_cover(pdf)

    # 内容页
    pdf.add_page()

    dispatch = {
        'h1': pdf.render_h1,
        'h2': pdf.render_h2,
        'h3': pdf.render_h3,
        'h4': pdf.render_h4,
        'p': pdf.render_p,
        'blockquote': pdf.render_blockquote,
        'code': pdf.render_code_block,
        'table': pdf.render_table,
        'ul': lambda x: pdf.render_list(x, ordered=False),
        'ol': lambda x: pdf.render_list(x, ordered=True),
        'hr': pdf.render_hr,
    }

    for block_type, content in blocks:
        renderer = dispatch.get(block_type)
        if renderer:
            try:
                renderer(content)
            except Exception as e:
                print(f"  WARNING: Failed to render {block_type}: {e}")
        else:
            print(f"  SKIP: unknown block type '{block_type}'")

    # 保存
    pdf.output(str(pdf_path))
    file_size = pdf_path.stat().st_size
    print(f"SUCCESS!  PDF: {pdf_path.name}  ({file_size / 1024:.1f} KB)")
    print(f"  {pdf_path}")


if __name__ == "__main__":
    if not MD_FILE.exists():
        print(f"ERROR: {MD_FILE} not found")
        sys.exit(1)
    convert_md_to_pdf(MD_FILE, PDF_FILE)
