#!/usr/bin/env python3
"""
WhatDreamsCost-ComfyUI 安装测试脚本
用于验证项目是否正确安装和配置
"""

import sys
import os

def test_imports():
    """测试必要的模块导入"""
    print("测试模块导入...")
    
    try:
        import torch
        print(f"✅ PyTorch: {torch.__version__}")
    except ImportError as e:
        print(f"❌ PyTorch 导入失败: {e}")
        return False
    
    try:
        import numpy as np
        print(f"✅ NumPy: {np.__version__}")
    except ImportError as e:
        print(f"❌ NumPy 导入失败: {e}")
        return False
    
    try:
        from PIL import Image
        print(f"✅ Pillow: {Image.__version__}")
    except ImportError as e:
        print(f"❌ Pillow 导入失败: {e}")
        return False
    
    try:
        import av
        print(f"✅ PyAV: {av.__version__}")
    except ImportError as e:
        print(f"❌ PyAV 导入失败: {e}")
        return False
    
    return True

def test_comfyui_imports():
    """测试 ComfyUI 相关导入"""
    print("\n测试 ComfyUI 导入...")
    
    try:
        import folder_paths
        print("✅ folder_paths 模块")
    except ImportError as e:
        print(f"❌ folder_paths 导入失败: {e}")
        return False
    
    try:
        import comfy.model_management
        print("✅ comfy.model_management 模块")
    except ImportError as e:
        print(f"❌ comfy.model_management 导入失败: {e}")
        return False
    
    return True

def test_project_structure():
    """测试项目结构"""
    print("\n测试项目结构...")
    
    required_files = [
        "__init__.py",
        "ltx_director.py",
        "ltx_director_guide.py",
        "multi_image_loader.py",
        "ltx_sequencer.py",
        "ltx_keyframer.py",
        "speech_length_calculator.py",
        "load_audio_ui.py",
        "load_video_ui.py",
        "patches.py",
        "prompt_relay.py",
        "js",
        "example_workflows"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少文件/目录: {', '.join(missing_files)}")
        return False
    else:
        print("✅ 项目结构完整")
        return True

def main():
    """主测试函数"""
    print("WhatDreamsCost-ComfyUI 安装测试")
    print("=" * 40)
    
    # 测试项目结构
    structure_ok = test_project_structure()
    
    print("\n" + "=" * 40)
    print("测试结果:")
    print(f"项目结构: {'✅ 通过' if structure_ok else '❌ 失败'}")
    
    if structure_ok:
        print("\n🎉 项目结构验证通过！")
        print("\n注意: 模块导入测试需要在 ComfyUI 环境中运行。")
        print("\n下一步:")
        print("1. 启动 ComfyUI")
        print("2. 检查节点列表中是否出现 WhatDreamsCost 节点")
        print("3. 加载示例工作流测试功能")
        print("\n如需在 ComfyUI 环境中测试导入，请在 ComfyUI 的 Python 环境中运行:")
        print("  import sys")
        print("  sys.path.insert(0, 'D:/ComfyUI-aki-v3/agent-projects/whatdreamscost-comfyui')")
        print("  from ltx_director import LTXDirector")
        return 0
    else:
        print("\n⚠️  项目结构验证失败，请检查文件完整性。")
        return 1

if __name__ == "__main__":
    sys.exit(main())