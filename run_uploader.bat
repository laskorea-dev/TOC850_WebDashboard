@echo off
:: gui_uploader.py가 위치한 폴더로 작업 디렉토리를 변경합니다.
cd /d "%~dp0"

echo ========================================================
echo Running TOC DB GUI Uploader Window...
echo ========================================================

:: [테스트 모드] 구글 클라우드 API 연동 전에는 아래 명령어를 실행하여 로컬 CSV 대시보드 연동 모드로 테스트합니다.
python gui_uploader.py --mock

:: [실제 연동 모드] 구글 API 설정(credentials.json 추가)이 완료된 후에는 위의 `--mock` 줄을 지우거나 아래 줄의 주석(::)을 해제하여 사용하세요.
:: python gui_uploader.py

echo Uploader finished.
exit /b
