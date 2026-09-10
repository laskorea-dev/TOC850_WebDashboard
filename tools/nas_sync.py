# -*- coding: utf-8 -*-
"""
NAS 동기화 — 고객용 TOC850 웹 대시보드

    python tools/nas_sync.py             # 전체 동기화
    python tools/nas_sync.py --dry-run   # 무엇을 할지만 출력
    python tools/nas_sync.py --no-vercel # Vercel 운영 환경변수 조회 건너뜀

이 PC 는 개인용이다. 담당자가 부재하거나 인수인계가 발생했을 때
**NAS 폴더만 통째로 가져가면 작업을 이어갈 수 있어야 한다.**
따라서 소스뿐 아니라 git 히스토리·환경변수·개발 맥락 문서까지 함께 남긴다.

사무실용 저장소(`D:\\antigravity\\toc850_office_dashboard`)의
`scripts/nas-sync.mjs` 를 고객용 구조에 맞게 이식한 것이다.
고객용은 Python(업로더) + React(대시보드) 혼합이고 루트에 package.json 이
없으므로 Node 가 아닌 Python 으로 구현했다.

⚠️ 04_운영관리_인프라정보.md 와 03_대시보드_소스코드/.env.local,
   02_Uploader_원본코드/uploader_config.json 에 실제 키가 들어간다.
   NAS 접근 권한 = 시스템 전체 접근 권한이라는 뜻이므로
   이 폴더의 권한을 개발부로 제한해 두십시오.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Windows 기본 콘솔(cp949)은 ✓·⚠ 같은 기호를 못 찍는다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
NAS_BASE = Path(r"Z:\05. 개발부\01. 개발프로젝트\01. TOC850\08. 소프트웨어")
DEST = NAS_BASE / "05. TOC850_웹대시보드"

# 복사 제외 — 용량만 차지하거나 기계마다 다시 만들어지는 것들
SKIP_NAMES = {"node_modules", "dist", ".vercel", ".git", "__pycache__", ".pytest_cache"}

# 자동 생성 문서 하단에 넣는 표식. 이 표식이 있는 파일은 다음 실행 때 그냥 덮어쓴다.
GEN_MARK = "<!-- nas_sync:generated -->"

# 손으로 쓴 문서 — 절대 건드리지 않는다.
PRESERVED = ["04_운영관리_인프라정보.md", "05_아키텍처_구조_명세서.md"]

# 07_개발_컨텍스트 로 복사할 개발 맥락 (루트 기준 상대 경로)
CONTEXT_ITEMS = [
    "1_작업계획서_System_Architecture.md",
    "2_투두리스트_Task_List.md",
    "3_히스토리_및_완료보고서.md",
    "4_웹_대시보드_무료_배포_가이드.md",
    "TOC850_B2B_시스템_통합명세서.md",
    "docs",
    "meeting_notes",
    "analysis",
    "tools",
]

# 02_Uploader_원본코드 로 복사할 업로더 일체
UPLOADER_ITEMS = [
    "gui_uploader.py",
    "uploader.py",
    "build_release.py",
    "diagnose_sync.py",
    "uploader_config.json",
    "uploader_config.example.json",
    "run_uploader.bat",
    "1_업로더_실행하기.bat",
    "2_대시보드_웹화면_열기.bat",
    "gui_uploader_v5.0_README.md",
]

log = []


def say(msg):
    print(msg)
    log.append(msg)


def ignore_factory(*_):
    def _ignore(_dir, names):
        return {n for n in names if n in SKIP_NAMES}
    return _ignore


def copy_tree(src: Path, dst: Path, dry: bool):
    if dry:
        return
    if dst.exists():
        shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=ignore_factory(), dirs_exist_ok=True)


def copy_item(src: Path, dst_dir: Path, dry: bool):
    if not src.exists():
        return False
    if dry:
        return True
    dst_dir.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        copy_tree(src, dst_dir / src.name, dry)
    else:
        shutil.copy2(src, dst_dir / src.name)
    return True


def git(args):
    try:
        return subprocess.run(
            ["git"] + args, cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60,
        ).stdout.strip()
    except Exception:
        return ""


def parse_env(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        m = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def read_local_env() -> dict:
    for rel in ("dashboard/.env.local", ".env.local"):
        p = ROOT / rel
        if p.exists():
            try:
                return parse_env(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return {}


def read_vercel_env(skip: bool):
    """
    운영(Production) 환경변수의 정본은 Vercel 이다.
    로컬 .env.local 은 개발용이라 값이 다를 수 있다.
    인수인계 문서에 로컬 값을 적으면 인수받은 사람이 운영과 다른 값을 보게 된다.
    """
    if skip:
        return None
    tmp = Path(tempfile.gettempdir()) / f"toc-cust-prod-env-{os.getpid()}"
    try:
        subprocess.run(
            ["npx", "--yes", "vercel@latest", "env", "pull", str(tmp),
             "--environment=production", "--yes"],
            cwd=ROOT / "dashboard", capture_output=True, shell=True, timeout=120,
        )
        if tmp.exists():
            v = parse_env(tmp.read_text(encoding="utf-8", errors="replace"))
            tmp.unlink(missing_ok=True)
            if v:
                return {"env": v, "fresh": True}
    except Exception:
        pass
    finally:
        tmp.unlink(missing_ok=True)

    # CLI 가 안 되면(로그인 만료 등) 이전에 받아둔 파일을 쓴다.
    cached = ROOT / "dashboard" / ".vercel" / ".env.production.local"
    if cached.exists():
        try:
            v = parse_env(cached.read_text(encoding="utf-8", errors="replace"))
            if v.get("VITE_SUPABASE_URL"):
                return {"env": v, "fresh": False}
        except Exception:
            pass
    return None


def jwt_role(token: str) -> str:
    """키 값을 노출하지 않고 role 만 확인한다."""
    import base64, json
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get("role", "?")
    except Exception:
        return "?"


def write_generated(path: Path, body: str, dry: bool):
    """
    자동 생성 문서를 쓴다.
    표식이 없는 기존 파일(= 사람이 쓴 것일 수 있음)은 _보존/ 으로 한 번 백업한 뒤 덮어쓴다.
    """
    if dry:
        return
    if path.exists():
        try:
            old = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            old = ""
        if GEN_MARK not in old:
            keep = path.parent / "_보존"
            keep.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(path, keep / f"{path.stem}.{ts}{path.suffix}")
            say(f"  · 기존 {path.name} → _보존/{path.stem}.{ts}{path.suffix} (사람이 쓴 문서일 수 있어 보관)")
    path.write_text(body + "\n\n" + GEN_MARK + "\n", encoding="utf-8")


def latest_package():
    """가장 높은 버전의 계측기 배포패키지 폴더와 zip 을 찾는다."""
    best, best_v = None, ()
    for p in ROOT.glob("계측기_PC_배포패키지_v*"):
        if not p.is_dir():
            continue
        m = re.search(r"_v([\d.]+)$", p.name)
        if not m:
            continue
        v = tuple(int(x) for x in m.group(1).split("."))
        if v > best_v:
            best, best_v = p, v
    zip_path = None
    if best is not None:
        # with_suffix 는 "..._v5.5" 의 ".5" 를 확장자로 보므로 쓰면 안 된다.
        z = best.parent / (best.name + ".zip")
        if z.exists():
            zip_path = z
    return best, zip_path


def main():
    ap = argparse.ArgumentParser(description="고객용 TOC850 NAS 동기화")
    ap.add_argument("--dry-run", action="store_true", help="무엇을 할지만 출력")
    ap.add_argument("--no-vercel", action="store_true", help="Vercel 운영 환경변수 조회 생략")
    args = ap.parse_args()
    dry = args.dry_run

    if not NAS_BASE.exists():
        print("\n⚠ NAS(Z:) 에 접근할 수 없어 동기화를 건너뜁니다.")
        print("  드라이브 연결 후 `python tools/nas_sync.py` 로 다시 실행하십시오.")
        return 0

    print(f"\n[NAS] {DEST}" + ("   (모의 실행)" if dry else ""))
    if not dry:
        DEST.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit = git(["log", "-1", "--format=%h %s"])
    commit_date = git(["log", "-1", "--format=%ci"])
    remote = git(["remote", "get-url", "origin"])
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    dirty = bool(git(["status", "--porcelain"]))

    local_env = read_local_env()
    pulled = read_vercel_env(args.no_vercel)
    env = pulled["env"] if pulled else local_env
    if pulled and pulled["fresh"]:
        env_source = "Vercel 운영 환경변수 (이번 동기화 시 직접 조회)"
    elif pulled:
        env_source = "Vercel 운영 환경변수 (이전에 받아둔 캐시 — 최신이 아닐 수 있음)"
    elif args.no_vercel:
        env_source = "로컬 `dashboard/.env.local` (--no-vercel 지정)"
    else:
        env_source = "⚠️ 로컬 `dashboard/.env.local` (개발용) — Vercel 조회 실패. **운영 값과 다를 수 있습니다.**"
    if not pulled and not args.no_vercel:
        say("  ⚠ Vercel 운영 환경변수를 읽지 못했습니다. 로컬 값으로 기록합니다.")
        say("    (`npx vercel login` 후 다시 실행하면 최신값으로 갱신됩니다)")

    # ── 1) 업로더 배포패키지 ──────────────────────────────────────────
    pkg, pkg_zip = latest_package()
    if pkg:
        d = DEST / "01_Uploader_배포패키지"
        if not dry:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True, exist_ok=True)
            copy_tree(pkg, d / pkg.name, dry)
            if pkg_zip:
                shutil.copy2(pkg_zip, d / pkg_zip.name)
        say(f"  ✓ 01_Uploader_배포패키지  ({pkg.name}{' + zip' if pkg_zip else ''})")
    else:
        say("  ⚠ 01_Uploader_배포패키지 — 배포패키지 폴더를 찾지 못했습니다")

    # ── 2) 업로더 원본코드 ────────────────────────────────────────────
    d = DEST / "02_Uploader_원본코드"
    if not dry:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True, exist_ok=True)
    n = 0
    for name in UPLOADER_ITEMS:
        if copy_item(ROOT / name, d, dry):
            n += 1
    if not dry:
        for spec in ROOT.glob("*.spec"):
            shutil.copy2(spec, d / spec.name)
            n += 1
    say(f"  ✓ 02_Uploader_원본코드  ({n}개 항목, uploader_config.json 포함)")

    # ── 3) 대시보드 소스코드 ──────────────────────────────────────────
    src = ROOT / "dashboard"
    if src.exists():
        copy_tree(src, DEST / "03_대시보드_소스코드", dry)
        say("  ✓ 03_대시보드_소스코드  (node_modules · dist · .vercel 제외, .env.local 포함)")
    else:
        say("  ⚠ 03_대시보드_소스코드 — dashboard/ 를 찾지 못했습니다")

    # ── 4)5) 손으로 쓴 문서 — 건드리지 않는다 ─────────────────────────
    for name in PRESERVED:
        p = DEST / name
        if p.exists():
            age = (datetime.now() - datetime.fromtimestamp(p.stat().st_mtime)).days
            flag = "  ← 오래됨, 검토 필요" if age > 60 else ""
            say(f"  · {name}  (보존, 최종수정 {age}일 전){flag}")
        else:
            say(f"  ⚠ {name} 이 없습니다 — 손으로 작성해야 하는 문서입니다")

    # ── 6) git 전체 히스토리 ──────────────────────────────────────────
    bundle = DEST / "06_저장소_백업.bundle"
    if not dry:
        try:
            if bundle.exists():
                bundle.unlink()
            subprocess.run(["git", "bundle", "create", str(bundle), "--all"],
                           cwd=ROOT, capture_output=True, timeout=600, check=True)
            mb = bundle.stat().st_size / 1024 / 1024
            say(f"  ✓ 06_저장소_백업.bundle  ({mb:.1f} MB — git clone 으로 복원 가능)")
        except Exception as e:
            say(f"  ⚠ git bundle 실패: {e}")
    else:
        say("  ✓ 06_저장소_백업.bundle  (모의)")

    # ── 7) 개발 맥락 ──────────────────────────────────────────────────
    d = DEST / "07_개발_컨텍스트"
    if not dry:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True, exist_ok=True)
        agents = ROOT / ".agents" / "AGENTS.md"
        if agents.exists():
            shutil.copy2(agents, d / "AGENTS.md")
    n = 0
    for name in CONTEXT_ITEMS:
        if copy_item(ROOT / name, d, dry):
            n += 1
    say(f"  ✓ 07_개발_컨텍스트  (AGENTS.md + {n}개 항목)")

    # ── 문서 생성 ─────────────────────────────────────────────────────
    key = env.get("VITE_SUPABASE_KEY", "")
    role = jwt_role(key) if key else "?"
    role_warn = ""
    if role == "service_role":
        role_warn = (
            "\n> 🔴 **현재 키는 `service_role`(최고 권한)이며 브라우저 번들에 그대로 공개됩니다.**\n"
            "> 조치 순서는 `07_개발_컨텍스트/docs/2026-09-10_보안_및_트래픽_후속작업_인계.md` 참조.\n"
        )

    pkg_name = pkg.name if pkg else "(없음)"
    dirty_note = "\n> ⚠️ 동기화 시점에 **커밋되지 않은 로컬 변경**이 있었습니다. 소스와 git 이력이 다를 수 있습니다.\n" if dirty else ""

    write_generated(DEST / "README.md", f"""# TOC850 웹 대시보드 (고객용) — 보관함

고객사에 제공 중인 **TOC850 B2B 웹 대시보드**와 현장 **계측기 업로더**의
원본 코드·이력·운영 정보 보관소입니다.
이 폴더를 통째로 가져가면 그대로 작업을 이어받을 수 있도록 구성되어 있습니다.

| 항목 | 값 |
|---|---|
| 운영 주소 | https://toc-850-web-dashboard.vercel.app |
| 최종 동기화 | {stamp} |
| 소스 버전 | {commit or '(git 정보 없음)'} |
| 브랜치 | {branch or '?'} |
| 커밋 일자 | {commit_date or '?'} |
| 업로더 버전 | {pkg_name} |
{dirty_note}
> 처음 인수받으셨다면 [`00_인수인계_안내.md`](00_인수인계_안내.md) 부터 읽으십시오.

---

## 폴더 구성

| 항목 | 내용 | 갱신 |
|---|---|---|
| [`00_인수인계_안내.md`](00_인수인계_안내.md) | **여기부터 읽으십시오.** 환경 구축 → 실행 → 배포 | 자동 |
| [`01_Uploader_배포패키지/`](01_Uploader_배포패키지/) | 현장 PC 에 설치하는 배포본 ({pkg_name}) | 자동 |
| [`02_Uploader_원본코드/`](02_Uploader_원본코드/) | 업로더 Python 원본 · 빌드 스크립트 · 설정 | 자동 |
| [`03_대시보드_소스코드/`](03_대시보드_소스코드/) | React 대시보드 전체. `.env.local` 포함 | 자동 |
| [`04_운영관리_인프라정보.md`](04_운영관리_인프라정보.md) | 🔴 Supabase · Vercel · 계정 및 키 | **수기** |
| [`05_아키텍처_구조_명세서.md`](05_아키텍처_구조_명세서.md) | 전체 시스템 구조와 데이터 흐름 | **수기** |
| [`06_저장소_백업.bundle`](06_저장소_백업.bundle) | git 전체 이력. GitHub 접근 불가 시 복원용 | 자동 |
| [`07_개발_컨텍스트/`](07_개발_컨텍스트/) | AGENTS.md · 투두 · 히스토리 · 회의록 · 분석 | 자동 |

«수기» 항목은 자동 동기화가 **덮어쓰지 않습니다.** 내용이 바뀌면 직접 갱신하십시오.

## 두 대시보드의 관계

| | 고객용 (이 폴더) | 사무실용 |
|---|---|---|
| 보관 위치 | `05. TOC850_웹대시보드` | `06. TOC850_웹대시보드(사무실용)` |
| 대상 | 고객사에 제공 | 사내 전 고객사 통합 감시 |
| 저장소 | `laskorea-dev/TOC850_WebDashboard` | `laskorea-dev/TOC850_OfficeDashboard` |
| Vercel | `toc-850-web-dashboard` | `toc-office-dashboard` |

**공유하는 것은 Supabase 데이터베이스 하나뿐**입니다. 사무실용은 읽기 전용으로 조회합니다.

---

*이 파일은 `python tools/nas_sync.py` 실행 시 자동 생성됩니다. 직접 고쳐도 다음 동기화 때 덮어써집니다.*""", dry)

    write_generated(DEST / "00_인수인계_안내.md", f"""# 인수인계 안내 — 고객용 TOC850 웹 대시보드

**후임자는 이 문서부터 읽으십시오.**

최종 동기화: {stamp} · 소스 버전: {commit or '(git 정보 없음)'}

---

## 0. 이게 뭔가

TOC(총유기탄소) 계측기 데이터를 클라우드로 올리고 웹에서 보는 시스템입니다. 두 부분입니다.

1. **업로더** (`02_Uploader_원본코드/gui_uploader.py`) — 현장 계측기 PC 에서 돌아가는 Python GUI.
   로컬 SQLite 를 읽어 Supabase 로 증분 업로드하고, 임계치 초과 시 텔레그램/메일로 알립니다.
2. **웹 대시보드** (`03_대시보드_소스코드/`) — React/Vite. 고객사가 브라우저로 봅니다.
   `https://toc-850-web-dashboard.vercel.app/?site=<site_id>` 형태로 지점별 접속합니다.

현재 가동 중인 현장 기기는 **{'5대' if True else ''}**이며 목록은 `04_운영관리_인프라정보.md` 및
Supabase `device_config` 테이블에서 확인합니다.

---

## 1. 작업 환경 만들기

### 필요한 것
- **Python 3.10 이상** (업로더 개발·빌드용, PyInstaller 사용)
- **Node.js 20 이상** (대시보드용)
- **Git**

### 대시보드
```bash
# 03_대시보드_소스코드 를 작업할 위치로 복사한다.
# NAS 에서 직접 작업하지 마십시오 — 빌드가 느리고 실수 시 원본이 손상됩니다.

cd <복사한 폴더>
npm install
npm run dev      # http://localhost:5173
```
`.env.local` 이 이미 들어 있어 **추가 설정 없이 바로 실행됩니다.**

### 업로더
```bash
cd 02_Uploader_원본코드
pip install -r requirements.txt   # 없으면: pip install requests pyinstaller
python gui_uploader.py
```
빌드는 `python build_release.py` — 실행 파일과 배포 패키지를 한 번에 만듭니다.

### git 이력까지 복원하려면
```bash
git clone "06_저장소_백업.bundle" <새폴더>
cd <새폴더>
git remote set-url origin {remote or 'https://github.com/laskorea-dev/TOC850_WebDashboard.git'}
```

---

## 2. 배포하기

- **대시보드**: `main` 브랜치에 push 하면 Vercel 이 자동 재배포합니다.
  → **문서만 고친 커밋도 배포를 유발할 수 있으니 주의하십시오.**
- **업로더**: `python build_release.py` 로 패키지를 만든 뒤 현장 PC 에 배포합니다.
  v5.5 부터 **원격 정지·주기 조정·자가 업데이트**가 있어, `device_config` 를 통해
  현장 방문 없이 제어할 수 있습니다.
- 배포 후에는 **반드시 `python tools/nas_sync.py` 를 실행해 이 폴더를 갱신**하십시오.

---

## 3. 반드시 알아야 할 것

### 자격 증명
`04_운영관리_인프라정보.md` 에 Supabase · Vercel 접속 정보가 있습니다.
{role_warn}
### 사무실용 대시보드는 별개입니다
사내 통합 감시 화면(`06. TOC850_웹대시보드(사무실용)`)은 **완전히 다른 저장소**입니다.
같은 Supabase 를 읽을 뿐 코드를 공유하지 않습니다. 증상이 그 화면에서 나타나면
그쪽 폴더에서 처리하십시오. — 한쪽만 보고 진단하면 틀립니다.

### 데이터의 함정
- **`Date_Time` 은 업로드 시각이 아니라 측정 시각입니다.**
- **한 지점(`Site_ID`)에 계측기(`Device_ID`)가 여러 대** 붙을 수 있습니다.
- 측정 주기가 지점마다 다릅니다. 업로더 기본 주기는 900초입니다.
- 결측이 `NULL` 이 아니라 `0` 으로 기록되는 구간이 있습니다.

---

## 4. 더 읽을 것

| 문서 | 내용 |
|---|---|
| `07_개발_컨텍스트/AGENTS.md` | **작업 규칙. 새 세션을 시작하면 먼저 읽으십시오.** |
| `07_개발_컨텍스트/2_투두리스트_Task_List.md` | 진행 중·예정 작업 |
| `07_개발_컨텍스트/3_히스토리_및_완료보고서.md` | 누적 개발 이력 |
| `07_개발_컨텍스트/docs/` | 아키텍처, 후속작업 인계 문서 |
| `07_개발_컨텍스트/meeting_notes/` | 일자별 회의록 |
| `07_개발_컨텍스트/analysis/` | 현장 데이터 분석 기록 |
| `05_아키텍처_구조_명세서.md` | 시스템 전체 구조 |

---

*이 파일은 `python tools/nas_sync.py` 실행 시 자동 생성됩니다. 직접 고쳐도 다음 동기화 때 덮어써집니다.*""", dry)

    say("  ✓ README.md · 00_인수인계_안내.md")

    if role == "service_role":
        say("  🔴 환경변수의 VITE_SUPABASE_KEY 가 service_role 입니다 — 공개 번들에 실려 나갑니다.")

    print(f"\n  값 출처: {env_source}")
    print(f"  완료 — {commit or '?'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
