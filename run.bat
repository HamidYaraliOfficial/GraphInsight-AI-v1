@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title GraphInsight AI
echo ============================================================
echo   GraphInsight AI                         (Developer: Hamid Yarali)
echo ============================================================
echo.

rem ---- 1. Python 3.11+ -------------------------------------------------------
set "PY="
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3.10" "py -3.9" "py -3.8" "py -3" "python" "python3") do (
    if not defined PY (
        %%~C -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul && set "PY=%%~C"
    )
)
if not defined PY (
    echo [ERROR] Python 3.8 or newer was not found.
    echo         Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^) and double-click run.bat again.
    goto :fail
)
for /f "delims=" %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%V"
echo [OK] Python !PYVER!

rem ---- 2. virtual environment -------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] Creating the virtual environment ^(first run only^) ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment ^(.venv^). Check the disk space and the permissions of this folder.
        goto :fail
    )
)
set "VPY=%~dp0.venv\Scripts\python.exe"

rem ---- 3. dependencies: installed only when requirements.txt changed ----------
set "REQ_HASH="
for /f "skip=1 tokens=1" %%H in ('certutil -hashfile "requirements.txt" SHA256') do if not defined REQ_HASH set "REQ_HASH=%%H"
set "OLD_HASH="
if exist ".venv\.requirements.sha256" set /p OLD_HASH=<".venv\.requirements.sha256"
if "!REQ_HASH!"=="!OLD_HASH!" (
    echo [OK] Dependencies are up to date.
) else (
    echo [..] Installing dependencies ^(first run: a few minutes, needs internet^) ...
    "%VPY%" -m pip install --upgrade pip >nul 2>nul
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Installing the dependencies failed. Check the internet connection ^(or proxy^) and try again.
        echo         If a package has no wheel for your Python version, install Python 3.10 / 3.11 / 3.12.
        goto :fail
    )
    >".venv\.requirements.sha256" echo !REQ_HASH!
)

rem ---- 4. Tesseract hint --------------------------------------------------------
set "TESS="
where tesseract >nul 2>nul && set "TESS=1"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS=1"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS=1"
if not defined TESS (
    echo [WARNING] Tesseract OCR is not installed: axis numbers must be typed manually.
    echo           https://github.com/UB-Mannheim/tesseract/wiki
)
if not exist "data" mkdir data

rem ---- 5. start the dashboard --------------------------------------------------
echo.
echo [OK] Starting GraphInsight AI at  http://127.0.0.1:8501
echo      Close this window ^(or press Ctrl+C^) to stop the program.
echo.
"%VPY%" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
if errorlevel 1 (
    echo.
    echo [ERROR] The program stopped with an error. See the message above and data\logs\graphinsight.log
    goto :fail
)
exit /b 0

:fail
echo.
echo The window stays open so that you can read the message above.
pause
exit /b 1
