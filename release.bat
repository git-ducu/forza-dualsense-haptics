@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title DHE Release Zip

echo.
echo [DHE Release Packager]
echo.

if not exist "dist\DHE" (
    echo ERROR: dist\DHE not found. Run build.bat first.
    pause
    exit /b 1
)

set "ZIP_NAME=DHE_v1.02.zip"

if exist "%ZIP_NAME%" del "%ZIP_NAME%"

echo Copying helper batch files to dist...
copy /y "DHE_SelfTest.bat" "dist\DHE\" >nul 2>nul
copy /y "DHE_ExportDiagnostics.bat" "dist\DHE\" >nul 2>nul
copy /y "GUIDE.md" "dist\DHE\" >nul 2>nul

echo Creating %ZIP_NAME%...
powershell -Command "Compress-Archive -Path 'dist\DHE\*' -DestinationPath '%ZIP_NAME%' -Force"

if exist "%ZIP_NAME%" (
    echo.
    echo Done: %ZIP_NAME%
) else (
    echo ERROR: zip creation failed.
)
echo.
pause
