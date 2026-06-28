@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DHE Build

echo.
echo [DHE PyInstaller Build]
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: python not found in PATH.
    pause
    exit /b 1
)

python -m PyInstaller --noconfirm dhe.spec
if errorlevel 1 (
    echo.
    echo BUILD FAILED.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\DHE\
echo.
pause
