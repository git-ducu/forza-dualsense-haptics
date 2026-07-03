@echo off
cd /d "%~dp0"
echo.
echo === DHE Self-Test ===
echo.
DHE.exe --self-test
echo.
pause
