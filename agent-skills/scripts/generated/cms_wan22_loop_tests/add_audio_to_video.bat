@echo off
setlocal
cd /d "%~dp0..\..\..\.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0add_audio_to_video.ps1" %*
pause
