# -*- coding: utf-8 -*-
"""
将 Markdown 深度解析文档转换为 PDF
使用 markdown → HTML → fpdf2 管线（纯 Python，无需外部依赖）
"""
import sys
import os
import re
from pathlib import Path

import markdown
from fpdf import FPDF

# 路径配置
DOCS_DIR = Path(__file__).resolve().parent.parent.parent.parent / "docs"
MD_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.md"
PDF_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.pdf"


class ChinesePDF(FPDF):
    """支持中文的 PDF 类，使用系统自带中文字体"""

    def __init__(self):
        super().__init__("P", "mm", "A4")
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"

        yahei = font_dir / "msyh.ttc"
        simhei = font_dir / "simhei.ttf"
        simsun = font_dir / "simsun.ttc"

        if yahei.exists():
            self.add_font("CJK", "", str(yahei))
            self.font_name = "CJK"
        elif simhei.exists():
            self.add_font("CJK", "", str(simhei))
            self.font_name = "CJK"
        elif simsun.exists():
            self.add_font("CJK", "", str(simsun))
            self.font_name = "CJK"
        else:
            print("WARNING: No CJK font found, Chinese characters may not render")
            self.font_name = "Helvetica"

        cascadia = font_dir / "CascadiaCode.ttf"
        consolas = font_dir / "consola.ttf"
        if cascadia.exists():
            self.add_font("Mono", "", str(cascadia))
            self.mono_font = "Mono"
        elif consolas.exists():
            self.add_font("Mono", "", str(consolas))
            self.mono_font = "Mono"
        else:
            self.mono_font = "Courier"

    def header(self):
        if self.page_no() <= 1:
            return
        self.set_font(self.font_name, "", 7)
        self.set_text_color(150, 150, 150)
        self.cell(0, 4, "ComfyUI Wan2.2 - 专有名词功能逻辑深度解析", align="C")
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font(self.font_name, "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"第 {self.page_no()} 页", align="C")

    def safe_write_html(self, html_text: str):
        """安全写入 HTML，处理 fpdf2 的兼容性问题"""
        # 预处理：将 KaTeX 公式转为纯文本
        html_text = re.sub(r'\$\$([^$]+)\$\$', r'<i>[\1]</i>', html_text)
        html_text = re.sub(r'\$([^$]+)\$', r'<i>\1</i>', html_text)

        # 预处理代码块
        html_text = re.sub(
            r'<pre><code.*?>(.*?)</code></pre>',
            r'<pre>\1</pre>',
            html_text, flags=re.DOTALL
        )

        # 清理转义字符
        html_text = html_text.replace('&quot;', '"')
        html_text = html_text.replace('&amp;', '&')
        html_text = html_text.replace('&lt;', '<')
        html_text = html_text.replace('&gt;', '>')

        tag_styles = {
            'h1': {'family': self.font_name, 'size': 18},
            'h2': {'family': self.font_name, 'size': 14},
            'h3': {'family': self.font_name, 'size': 12},
            'h4': {'family': self.font_name, 'size': 11},
            'p':  {'family': self.font_name, 'size': 10},
            'li': {'family': self.font_name, 'size': 10},
            'td': {'family': self.font_name, 'size': 9},
            'th': {'family': self.font_name, 'size': 9},
            'code': {'family': self.mono_font, 'size': 8},
            'pre': {'family': self.mono_font, 'size': 7.5},
            'blockquote': {'family': self.font_name, 'size': 9},
            'i':  {'family': self.font_name, 'size': 10},
            'b':  {'family': self.font_name, 'size': 10},
            'a':  {'family': self.font_name, 'size': 10},
            'em': {'family': self.font_name, 'size': 10},
            'strong': {'family': self.font_name, 'size': 10},
            'span': {'family': self.font_name, 'size': 10},
            'div': {'family': self.font_name, 'size': 10},
        }

        try:
            super().write_html(html_text, tag_styles=tag_styles)
        except Exception as e:
            print(f"  WARNING: HTML parsing issue: {e}, falling back to plain text")
            clean = re.sub(r'<[^>]+>', '', html_text)
            clean = re.sub(r'\n{3,}', '\n\n', clean)
            self.set_font(self.font_name, "", 10)
            self.multi_cell(0, 5.5, clean)


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    """主转换函数"""

    print(f"Reading Markdown: {md_path}")
    md_text = md_path.read_text(encoding="utf-8")

    print("Converting to HTML...")
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

    # ---- 封面 ----
    pdf.add_page()
    pdf.ln(45)
    pdf.set_font(pdf.font_name, "", 28)
    pdf.set_text_color(26, 26, 46)
    pdf.multi_cell(0, 14, "ComfyUI Wan2.2 工作流", align="C")
    pdf.set_font(pdf.font_name, "", 20)
    pdf.multi_cell(0, 12, "专有名词功能逻辑深度解析", align="C")
    pdf.ln(12)
    pdf.set_draw_color(233, 69, 96)
    pdf.set_line_width(0.8)
    pdf.line(50, pdf.get_y(), 160, pdf.get_y())
    pdf.ln(12)
    pdf.set_font(pdf.font_name, "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "适用环境：ComfyUI-aki-v3 + RTX 5070 Ti (16GB VRAM)", align="C")
    pdf.ln(7)
    pdf.cell(0, 8, "核心模型：Wan2.2 T2V / I2V 14B + NSFW LoRA", align="C")
    pdf.ln(7)
    pdf.cell(0, 8, "生成日期：2026-05-07", align="C")

    # ---- 内容 ----
    pdf.add_page()
    pdf.set_font(pdf.font_name, "", 10)
    pdf.set_text_color(34, 34, 34)

    print("  Writing content...")
    pdf.safe_write_html(html_body)

    # ---- 保存 ----
    pdf.output(str(pdf_path))
    file_size = pdf_path.stat().st_size
    print(f"SUCCESS: PDF generated! Size: {file_size / 1024:.1f} KB")
    print(f"  Path: {pdf_path}")


if __name__ == "__main__":
    if not MD_FILE.exists():
        print(f"ERROR: Markdown file not found: {MD_FILE}")
        sys.exit(1)

    convert_md_to_pdf(MD_FILE, PDF_FILE)
