@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Virtual environment not found.
  echo Run install.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo Program exited with an error.
  pause
  exit /b 1
)
endlocal
