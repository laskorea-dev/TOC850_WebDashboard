# 에이전트 지침서 (Agent Instructions)

이 프로젝트(TOC850_WebDashboard)에서 작업할 때 에이전트가 준수해야 하는 지침입니다.

## 1. 프로젝트 개요 및 목적
- **프로젝트 명**: TOC850_WebDashboard
- **목적**: TOC(총유기탄소) 측정 계측기 데이터를 Supabase 데이터베이스에 업로드하고, 이를 웹 대시보드로 시각화하여 모니터링 및 알람(이메일 발송 등)을 처리하는 시스템입니다.
- **주요 구성**:
  - `gui_uploader.py`: 계측기 PC에서 실행되며 데이터를 Supabase에 업로드하고 설정된 임계치에 따라 메일을 발송하는 Python GUI 프로그램
  - `dashboard/`: Supabase 데이터를 실시간으로 모니터링하고 알람 임계치를 설정하는 React/Vite 기반 웹 대시보드

## 2. 작업 수행 시 필수 준수 사항
- **회의록 및 개발 이력 관리**:
  - 사용자 요구사항의 변경이나 작업 완료 시, 반드시 [meeting_notes](file:///d:/antigravity/db_upload_and_dashboard/meeting_notes) 폴더 내에 일자별 회의록(예: `2026-06-18_alert_and_test_page_design.md`)을 작성해야 합니다.
  - 프로젝트의 진척 및 작업 현황은 루트의 [2_투두리스트_Task_List.md](file:///d:/antigravity/db_upload_and_dashboard/2_투두리스트_Task_List.md)에, 누적 개발 타임라인 및 기술 내역은 [3_히스토리_및_완료보고서.md](file:///d:/antigravity/db_upload_and_dashboard/3_히스토리_및_완료보고서.md)에 기록하고 최신화해야 합니다.
- **데이터베이스 스키마 변경 제한**:
  - Supabase 데이터베이스의 기존 테이블 구조는 변경하지 않습니다. 임계치 설정 등 추가 데이터는 기존 `toc_alert_high` 컬럼의 JSON 구조 내에 기록하여 확장합니다.
- **Git 푸시 제한**:
  - 로컬 테스트 및 사용자의 최종 확인이 완료되기 전까지는 원격 저장소에 `git push`를 하지 않고 로컬 커밋만 유지합니다.
- **답변 언어**:
  - 사용자와의 소통 및 최종 설명은 항상 명확하고 친절한 한국어(한글)로 작성해야 합니다.
