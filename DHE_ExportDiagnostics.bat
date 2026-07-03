@echo off
cd /d "%~dp0"
echo.
echo === DHE Export Diagnostics ===
echo.
DHE.exe --export-diagnostics
echo.
pause
