import os
import sys
import shutil
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION = "5.5"
PACKAGE_NAME = f"계측기_PC_배포패키지_v{VERSION}"
SPEC_FILENAME = f"gui_uploader_v{VERSION}.spec"
SPEC_PATH = os.path.join(BASE_DIR, SPEC_FILENAME)
PACKAGE_PATH = os.path.join(BASE_DIR, PACKAGE_NAME)

SPEC_CONTENT = f"""# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['gui_uploader.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='gui_uploader_v{VERSION}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"""

LAUNCHER_CONTENT = f"""@echo off
chcp 65001 > nul
title TOC B2B Uploader Launcher v{VERSION}

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
"""

CONFIG_EXAMPLE_CONTENT = """{
    "db_path": "toc_db.db",
    "google_sheet_name": "TOC_Measure_Dashboard",
    "supabase_table": "measure_logs_v2",
    "site_id": "auto",
    "device_id": "auto",
    "site_name": "auto",
    "interval_seconds": 900,
    "last_datetime": "",
    "last_query": "N/A",
    "is_paused": true,
    "is_mock": true,
    "supabase_url": "",
    "supabase_key": ""
}
"""

README_CONTENT = f"""# TOC-850 B2B SYNC CLIENT v{VERSION} 배포 가이드

본 패키지는 현장 측정 PC의 SQLite DB에서 측정값을 자동으로 수집하여 Supabase 실시간 클라우드로 전송해주는 동기화 솔루션 배포 패키지입니다.

## 🆕 v{VERSION} 변경 사항

**서버 기준 시각 조회 실패 시 전체 재업로드를 하지 않습니다.**

이전 버전은 증분 기준점을 잡기 위한 서버 조회가 실패하면(통신 장애, API 차단 등)
'서버에 데이터가 없음'으로 잘못 해석해 **로컬 DB 전체를 다시 올리려** 했습니다.
서버에 중복 방지 제약이 없으면 그대로 중복이 쌓입니다(실제 발생 이력 있음).

v{VERSION}부터는 조회 실패와 '데이터 없음'을 구분하여, 실패한 주기는 건너뛰고
다음 주기에 재시도합니다. 측정값은 로컬 DB에 그대로 보존되므로 유실은 없습니다.

로그에 아래가 뜨면 정상 동작입니다(서버 복구 시 자동으로 따라잡습니다).

```
[동기화 보류] 서버 기준 시각을 확인하지 못했습니다. 전체 재업로드를 막기 위해 이번 주기를 건너뜁니다.
```

## 🛰️ 원격 관리 (v{VERSION} 신규)

본사에서 Supabase `device_config` 값만 바꾸면 현장 방문 없이 아래를 제어합니다.
업로더가 **매 동기화 주기마다 이 값을 먼저 읽고** 전송 여부를 결정합니다.

| 컬럼 | 용도 |
|---|---|
| `remote_paused` | `true` 로 두면 다음 주기부터 동기화 중지 (긴급 차단) |
| `interval_seconds` | 동기화 주기 원격 조정 (60초 미만은 무시) |
| `notice` | 현장 로그창에 표시할 공지 문구 |
| `target_version` | 이 기기가 올라갈 버전. 자가 업데이트가 수행됨 |

**자가 업데이트**는 `target_version` 이 현재 버전보다 높을 때만 동작하며,
`uploader_release` 테이블의 `sha256` 과 대조해 **무결성이 일치할 때만** 설치합니다.
설치는 현재 exe 를 `.old` 로 옮기고 새 파일로 재기동하는 방식이며, 어느 단계에서든
실패하면 원래 파일로 되돌리고 기존 버전으로 계속 동작합니다.

> 📌 서버에 위 컬럼이 아직 없어도 v{VERSION}은 정상 동작합니다.
> `tools/migrations/001_uploader_remote_management.sql` 을 실행하면 그 시점부터 적용됩니다.

> ⚠️ **새 버전은 반드시 한 지점에 먼저 배포하고 확인한 뒤 전체로 넓히십시오.**
> 전체에 동시에 지정하면 문제가 있을 때 5개 지점이 함께 멈춥니다.

## 📦 구성 파일
1. **`gui_uploader_v{VERSION}.exe`**: 동기화 실행 프로그램
2. **`1_업로더_실행하기.bat`**: 간편 실행 배치 스크립트 (최신 버전 exe 자동 선택)
3. **`uploader_config.example.json`**: 설정 파일 **템플릿**

## ♻️ 기존 설치본 업데이트 절차 (이미 운영 중인 현장)

> ⚠️ **`uploader_config.json`을 절대 덮어쓰지 마십시오.** 지점 ID와 Supabase 자격
> 증명이 들어 있습니다. 이 파일이 초기화되면 안전장치가 걸려 동기화가 조용히 멈춥니다.
> 그래서 이 패키지에는 설정 파일을 `.example.json` 이름으로만 넣었습니다.

1. 트레이에서 기존 업로더를 **완전히 종료**합니다.
2. 새 `gui_uploader_v{VERSION}.exe`와 `1_업로더_실행하기.bat` **두 개만** 기존 폴더에 복사합니다.
3. `1_업로더_실행하기.bat`을 실행합니다.
4. 로그 첫 줄에 버전이 v{VERSION}으로 표시되는지, 그리고 아래가 뜨는지 확인합니다.
   ```
   서버 최신 데이터 시각 조회 중...
   서버 최신 데이터: <시각>
   ```
5. 이전 버전 exe(`gui_uploader_v5.4.exe` 등)는 정상 확인 후 삭제하십시오.

설정 파일과 `toc_db.db`는 그대로 두면 됩니다. 건드릴 필요가 없습니다.

## ⚙️ 최초 현장 설치 및 세팅 절차

1. **DB 파일 복사 및 경로 셋업**:
   - 계측기 측정 프로그램이 생성하는 `toc_db.db` 파일을 본 폴더 내에 배치하거나, 다른 폴더에 있을 경우 `uploader_config.example.json`을 `uploader_config.json`으로 복사한 뒤 `db_path`에 절대경로를 입력합니다. (예: `C:\\LAS_Korea\\toc_db.db`)

2. **설정 수정 및 수동 활성화 (Fail-safe 해제)**:
   - 본 프로그램은 최초 배포 시 `auto` 플래그 안전장치에 의해 **일시정지(PAUSED)** 상태로 가동됩니다.
   - `gui_uploader_v{VERSION}.exe`를 실행한 후 화면 상에서 아래 항목을 실질적인 고유 값으로 기재하고 **[모든 설정 및 자격 증명 저장 💾]**을 클릭하십시오.
     - **지점 식별자 ID (Site ID)**: 예) `Samyang_Incheon`
     - **사이트 이름 (Site Name)**: 예) `삼양사 인천공장`
     - **상세 인프라 설정 (Supabase)**: 본사에서 발급받은 Supabase URL 및 API Key 입력
   - 저장이 완료되면 하단의 **[업로드 재개 ▶]**를 누르면 안전장치가 해제되며, 동기화가 활성화됩니다.

> ⚠️ **Site ID와 Site Name 중 하나라도 `auto`로 남아 있으면** 안전장치가 유지되어
> 자동 동기화와 지점 등록이 모두 보류됩니다. **반드시 두 값을 모두 실제 값으로 입력**하십시오.

## ✅ 설치 후 필수 확인 (이걸 안 하면 대시보드 접속이 안 됩니다)

업로더 로그 창에 아래 둘 중 하나가 반드시 떠야 합니다.

```
[원격 설정 동기화] '<기기ID>'의 지점 정보를 site_id='<지점ID>', ... 으로 갱신했습니다.
[자동 등록 성공] Supabase에 '<기기ID>' 기기 설정(지점 '<지점ID>')이 자동 등록되었습니다!
```

이 로그가 뜨면 Supabase `device_config`에 지점이 등록된 것이며, 그때부터
`https://<대시보드주소>/?site=<지점ID>` 접속이 가능합니다.

반대로 아래가 뜨면 아직 미설정 상태입니다.

```
[원격 설정 보류] 지점 식별자/사이트 이름이 'auto' 상태이므로 device_config 동기화를 건너뜁니다.
```

> 💡 측정 데이터가 클라우드에 올라가는 것과, 대시보드 접속 권한이 열리는 것은 **별개**입니다.
> 데이터는 `measure_logs_v2`에, 접속 권한은 `device_config`에 등록됩니다.
> 데이터가 보이는데 접속이 안 된다면 **[설정 저장 💾]을 한 번 더 누르십시오.**

## 🩺 문제 발생 시

같은 폴더에서 `diagnose_sync.py`(또는 배포된 진단 도구)를 실행하여 결과를 개발실에 전달하십시오.
"""

def main():
    print("==================================================")
    print(f" TOC-850 Uploader v{VERSION} 빌드 및 배포 자동화")
    print("==================================================")
    
    # 1. Spec 파일 생성
    print("1. PyInstaller Spec 파일 생성 중...")
    with open(SPEC_PATH, "w", encoding="utf-8") as f:
        f.write(SPEC_CONTENT)
    print(f" -> Spec 파일 생성 완료: {SPEC_FILENAME}")
    
    # 2. PyInstaller 실행하여 빌드
    print("2. PyInstaller를 실행하여 단일 실행파일(EXE) 컴파일을 시작합니다...")
    try:
        # PyInstaller 설치 확인
        import sys
        subprocess.run(["pyinstaller", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("[오류] 시스템에 'pyinstaller'가 설치되어 있지 않거나 PATH에 추가되어 있지 않습니다.")
        print("  -> pip install pyinstaller 를 실행한 후 다시 시도하십시오.")
        sys.exit(1)
        
    build_cmd = ["pyinstaller", SPEC_PATH, "--clean", "--noconfirm"]
    result = subprocess.run(build_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("[오류] PyInstaller 컴파일 빌드 도중 에러가 발생했습니다.")
        print(result.stderr)
        sys.exit(1)
    print(" -> EXE 파일 빌드 대성공!")

    # 3. 배포 디렉토리 생성 및 구성
    print(f"3. 배포 패키지 디렉토리 생성 중... ({PACKAGE_NAME})")
    if os.path.exists(PACKAGE_PATH):
        shutil.rmtree(PACKAGE_PATH)
    os.makedirs(PACKAGE_PATH)
    
    # EXE 복사
    built_exe = os.path.join(BASE_DIR, "dist", f"gui_uploader_v{VERSION}.exe")
    target_exe = os.path.join(PACKAGE_PATH, f"gui_uploader_v{VERSION}.exe")
    if os.path.exists(built_exe):
        shutil.copy2(built_exe, target_exe)
        print(f" -> EXE 복사 완료: {os.path.basename(target_exe)}")
    else:
        print(f"[오류] 빌드된 EXE 파일을 찾을 수 없습니다: {built_exe}")
        sys.exit(1)
        
    # Launcher bat 복사
    launcher_path = os.path.join(PACKAGE_PATH, "1_업로더_실행하기.bat")
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(LAUNCHER_CONTENT)
    print(f" -> 런처 배치파일 생성 완료: {os.path.basename(launcher_path)}")
    
    # 설정 파일은 '예제'로만 배포한다.
    # uploader_config.json 이라는 이름으로 넣으면, 업데이트 시 폴더째 덮어썼을 때
    # 현장에서 동작 중인 설정(지점 ID·자격증명)이 초기화되고 is_paused=true 로
    # 되돌아가 동기화가 조용히 멈춘다.
    config_path = os.path.join(PACKAGE_PATH, "uploader_config.example.json")
    with open(config_path, "w", encoding="utf-8") as f:
        f.write(CONFIG_EXAMPLE_CONTENT)
    print(f" -> 설정 예제 파일 생성 완료: {os.path.basename(config_path)}")
    
    # README.md 복사
    readme_path = os.path.join(PACKAGE_PATH, "README.md")
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(README_CONTENT)
    print(f" -> README.md 가이드 파일 생성 완료: {os.path.basename(readme_path)}")
    
    # 빌드 산출물 임시 정리 (build 및 spec 파일 제거)
    print("4. 임시 빌드 아티팩트 정리 중...")
    try:
        build_dir = os.path.join(BASE_DIR, "build")
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)
        if os.path.exists(SPEC_PATH):
            os.remove(SPEC_PATH)
    except Exception as e:
        print(f" [경고] 임시 파일 정리 오류: {e}")
        
    print("\n==================================================")
    print(f" [완료] 배포 패키지 구축이 완료되었습니다!")
    print(f" 경로: {PACKAGE_PATH}")
    print("==================================================")

if __name__ == "__main__":
    main()
