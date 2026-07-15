@echo off
setlocal
set "VENV=%USERPROFILE%\.bitwize-music\venv\Scripts\python.exe"
if exist "%VENV%" (
  "%VENV%" "%~dp0run.py" %*
) else (
  python "%~dp0run.py" %*
)
