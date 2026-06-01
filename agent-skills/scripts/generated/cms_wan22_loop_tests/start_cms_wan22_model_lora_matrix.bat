@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_cms_wan22_loop_matrix.ps1" -AllModelProfiles %*
pause
