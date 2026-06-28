@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DHE

if not exist "vendor" (
    echo ERROR: vendor folder not found.
    echo Run setup_vendor.bat first.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\vendor;%PYTHONPATH%"
set "PATH=%CD%\vendor;%PATH%"

if not exist "data" mkdir "data"

echo Starting DHE...
python app.py
if errorlevel 1 (
    echo.
    echo DHE crashed or exited with error.
    echo.
    if exist "data\crash.log" (
        echo ===== data\crash.log =====
        type "data\crash.log"
        echo ==========================
    )
    pause
)
