# TOC-850 온라인 계측 모니터링 시스템 & 대시보드

TOC-850 계측 장비의 측정 데이터를 로컬 SQLite에서 수집하여 Supabase에 적재하고,
이를 실시간 웹 대시보드로 시각화하는 다중 사이트 B2B 모니터링 솔루션입니다.

> **📐 시스템 구조 · 지점 식별 체계 · 신규 사이트 온보딩 절차는 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) 를 먼저 읽으십시오.**
> `site_id` / `device_id` 의 관계와 대시보드 접속 URL 규칙이 모두 그 문서에 정리되어 있습니다.

---

## 📂 디렉터리 구조

```
db_upload_and_dashboard/
├── gui_uploader.py              # ★ 현장 계측기 PC용 GUI 업로더 (운영 중인 유일한 업로더)
├── uploader_config.json         # 현장 설정 (git 제외 — 키 포함)
├── uploader_config.example.json # 배포용 설정 템플릿
├── diagnose_sync.py             # 현장 자가진단 도구
├── build_release.py             # 배포 패키지(exe) 빌드 도구
│
├── dashboard/                   # ★ React + Vite + Recharts 웹 대시보드
│   ├── src/App.jsx              #   화면 전체 (약 2,900줄 단일 파일)
│   ├── api/send-alert.js        #   Vercel 서버리스 — 알림 발송
│   └── api/telegram-webhook.js  #   Vercel 서버리스 — 텔레그램 웹훅
│
├── docs/ARCHITECTURE.md         # ★ 시스템 구조 · 식별자 체계 · 온보딩/트러블슈팅
├── meeting_notes/               # 일자별 회의록 (의사결정 이력)
├── .agents/AGENTS.md            # 에이전트/개발자 작업 지침
│
├── 계측기_PC_배포패키지_v5.x/    # 현장 배포용 패키지 (exe는 git 제외)
└── TOC850_Company_Handoff/      # ⚠️ 2026-06 시점 인수인계용 사본 (현행 아님, 참조 금지)
```

### ⚠️ 오해하기 쉬운 항목

| 경로 | 상태 |
|---|---|
| `uploader.py` | **사용하지 않음.** 구글 스프레드시트 연동 시절의 CLI 스크립트 |
| `TOC850_Company_Handoff/` | **현행 아님.** 2026-06 시점 사본. 수정 시 반영되지 않음 |
| `toc_db.db` | 개발용 샘플 DB. 현장 DB는 계측기 PC에 있음 |
| `*.spec` (v4.3~v5.2) | PyInstaller 빌드 산출물. `build_release.py`가 생성 |

---

## 🚀 실행

### 업로더 (현장 계측기 PC)

```bash
python gui_uploader.py
```

설정 후 **💾 설정 저장**을 눌러야 Supabase의 `device_config`에 지점 정보가 등록·갱신됩니다.
문제 발생 시 자가진단:

```bash
python diagnose_sync.py
```

### 웹 대시보드 (로컬)

```bash
cd dashboard
npm install
npm run dev
```

접속 시 **반드시 지점 파라미터가 필요합니다** (기본 지점 폴백 없음):

```
http://localhost:5173/?site=<site_id>
http://localhost:5173/?site=<site_id>&admin=true
```

환경변수는 `dashboard/.env.example`을 `.env.local`로 복사해 설정합니다.

---

## 🛠️ 문서화 규칙 (필수 준수)

여러 작업자·세션 간 컨텍스트 유실을 막기 위해 문서 체계를 상시 관리합니다.

1. **회의록** — 아키텍처 결정 및 신규 요구사항 수렴 시 `meeting_notes/YYYY-MM-DD_주제.md` 작성
2. **투두리스트** — `2_투두리스트_Task_List.md` 진척 갱신
3. **히스토리** — `3_히스토리_및_완료보고서.md` 누적 타임라인 갱신
4. **구조 변경 시** — `docs/ARCHITECTURE.md` 를 코드보다 먼저 갱신

상세 지침은 [.agents/AGENTS.md](.agents/AGENTS.md) 참조.

> [!IMPORTANT]
> 작업 시작 전 `docs/ARCHITECTURE.md` 와 `meeting_notes/` 를 최우선 검토하십시오.

---

## 🔴 보안 미해결

저장소 히스토리에 Supabase **service_role** 키·SMTP 비밀번호·Telegram 토큰이 남아 있습니다.
조치 절차는 [docs/ARCHITECTURE.md §7](docs/ARCHITECTURE.md) 참조.
