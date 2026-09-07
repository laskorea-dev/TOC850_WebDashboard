@echo off
chcp 65001 > nul
title TOC B2B Uploader Launcher v5.5

echo [TOC-850 Sync Client Launcher]
echo 현장 계측기 데이터 자동 동기화 프로그램을 가동합니다.
echo.

rem 자가 업데이트로 실행파일 이름이 바뀌므로 특정 버전을 고정하지 않는다.
rem 1순위: 업데이터가 남긴 current_exe.txt (정확함)
rem 2순위: 폴더에서 이름순 최신 파일 (최초 설치 시)
rem   ※ 2순위는 문자열 정렬이라 v5.10 이 v5.9 보다 낮게 잡힌다. 그래서
rem      업데이트를 거치면 반드시 1순위 경로를 타도록 해 두었다.
set "TARGET="
if exist "%~dp0current_exe.txt" (
    set /p TARGET=<"%~dp0current_exe.txt"
)
if defined TARGET if not exist "%~dp0%TARGET%" set "TARGET="

if not defined TARGET (
    for /f "delims=" %%F in ('dir /b /o-n "%~dp0gui_uploader_v*.exe" 2^>nul') do (
        if not defined TARGET set "TARGET=%%F"
    )
)

if not defined TARGET (
    echo [오류] gui_uploader_v*.exe 파일을 찾을 수 없습니다.
    echo 배포 폴더가 올바르게 구성되어 있는지 확인하십시오.
    pause
    exit /b 1
)

echo [안내] 실행 대상: %TARGET%
start "" "%~dp0%TARGET%"
echo [안내] 업로더가 정상적으로 가동되어 백그라운드 트레이로 기동됩니다.
exit
