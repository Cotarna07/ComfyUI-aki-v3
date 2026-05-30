@echo off
chcp 65001 >nul
echo ============================================================
echo  ComfyUI 测试启动（带 fp8 噪点修复参数）
echo  参数: --disable-dynamic-vram --disable-smart-memory
echo  说明: 仅本次命令行生效, 不修改绘世启动器任何配置
echo ============================================================
echo.
cd /d "D:\ComfyUI-aki-v3\ComfyUI"
"D:\ComfyUI-aki-v3\python\python.exe" main.py --auto-launch --preview-method auto --disable-cuda-malloc --disable-dynamic-vram --disable-smart-memory
pause
