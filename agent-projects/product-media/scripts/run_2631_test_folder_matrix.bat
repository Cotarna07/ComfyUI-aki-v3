@echo off
setlocal

set "REPO=%~dp0..\..\.."
set "PYTHON=%REPO%\.venv\Scripts\python.exe"
set "SCRIPT=%~dp0run_2631_test_folder_matrix.py"

"%PYTHON%" "%SCRIPT%" %*
exit /b %ERRORLEVEL%
