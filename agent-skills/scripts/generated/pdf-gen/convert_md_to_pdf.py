# -*- coding: utf-8 -*-
"""
将 Markdown 深度解析文档转换为 PDF
使用 markdown → HTML → weasyprint 管线
"""
import sys
import os
from pathlib import Path

import markdown
from weasyprint import HTML

# 路径配置
DOCS_DIR = Path(__file__).resolve().parent.parent / "agent-skills" / "docs"
MD_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.md"
PDF_FILE = DOCS_DIR / "2026-05-07_NSFW工作流深度解析_专有名词功能逻辑.pdf"

# CSS 样式 - 面向 A4 PDF 优化的中文排版
CSS_STYLE = """
@page {
    size: A4;
    margin: 2cm 2.2cm 2cm 2.2cm;
    @bottom-center {
        content: counter(page);
        font-family: "Microsoft YaHei", "SimHei", sans-serif;
        font-size: 9pt;
        color: #888;
    }
}

body {
    font-family: "Microsoft YaHei", "SimHei", "Noto Sans SC", sans-serif;
    font-size: 10.5pt;
    line-height: 1.7;
    color: #222;
    text-align: justify;
}

h1 {
    font-size: 20pt;
    font-weight: bold;
    color: #1a1a2e;
    border-bottom: 3px solid #e94560;
    padding-bottom: 6pt;
    margin-top: 24pt;
    margin-bottom: 12pt;
    page-break-before: always;
}

h1:first-of-type {
    page-break-before: avoid;
}

h2 {
    font-size: 15pt;
    font-weight: bold;
    color: #16213e;
    border-bottom: 1.5px solid #0f3460;
    padding-bottom: 4pt;
    margin-top: 20pt;
    margin-bottom: 10pt;
}

h3 {
    font-size: 12pt;
    font-weight: bold;
    color: #333;
    margin-top: 14pt;
    margin-bottom: 8pt;
}

h4 {
    font-size: 11pt;
    font-weight: bold;
    color: #444;
    margin-top: 10pt;
    margin-bottom: 6pt;
}

p {
    margin: 6pt 0;
}

code {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 8.5pt;
    background-color: #f4f4f4;
    padding: 1pt 4pt;
    border-radius: 3pt;
    color: #c7254e;
}

pre {
    font-family: "Cascadia Code", "Consolas", "Courier New", monospace;
    font-size: 8pt;
    background-color: #1e1e1e;
    color: #d4d4d4;
    padding: 10pt;
    border-radius: 6pt;
    line-height: 1.4;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
}

pre code {
    background: none;
    color: inherit;
    padding: 0;
}

blockquote {
    margin: 8pt 0;
    padding: 8pt 14pt;
    border-left: 4px solid #e94560;
    background-color: #fef5f7;
    color: #555;
    font-style: italic;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 10pt 0;
    font-size: 9pt;
}

th {
    background-color: #16213e;
    color: white;
    padding: 6pt 8pt;
    text-align: left;
    font-weight: bold;
}

td {
    padding: 5pt 8pt;
    border-bottom: 1px solid #ddd;
}

tr:nth-child(even) {
    background-color: #f8f9fa;
}

tr:hover {
    background-color: #e8f0fe;
}

ul, ol {
    margin: 4pt 0;
    padding-left: 20pt;
}

li {
    margin: 2pt 0;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 16pt 0;
}

strong {
    color: #16213e;
}

a {
    color: #e94560;
    text-decoration: none;
}

img {
    max-width: 100%;
}

.math-block, .math {
    overflow-x: auto;
}

/* KaTeX fallback */
.katex {
    font-size: 1.05em;
}
"""


def convert_md_to_pdf(md_path: Path, pdf_path: Path, css: str) -> None:
    """Convert a Markdown file to a styled PDF."""

    print(f"读取 Markdown: {md_path}")
    md_text = md_path.read_text(encoding="utf-8")

    print("转换为 HTML...")
    # 使用扩展：表格、代码高亮、围栏代码块、目录、脚注
    extensions = [
        "markdown.extensions.tables",
        "markdown.extensions.fenced_code",
        "markdown.extensions.codehilite",
        "markdown.extensions.toc",
        "markdown.extensions.nl2br",
        "markdown.extensions.sane_lists",
    ]
    html_body = markdown.markdown(md_text, extensions=extensions)

    # 包装为完整 HTML
    html_full = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="utf-8">
    <title>ComfyUI Wan2.2 工作流 · 专有名词功能逻辑深度解析</title>
    <style>{css}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    print(f"生成 PDF: {pdf_path}")
    HTML(string=html_full).write_pdf(str(pdf_path))

    file_size = pdf_path.stat().st_size
    print(f"✅ PDF 生成完成！文件大小: {file_size / 1024:.1f} KB")
    print(f"   路径: {pdf_path}")


if __name__ == "__main__":
    if not MD_FILE.exists():
        print(f"❌ 找不到 Markdown 文件: {MD_FILE}")
        sys.exit(1)

    convert_md_to_pdf(MD_FILE, PDF_FILE, CSS_STYLE)
