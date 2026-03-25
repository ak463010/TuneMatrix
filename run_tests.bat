@echo off
setlocal

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
)

set "QT_QPA_PLATFORM=offscreen"

echo Using %PYTHON_EXE%
%PYTHON_EXE% -m unittest discover -s tests -v
exit /b %ERRORLEVEL%
