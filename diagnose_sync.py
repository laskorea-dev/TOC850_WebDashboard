import os
import sys
import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "uploader_config.json")

def print_result(step, status, message):
    mark = "[정상]" if status == "ok" else "[경고]" if status == "warn" else "[오류]"
    print(f"{step} {mark} {message}")

def test_supabase_request(url, headers, method="GET", data=None):
    try:
        req = urllib.request.Request(url, headers=headers, method=method, data=data)
        with urllib.request.urlopen(req, timeout=10) as res:
            return res.status, res.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return -1, str(e).encode('utf-8')

def main():
    print("==================================================")
    print(" [TOC-850 B2B 동기화 시스템 현장 자가진단 도구]")
    print("==================================================")
    print(f"실행 일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"실행 경로: {BASE_DIR}")
    print("--------------------------------------------------")

    # Step 1. uploader_config.json 존재 여부 및 로드 검사
    if not os.path.exists(CONFIG_PATH):
        print_result("Step 1", "error", f"설정 파일 uploader_config.json이 존재하지 않습니다.\n   경로: {CONFIG_PATH}")
        sys.exit(1)
        
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        print_result("Step 1", "ok", "uploader_config.json 파일을 성공적으로 로드했습니다.")
    except Exception as e:
        print_result("Step 1", "error", f"설정 파일 JSON 파싱 실패: {e}")
        sys.exit(1)

    # 파라미터 획득
    db_path = config.get("db_path", "toc_db.db")
    # 하위 호환
    db_path_absolute = db_path if os.path.isabs(db_path) else os.path.join(BASE_DIR, db_path)
    site_id = config.get("site_id", "")
    device_id = config.get("device_id", "")
    site_name = config.get("site_name", "")
    supabase_url = config.get("supabase_url", "").rstrip('/')
    supabase_key = config.get("supabase_key", "")
    supabase_table = config.get("supabase_table", "measure_logs_v2")
    is_mock = config.get("is_mock", True)

    print(f"   [로드된 설정 요약]")
    print(f"   - 로컬 DB 경로: {db_path_absolute}")
    print(f"   - 지점 ID (Site ID): {site_id}")
    print(f"   - 장비 ID (Device ID): {device_id}")
    print(f"   - 사이트 이름: {site_name}")
    print(f"   - 전송 모드: {'로컬 파일 저장 (Mock)' if is_mock else 'Supabase 실시간 전송 (Prod)'}")
    print("--------------------------------------------------")

    # Step 2. 초기 기동 제한 (Fail-safe) 세팅 검사
    is_auto = False
    if not site_id or site_id.lower() == "auto":
        is_auto = True
    if not site_name or site_name.lower() == "auto":
        is_auto = True
    if not device_id or device_id.lower() == "auto":
        is_auto = True

    if is_auto:
        print_result("Step 2", "warn", "설정값 중 'auto' 상태인 항목이 있습니다. 최초 기동 시 Fail-safe가 작동하여 일시정지 상태가 됩니다.\n   현장 ID 및 한글 사이트명을 실제 값으로 수정한 뒤 가동해 주십시오.")
    else:
        print_result("Step 2", "ok", "모든 현장 기기 정보가 고유 식별자로 설정되어 있습니다. (Fail-safe 통과)")

    # Step 3. SQLite 데이터베이스 상태 검사
    print("--------------------------------------------------")
    if not os.path.exists(db_path_absolute):
        print_result("Step 3", "error", f"로컬 SQLite DB 파일을 지정된 경로에서 찾을 수 없습니다: {db_path_absolute}")
    else:
        conn = None
        try:
            conn = sqlite3.connect(db_path_absolute)
            cursor = conn.cursor()
            
            # View 존재 여부 검사
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='Measure_Result_With_Channel_Name'")
            view_exists = cursor.fetchone()
            if not view_exists:
                print_result("Step 3", "error", "SQLite DB 내에 필수 뷰 'Measure_Result_With_Channel_Name'이 존재하지 않습니다.")
            else:
                print_result("Step 3", "ok", "SQLite DB 및 필수 연동 뷰가 정상적으로 확인되었습니다.")
                
                # 데이터 건수 및 마지막 측정 시간 체크
                cursor.execute("SELECT COUNT(*), MAX(Date_Time) FROM Measure_Result_With_Channel_Name")
                count, max_time = cursor.fetchone()
                print(f"   - 로컬 DB 누적 측정 데이터 건수: {count}건")
                print(f"   - 로컬 DB 최종 측정 시각: {max_time if max_time else '데이터 없음'}")
        except Exception as e:
            print_result("Step 3", "error", f"SQLite DB 파일 쿼리 중 오류 발생: {e}")
        finally:
            if conn:
                conn.close()

    # Step 4. Supabase 연동 검사 (Mock 모드인 경우 Skip)
    print("--------------------------------------------------")
    if is_mock:
        print_result("Step 4", "warn", "현재 시뮬레이션 모드(Mock Mode) 설정 상태입니다. Supabase 연동 테스트를 건너뜁니다.")
    else:
        if not supabase_url or not supabase_key:
            print_result("Step 4", "error", "Supabase URL 또는 Key 설정이 비어 있습니다. 실시간 연동이 불가능합니다.")
        else:
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json"
            }
            
            # 4-1. Supabase REST API 통신 테스트
            print("Supabase API 연결 및 인증 검증 시도 중...")
            if "/rest/v1" in supabase_url:
                device_config_url = f"{supabase_url}/device_config?device_id=eq.{urllib.parse.quote(device_id)}"
            else:
                device_config_url = f"{supabase_url}/rest/v1/device_config?device_id=eq.{urllib.parse.quote(device_id)}"
                
            status, body = test_supabase_request(device_config_url, headers)
            
            if status == 200:
                print_result("Step 4-1", "ok", "Supabase API 연결 및 인증 인가가 정상 확인되었습니다.")
                # device_config 등록 여부 분석
                res_data = json.loads(body.decode('utf-8'))
                if len(res_data) > 0:
                    print_result("Step 4-2", "ok", f"원격 'device_config' 테이블에 해당 기기 ID('{device_id}')가 등록되어 있습니다.")
                    db_site_name = res_data[0].get("site_name", "")
                    print(f"   - 원격 매핑 사이트 이름: {db_site_name}")
                else:
                    print_result("Step 4-2", "warn", f"원격 'device_config' 테이블에 해당 기기 ID('{device_id}')용 행이 없습니다.\n   Uploader 최초 정상 가동 시 자동 등록이 시도됩니다.")
            else:
                print_result("Step 4-1", "error", f"Supabase API 접속 실패! HTTP 상태코드: {status}\n   응답: {body.decode('utf-8')[:300]}")

            # 4-3. measure_logs_v2 쓰기 권한 테스트 (GET/SELECT 테스트)
            if "/rest/v1" in supabase_url:
                measure_url = f"{supabase_url}/{supabase_table}?limit=1"
            else:
                measure_url = f"{supabase_url}/rest/v1/{supabase_table}?limit=1"
            m_status, m_body = test_supabase_request(measure_url, headers)
            if m_status in [200, 206]:
                print_result("Step 4-3", "ok", f"측정 로그 테이블('{supabase_table}') 쿼리 권한(R)이 확인되었습니다.")
            else:
                print_result("Step 4-3", "error", f"측정 로그 테이블('{supabase_table}') 접근 권한 오류. HTTP 상태코드: {m_status}\n   응답: {m_body.decode('utf-8')[:300]}")

    print("==================================================")
    print(" 자가진단이 종료되었습니다. 위 결과를 개발실에 전달바랍니다.")
    print("==================================================")
    input("\n종료하려면 엔터 키를 누르십시오...")

if __name__ == "__main__":
    main()
