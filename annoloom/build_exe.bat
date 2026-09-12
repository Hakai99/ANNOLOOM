@echo off
REM Build a standalone AnnoLoom.exe — run this from inside the annoloom folder
REM (the one containing pyproject.toml and this file).

echo Installing/upgrading build dependencies...
pip install --upgrade pyinstaller PyQt6

echo.
echo Building AnnoLoom.exe (this can take a minute or two)...
pyinstaller --name AnnoLoom --windowed --onefile --clean AnnoLoom.spec

echo.
echo Done. Your executable is at: dist\AnnoLoom.exe
echo You can copy dist\AnnoLoom.exe anywhere and double-click it to run AnnoLoom.
pause
