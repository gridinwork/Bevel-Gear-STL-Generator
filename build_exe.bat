@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run install.bat first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

".venv\Scripts\python.exe" -m PyInstaller ^
 --noconfirm ^
 --clean ^
 --windowed ^
 --name BevelGearGenerator ^
 --collect-all pyvista ^
 --collect-all pyvistaqt ^
 --collect-all vtk ^
 --collect-all trimesh ^
 --collect-all numpy ^
 main.py

echo.
echo Output:
echo dist\BevelGearGenerator\BevelGearGenerator.exe
pause
endlocal
