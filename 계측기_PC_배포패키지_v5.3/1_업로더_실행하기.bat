@echo off
chcp 65001 > nul
title TOC B2B Uploader Launcher v5.3

echo [TOC-850 Sync Client Launcher]
echo 현장 계측기 데이터 자동 동기화 프로그램을 가동합니다.
echo.

if not exist "%~dp0gui_uploader_v5.3.exe" (
    echo [오류] gui_uploader_v5.3.exe 파일을 찾을 수 없습니다.
    echo 배포 폴더가 올바르게 구성되어 있는지 확인하십시오.
    pause
    exit /b 1
)

start "" "%~dp0gui_uploader_v5.3.exe"
echo [안내] 업로더가 정상적으로 가동되어 백그라운드 트레이로 기동됩니다.
exit
