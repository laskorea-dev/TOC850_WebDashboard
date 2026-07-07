@echo off
:: Force CMD to use UTF-8 Encoding to prevent Korean character issues
chcp 65001 > nul

cd /d "%~dp0"

echo ========================================================
echo [Uploader] TOC B2B GUI Uploader EXE is launching...
echo ========================================================

if exist gui_uploader_v5.0.exe (
    start "" gui_uploader_v5.0.exe
    echo [OK] Uploader v5.0 launched successfully in background.
) else (
    echo [ERROR] gui_uploader_v5.0.exe not found! Please check the folder.
    pause
)
