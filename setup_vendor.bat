@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DHE Setup Vendor

echo.
echo [DHE Setup Vendor]
echo Folder: %CD%
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python was not found in PATH.
    echo Install Python 3.13 x64 (recommended), then run this again.
    pause
    exit /b 1
)

echo Python:
python --version
echo.

if not exist "requirements.txt" (
    echo ERROR: requirements.txt not found.
    pause
    exit /b 1
)

if not exist "vendor" mkdir "vendor"

echo Upgrading pip...
python -m pip install -U pip
if errorlevel 1 (
    echo ERROR: pip upgrade failed.
    pause
    exit /b 1
)

echo.
echo Installing PySide6 system-wide (cannot use --target for Qt)...
python -m pip install --upgrade PySide6
if errorlevel 1 (
    echo ERROR: PySide6 install failed.
    pause
    exit /b 1
)

echo.
echo Installing other dependencies into:
echo   %CD%\vendor
echo.
python -m pip install --upgrade --target "%CD%\vendor" -r requirements-vendor.txt
if errorlevel 1 (
    echo ERROR: dependency install failed.
    pause
    exit /b 1
)

echo.
echo DONE.
echo Run DHE with:
echo   run_dhe.bat
echo.
pause
exit /b 0
