@echo off
setlocal

cd /d H:\git\MultiScheduler
set "MULTISCHEDULER_OUTPUT_DIR=H:\git\MultiScheduler\output"
if not exist "%MULTISCHEDULER_OUTPUT_DIR%" mkdir "%MULTISCHEDULER_OUTPUT_DIR%"

echo ==== %DATE% %TIME% multischeduler start ====>> "%MULTISCHEDULER_OUTPUT_DIR%\scheduled_scan.log"
uv run multischeduler --days 7 --max-gap-hours 2 >> "%MULTISCHEDULER_OUTPUT_DIR%\scheduled_scan.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"
echo ==== %DATE% %TIME% multischeduler end exit=%EXIT_CODE% ====>> "%MULTISCHEDULER_OUTPUT_DIR%\scheduled_scan.log"

endlocal & exit /b %EXIT_CODE%
