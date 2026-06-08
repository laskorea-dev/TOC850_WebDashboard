@echo off
:: Force CMD to use UTF-8 Encoding to prevent Korean character issues
chcp 65001 > nul

cd /d "%~dp0"

echo =======================================================================
echo  🚀 [GitHub Uploader] 깃허브 코드 처음 업로드하기 (자동 도우미)
echo =======================================================================
echo  본 도우미는 대용량 DB 파일(.db), 비밀키(credentials.json), 빌드된 EXE 등을
echo  자동으로 걸러내고(안전 보안), 오직 필요한 소스코드만 깔끔하게 골라
echo  깃허브에 처음 업로드할 수 있도록 도와줍니다.
echo =======================================================================
echo.
echo  [필수 선행 조건]
echo  1. https://github.com/ 에 가입하고 로그인해 두세요.
echo  2. 오른쪽 상단 [+] -> [New repository]를 누릅니다.
echo  3. Repository name에 "toc-b2b-dashboard" 라고 칩니다.
echo  4. 공개범위를 반드시 "Private(비공개)"로 설정하고 생성합니다!
echo.
echo =======================================================================
pause
echo.

REM 1. Git 초기화
echo  1. 로컬 저장소 초기화 중 (git init)...
git init
echo.

REM 2. 파일 추가 및 커밋
echo  2. 필요한 소스코드 파일 분류 및 추가 중...
git add .
echo.
echo  3. 커밋 생성 중 (commit)...
git commit -m "First commit - Supabase Multi-Tenancy Dashboard"
echo.

REM 3. 깃허브 원격 주소 입력 받기
echo =======================================================================
echo  [중요] 방금 깃허브에서 만든 비공개 저장소의 주소를 입력해 주세요.
echo  예: https://github.com/username/toc-b2b-dashboard.git
echo =======================================================================
set /p repo_url="👉 깃허브 주소를 붙여넣고 엔터(Enter): "

if "%repo_url%"=="" (
    echo.
    echo  [에러] 주소가 입력되지 않았습니다. 프로그램을 재실행해 주세요.
    pause
    exit
)

REM 원격 주소 등록
git remote remove origin 2>nul
git remote add origin %repo_url%
git branch -M main

echo.
echo =======================================================================
echo  4. 깃허브 서버로 코드 업로드 시작 (git push)...
echo     (처음 실행 시 깃허브 로그인 웹창이 뜰 수 있습니다. 로그인을 완료해 주세요!)
echo =======================================================================
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo  [오류] 업로드 중 문제가 발생했습니다.
    echo  - 깃허브 로그인 연동이 정상적으로 되지 않았거나 주소가 다를 수 있습니다.
) else (
    echo.
    echo =======================================================================
    echo  🎉 깃허브 업로드 성공!
    echo     코드가 안전하게 비공개로 업로드되었습니다.
    echo.
    echo     이제 Vercel (https://vercel.com) 로 가셔서
    echo     이 저장소를 불러와(Import) 100%% 무료 웹 배포를 시작하시면 됩니다!
    echo =======================================================================
)

pause
exit
