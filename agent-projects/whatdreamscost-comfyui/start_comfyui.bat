@echo off
echo ========================================
echo WhatDreamsCost-ComfyUI 启动脚本
echo ========================================
echo.

echo 检查 ComfyUI 目录...
if exist "D:\ComfyUI-aki-v3\ComfyUI\main.py" (
    echo ✅ ComfyUI 目录存在
) else (
    echo ❌ ComfyUI 目录不存在
    pause
    exit /b 1
)

echo.
echo 检查 WhatDreamsCost-ComfyUI 链接...
if exist "D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\WhatDreamsCost-ComfyUI" (
    echo ✅ WhatDreamsCost-ComfyUI 链接存在
) else (
    echo ❌ WhatDreamsCost-ComfyUI 链接不存在
    echo 请运行以下命令创建链接:
    echo cmd /c mklink /J "D:\ComfyUI-aki-v3\ComfyUI\custom_nodes\WhatDreamsCost-ComfyUI" "D:\ComfyUI-aki-v3\agent-projects\whatdreamscost-comfyui"
    pause
    exit /b 1
)

echo.
echo 启动 ComfyUI...
cd /d "D:\ComfyUI-aki-v3\ComfyUI"
python main.py

pause