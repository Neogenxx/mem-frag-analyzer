@echo off
echo ================================================
echo   MEMSIM - Memory Allocation Simulator
echo ================================================
echo.

cd /d "%~dp0"

REM Activate venv if it exists
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo ERROR: Virtual environment not found!
    echo Run: python -m venv venv
    pause
    exit /b 1
)

REM Install dependencies if needed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

echo.
echo Starting server at http://localhost:8000
echo Press Ctrl+C to stop
echo.

cd backend
uvicorn main:app --host 127.0.0.1 --port 8000