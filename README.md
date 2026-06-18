# TOC-850 온라인 계측 모니터링 시스템 & 대시보드

이 프로젝트는 TOC-850 계측 장비에서 측정된 실시간 데이터를 로컬 DB(SQLite)에서 수집하여 클라우드 데이터베이스(Supabase)에 적재하고, 이를 실시간 모니터링 웹 대시보드로 시각화하는 통합 B2B 모니터링 솔루션입니다.

---

## 📂 프로젝트 주요 구성 및 파일 구조

- 📁 `dashboard/` : React + Vite + Recharts 기반의 모니터링 웹 대시보드 소스 코드
- 📁 `meeting_notes/` : 프로젝트 개발 이력 및 의사결정 추적용 문서 보관소
- 📄 `gui_uploader.py` : Windows 환경의 계측기 연동용 실시간 클라우드/SMTP 알림 전송 GUI 업로더 프로그램
- 📄 `uploader.py` : 로컬 SQLite DB 데이터를 구글 스프레드시트로 올리는 CLI용 파이썬 스크립트
- 📄 `uploader_config.json` : 로컬 SMTP 서버 설정 및 데이터베이스 연결 환경 설정 파일
- 📄 `toc_db.db` : 현장 계측 결과가 기록되는 로컬 SQLite 데이터베이스

---

## 🛠️ 프로젝트 관리 및 개발 이력 지침 (필수 준수 사항)

이 프로젝트는 개발 흐름의 투명성을 확보하고, 여러 작업자(에이전트 및 개발자)가 협업하거나 다른 세션에서 개발을 이어갈 때 **컨텍스트 유실을 방지하기 위해 문서화 체계를 상시 관리**해야 합니다.

### 1. 회의록 (Meeting Notes) 관리
- 주요 논의 사항, 아키텍처 결정, 사용자 신규 요구사항 수렴 시 반드시 회의록을 작성해야 합니다.
- **작성 위치**: [meeting_notes/](file:///d:/antigravity/db_upload_and_dashboard/meeting_notes/) 폴더
- **규칙**: `YYYY-MM-DD_주제.md` 형식의 네이밍 규칙을 준수하여 마크다운 문서로 작성합니다.

### 2. 프로젝트 타임라인 (Timeline) 관리
- 개발 마일스톤 및 릴리즈 현황, 현재 진행 중인 검토 사안을 전체적으로 트래킹합니다.
- **작성 위치**: [meeting_notes/project_timeline.md](file:///d:/antigravity/db_upload_and_dashboard/meeting_notes/project_timeline.md)
- **규칙**: 새로운 작업 완료 및 갱신 요구사항이 발생할 때마다 타임라인 문서의 개발 이력을 업데이트하여 동기화합니다.

> [!IMPORTANT]
> **프로젝트에 참여하는 모든 개발자 및 AI 에이전트는 작업을 시작하기 전 `meeting_notes/` 폴더를 최우선으로 검토하고, 작업 완료 시 회의록과 타임라인을 갱신해야 합니다.**

---

## 🚀 기동 및 실행 가이드

### 1. 로컬 업로더 실행
- `python gui_uploader.py`를 실행하여 실시간 SQLite 전송 엔진을 가동합니다.
- SMTP 설정을 등록하면 웹 설정창의 알림 수신처 주소로 경고 메일 발송 기능이 가동됩니다.

### 2. 웹 대시보드 로컬 실행
```bash
cd dashboard
npm install
npm run dev
```
- 브라우저 주소창에 `http://localhost:5173/?site=Samyang_Incheon` 형식으로 접속합니다.
- 관리자 테스트 및 샌드박스 설정 기능을 확인하려면 `?admin=true` 파라미터를 추가하여 접속해 검증합니다.
