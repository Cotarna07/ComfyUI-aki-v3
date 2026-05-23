# -*- coding: utf-8 -*-
"""
将 Markdown 深度解析文档转换为 PDF
使用 markdown → HTML → fpdf2 管线（纯 Python，无需外部依赖）
字体：Windows 系统 SimHei（黑体）
"""
import sys
import os
import re
from pathlib import Path

import markdown
from fpdf import FPDF
from fpdf.fonts import FontFace

# 路径配置
DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"
MD_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.md"
PDF_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.pdf"

FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"


class ChinesePDF(FPDF):
    """支持中文的 PDF 类"""

    def __init__(self):
        super().__init__("P", "mm", "A4")
        self._setup_fonts()

    def _setup_fonts(self):
        """注册中英文和等宽字体"""
        simhei = FONT_DIR / "simhei.ttf"
        if simhei.exists():
            # 注册所有变体（使用同一字体文件模拟）
            for style in ["", "B", "I", "BI"]:
                self.add_font("CJK", style, str(simhei))
            self.font_name = "CJK"
            print(f"  Using font: SimHei ({simhei.stat().st_size // 1024}KB)")
        else:
            raise RuntimeError("SimHei font not found - cannot render Chinese")

        # 等宽字体
        for name in ["CascadiaCode.ttf", "consola.ttf", "cour.ttf"]:
            p = FONT_DIR / name
            if p.exists():
                self.add_font("Mono", "", str(p))
                self.mono_font = "Mono"
                break
        else:
            self.mono_font = "Courier"

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

    def safe_write_html(self, html_text: str):
        """安全写入 HTML 内容"""
        # 预处理 KaTeX
        html_text = re.sub(r'\$\$([^$]+)\$\$', r'<i>[\1]</i>', html_text)
        html_text = re.sub(r'\$([^$]+)\$', r'<i>\1</i>', html_text)

        # fpdf2 2.8.7 不支持 table/span/div 标签，转换为 <p> + <br>
        html_text = re.sub(r'</?table[^>]*>', '', html_text)
        html_text = re.sub(r'</?thead[^>]*>', '', html_text)
        html_text = re.sub(r'</?tbody[^>]*>', '', html_text)
        html_text = re.sub(r'</?span[^>]*>', '', html_text)
        html_text = re.sub(r'</?div[^>]*>', '', html_text)
        html_text = re.sub(r'<tr[^>]*>', '<p>', html_text)
        html_text = re.sub(r'</tr>', '</p>', html_text)
        html_text = re.sub(r'<t[dh][^>]*>', '', html_text)
        html_text = re.sub(r'</t[dh]>', ' | ', html_text)

        # 预处理代码块：fpdf2 对嵌套 code-in-pre 支持不好
        html_text = re.sub(
            r'<pre><code.*?>(.*?)</code></pre>',
            r'<pre>\1</pre>',
            html_text, flags=re.DOTALL
        )
        # 行内 code 标签保留（fpdf2 支持）

        # 清理 HTML 转义
        html_text = html_text.replace('&quot;', '"')
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')

        F = self.font_name
        M = self.mono_font
        tag_styles = {
            'h1': FontFace(family=F, size_pt=17),
            'h2': FontFace(family=F, size_pt=13),
            'h3': FontFace(family=F, size_pt=11.5),
            'h4': FontFace(family=F, size_pt=10.5),
            'p':  FontFace(family=F, size_pt=9.5),
            'li': FontFace(family=F, size_pt=9.5),
            'pre': FontFace(family=M, size_pt=7.5),
            'blockquote': FontFace(family=F, size_pt=9),
            'a':  FontFace(family=F, size_pt=9.5),
        }

        try:
            super().write_html(html_text, tag_styles=tag_styles)
        except Exception as e:
            print(f"  WARNING: HTML rendering issue: {e}")
            print(f"  Falling back to plain text mode...")
            clean = re.sub(r'<[^>]+>', '', html_text)
            clean = re.sub(r'\n{3,}', '\n\n', clean)
            if self.page == 0:
                self.add_page()
            self.set_font(self.font_name, "", 9.5)
            self.multi_cell(0, 5, clean)


def _make_cover(pdf: ChinesePDF):
    """生成封面页"""
    pdf.add_page()
    pdf.ln(45)

    # 主标题
    pdf.set_font(pdf.font_name, "", 26)
    pdf.set_text_color(26, 26, 46)
    # 使用 cell 逐行写标题（避免 multi_cell align=C 的问题）
    w = pdf.w - 2 * pdf.l_margin
    pdf.cell(w, 13, "ComfyUI Wan2.2 工作流", align="C")
    pdf.ln(16)
    pdf.set_font(pdf.font_name, "", 18)
    pdf.cell(w, 11, "专有名词功能逻辑深度解析", align="C")
    pdf.ln(14)

    # 分隔线
    pdf.set_draw_color(233, 69, 96)
    pdf.set_line_width(0.8)
    x_center = pdf.w / 2
    pdf.line(x_center - 50, pdf.get_y(), x_center + 50, pdf.get_y())
    pdf.ln(14)

    # 元信息
    pdf.set_font(pdf.font_name, "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(w, 8, "适用环境：ComfyUI-aki-v3  +  RTX 5070 Ti (16GB VRAM)", align="C")
    pdf.ln(7)
    pdf.cell(w, 8, "核心模型：Wan2.2 T2V / I2V 14B  +  NSFW LoRA", align="C")
    pdf.ln(7)
    pdf.cell(w, 8, "生成日期：2026-05-07", align="C")
    pdf.ln(20)

    # 简要说明
    pdf.set_font(pdf.font_name, "", 9)
    pdf.set_text_color(130, 130, 130)
    pdf.cell(w, 7, "本文档从底层数学原理出发，逐项解析 ComfyUI Wan2.2 工作流中", align="C")
    pdf.ln(6)
    pdf.cell(w, 7, "每个专有名词的功能逻辑、设计动机与参数调优策略。", align="C")
    pdf.ln(6)
    pdf.cell(w, 7, "面向需要深入理解模型机制的高级用户与开发者。", align="C")


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """主转换函数"""
    print(f"Reading: {md_path.name}")
    md_text = md_path.read_text(encoding="utf-8")

    print("Converting Markdown → HTML...")
    extensions = [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.codehilite",
        "markdown.extensions.toc",
        "markdown.extensions.nl2br",
        "markdown.extensions.sane_lists",
    ]
    html_body = markdown.markdown(md_text, extensions=extensions)

    print("Generating PDF...")
    pdf = ChinesePDF()
    pdf.set_auto_page_break(True, margin=18)

    # 封面
    _make_cover(pdf)

    # 内容
    pdf.add_page()
    pdf.set_font(pdf.font_name, "", 9.5)
    pdf.set_text_color(34, 34, 34)

    print("  Writing content (this may take a moment)...")
    pdf.safe_write_html(html_body)

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
