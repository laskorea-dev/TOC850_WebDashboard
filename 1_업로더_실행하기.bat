@echo off
:: Force CMD to use UTF-8 Encoding to prevent Korean character issues
chcp 65001 > nul

cd /d "%~dp0"

echo ========================================================
echo [Uploader] TOC B2B GUI Uploader EXE is launching...
echo ========================================================

if exist gui_uploader.exe (
    start "" gui_uploader.exe
    echo [OK] Uploader launched successfully in background.
) else (
    echo [ERROR] gui_uploader.exe not found! Please check the folder.
    pause
)

