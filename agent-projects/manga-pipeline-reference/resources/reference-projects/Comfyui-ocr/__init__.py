# -*- coding: utf-8 -*-
"""
ComfyUI PaddleOCR Node Plugin
Supports OCR text recognition and coordinate annotation
"""

import sys
import traceback

# 添加调试信息
print("正在加载 PaddleOCR 节点...")

try:
    from .ocr_node import PaddleOCRNode
    print("成功导入 PaddleOCRNode (相对导入)")
except ImportError as e:
    print(f"相对导入失败: {e}")
    try:
        # If relative import fails, try direct import
        from ocr_node import PaddleOCRNode
        print("成功导入 PaddleOCRNode (直接导入)")
    except ImportError as e2:
        print(f"直接导入也失败: {e2}")
        print("完整错误信息:")
        traceback.print_exc()
        # 创建一个占位符类以防止完全失败
        class PaddleOCRNode:
            @classmethod
            def INPUT_TYPES(cls):
                return {"required": {"error": ("STRING", {"default": "PaddleOCR节点加载失败，请检查依赖安装"})}}
            
            RETURN_TYPES = ("STRING",)
            FUNCTION = "error_function"
            CATEGORY = "OCR"
            
            def error_function(self, error):
                return ("PaddleOCR节点加载失败，请检查依赖安装",)

NODE_CLASS_MAPPINGS = {
    "PaddleOCRNode": PaddleOCRNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PaddleOCRNode": "PaddleOCR 文字识别"
}

print("PaddleOCR 节点映射已创建")
print(f"节点类: {NODE_CLASS_MAPPINGS}")

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']