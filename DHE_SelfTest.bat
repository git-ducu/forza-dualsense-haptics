@echo off
cd /d "%~dp0"
echo.
echo === DHE Self-Test ===
echo.
DHE.exe --self-test
echo.
if exist "data\diagnostics" (
    echo Opening diagnostics folder...
    explorer "data\diagnostics"
) else (
    echo Note: diagnostics folder not found.
)
echo.
pause
