@echo off
setlocal
echo ============================================
echo AKASH TECH SOLUTIONS
echo Project - Bulk Image Processing
echo Windows EXE Build
echo ============================================
echo.

if not exist venv\Scripts\python.exe (
    echo Creating virtual environment...
    python -m venv venv
)

echo Installing dependencies...
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe -m pip install -r requirements-dev.txt

echo.
echo Building EXE...
venv\Scripts\python.exe -m PyInstaller --noconsole --onefile --clean --name "AKASH_Bulk_Image_Processing" app.py

echo.
echo ============================================
echo BUILD COMPLETE
echo EXE: dist\AKASH_Bulk_Image_Processing.exe
echo ============================================
pause
