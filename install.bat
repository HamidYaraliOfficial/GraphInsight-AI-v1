@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title GraphInsight AI - install
echo ============================================================
echo   GraphInsight AI - installation          (Developer: Hamid Yarali)
echo ============================================================
echo.

rem ---- 1. find Python 3.11+ ------------------------------------------------
set "PY="
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3.10" "py -3.9" "py -3.8" "py -3" "python" "python3") do (
    if not defined PY (
        %%~C -c "import sys; sys.exit(0 if sys.version_info>=(3,8) else 1)" >nul 2>nul && set "PY=%%~C"
    )
)
if not defined PY (
    echo [ERROR] Python 3.8 or newer was not found.
    echo         Install it from https://www.python.org/downloads/  ^(tick "Add python.exe to PATH"^) and run this file again.
    goto :fail
)
for /f "delims=" %%V in ('%PY% -c "import sys; print(sys.version.split()[0])"') do set "PYVER=%%V"
echo [OK] Python !PYVER! found  ^(%PY%^)

rem ---- 2. virtual environment ----------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] Creating virtual environment .venv ...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Could not create the virtual environment.
        goto :fail
    )
)
set "VPY=%~dp0.venv\Scripts\python.exe"

rem ---- 3. dependencies (only when requirements.txt changed or --force) -------
set "REQ_HASH="
for /f "skip=1 tokens=1" %%H in ('certutil -hashfile "requirements.txt" SHA256') do if not defined REQ_HASH set "REQ_HASH=%%H"
set "OLD_HASH="
if exist ".venv\.requirements.sha256" set /p OLD_HASH=<".venv\.requirements.sha256"
if /i "%~1"=="--force" set "OLD_HASH="
if "!REQ_HASH!"=="!OLD_HASH!" (
    echo [OK] Dependencies are already installed ^(requirements.txt unchanged^).
) else (
    echo [..] Installing dependencies ^(this can take a few minutes the first time^) ...
    "%VPY%" -m pip install --upgrade pip >nul 2>nul
    "%VPY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [ERROR] Installing the dependencies failed. Typical reasons:
        echo         - no internet connection / proxy: configure pip ^(pip config set global.proxy ...^)
        echo         - a very new Python version without wheels: use Python 3.10, 3.11 or 3.12
        echo         Run this file again after fixing the problem; the full pip message is above.
        goto :fail
    )
    >".venv\.requirements.sha256" echo !REQ_HASH!
)

rem ---- 4. Tesseract OCR (optional but strongly recommended) -------------------
set "TESS="
where tesseract >nul 2>nul && set "TESS=1"
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" set "TESS=1"
if exist "C:\Program Files (x86)\Tesseract-OCR\tesseract.exe" set "TESS=1"
if not defined TESS (
    echo.
    echo [WARNING] Tesseract OCR was not found. Axis numbers cannot be read automatically without it
    echo           ^(you can still type the axis values manually in the dashboard^).
    echo           Install: https://github.com/UB-Mannheim/tesseract/wiki   then run this file again or set TESSERACT_CMD in .env
) else (
    echo [OK] Tesseract OCR found.
)
if not exist "data" mkdir data
echo.
echo Installation finished. Start the program with run.bat  ^(http://127.0.0.1:8501^)
echo.
pause
exit /b 0

:fail
echo.
echo The window stays open so you can read the message above.
pause
exit /b 1
