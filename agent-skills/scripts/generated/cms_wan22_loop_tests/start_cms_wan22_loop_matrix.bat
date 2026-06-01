@echo off
setlocal
cd /d "%~dp0..\..\..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_cms_wan22_loop_matrix.ps1" %*
pause
