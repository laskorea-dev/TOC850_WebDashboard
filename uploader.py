import os
import sys
import json
import sqlite3
from datetime import datetime

# Windows 및 시스템 환경에 상관없이 절대 경로를 안정적으로 계산하기 위한 헬퍼
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "toc_db.db")
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
CONFIG_PATH = os.path.join(BASE_DIR, "last_upload.json")
LOG_PATH = os.path.join(BASE_DIR, "uploader.log")

def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"
    print(log_line.strip())
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_line)
    except Exception as e:
        print(f"Failed to write log: {e}")

def get_last_upload_time():
    """마지막으로 업로드 성공한 Date_Time을 반환합니다."""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                return config.get("last_datetime")
        except Exception as e:
            log_message(f"Error reading config file: {e}")
    return None

def save_last_upload_time(last_datetime):
    """마지막으로 업로드 성공한 Date_Time을 설정 파일에 기록합니다."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump({"last_datetime": last_datetime}, f, ensure_ascii=False, indent=4)
        log_message(f"Saved last upload time: {last_datetime}")
    except Exception as e:
        log_message(f"Failed to save last upload time: {e}")

def fetch_new_data(last_datetime):
    """toc_db.db에서 last_datetime 이후에 추가된 데이터를 가져옵니다."""
    if not os.path.exists(DB_PATH):
        log_message(f"Database file not found at: {DB_PATH}")
        return [], []

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. 뷰 존재 여부 확인
        cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='Measure_Result_With_Channel_Name'")
        if not cursor.fetchone():
            log_message("View 'Measure_Result_With_Channel_Name' does not exist in the database.")
            return [], []

        # 2. 쿼리 구성
        if last_datetime:
            query = """
                SELECT * FROM Measure_Result_With_Channel_Name 
                WHERE Date_Time > ? 
                ORDER BY Date_Time ASC
            """
            cursor.execute(query, (last_datetime,))
        else:
            # 최초 실행 시 데이터가 너무 많을 수 있으므로 최근 1000개만 가져오거나, 
            # 전체 데이터를 다 올릴 수 있도록 설정 (계측기의 측정 데이터 규모에 따라 조절)
            query = """
                SELECT * FROM Measure_Result_With_Channel_Name 
                ORDER BY Date_Time ASC
            """
            cursor.execute(query)
            
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        return rows, columns
    except Exception as e:
        log_message(f"Database error: {e}")
        return [], []
    finally:
        if conn:
            conn.close()

def upload_to_google_sheets(rows, columns):
    """구글 시트에 행 데이터를 전송합니다."""
    if not os.path.exists(CREDENTIALS_PATH):
        log_message(
            f"API Credentials file not found at: {CREDENTIALS_PATH}\n"
            "Please configure your Google Cloud Service Account and download credentials.json to the same folder."
        )
        return False

    try:
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
    except ImportError:
        log_message(
            "Required libraries not installed. Please install them using:\n"
            "pip install gspread oauth2client"
        )
        return False

    try:
        # 구글 시트 인증 설정
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
        client = gspread.authorize(creds)

        # 설정 파일 또는 환경 변수 등에서 구글 시트 이름을 읽어오거나 
        # 여기서는 기본값 'TOC_Measure_Dashboard' 시트를 엽니다.
        spreadsheet_name = "TOC_Measure_Dashboard"
        
        try:
            sheet = client.open(spreadsheet_name).sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            # 시트가 없을 경우, 서비스 계정이 새로운 스프레드시트를 생성하도록 할 수도 있습니다.
            log_message(f"Spreadsheet '{spreadsheet_name}' not found. Creating a new one...")
            new_spreadsheet = client.create(spreadsheet_name)
            
            # 서비스 계정이 만든 시트이므로, 실제 사용자(구글 이메일 주소)와 공유 설정이 필요합니다.
            # (수동으로 구글 시트를 만들어 서비스 계정 이메일을 초대하는 것이 권장되는 방식입니다.)
            log_message(
                f"New sheet created! ID: {new_spreadsheet.id}\n"
                "IMPORTANT: If you created this sheet via script, you need to share it with your google email to view it."
            )
            sheet = new_spreadsheet.sheet1

        # 시트가 완전히 비어있는 경우(첫 행에 데이터가 없는 경우) 헤더를 작성합니다.
        existing_values = sheet.get_all_values()
        if not existing_values:
            sheet.append_row(columns)
            log_message("Written columns header to Google Sheet.")

        # SQLite 데이터의 None(Null) 값을 구글 시트 전송용 빈 문자열로 정제
        formatted_rows = []
        for row in rows:
            formatted_row = ["" if val is None else val for val in row]
            formatted_rows.append(formatted_row)

        # 데이터 일괄 추가 (append_rows)
        sheet.append_rows(formatted_rows, value_input_option="USER_ENTERED")
        log_message(f"Successfully uploaded {len(rows)} new rows to Google Sheet.")
        return True
    except Exception as e:
        log_message(f"Google Sheets upload error: {e}")
        return False

def mock_upload_to_csv(rows, columns):
    """구글 시트 연동 전, 로컬 테스트를 위해 CSV 파일로 업로드를 시뮬레이션합니다."""
    # Vite React 앱의 public 폴더 경로 탐색
    vite_public_dir = os.path.join(BASE_DIR, "dashboard", "public")
    if os.path.exists(vite_public_dir):
        mock_csv_path = os.path.join(vite_public_dir, "mock_google_sheet.csv")
    else:
        mock_csv_path = os.path.join(BASE_DIR, "mock_google_sheet.csv")
        
    log_message(f"[MOCK MODE] Simulating upload of {len(rows)} rows to CSV: {mock_csv_path}")
    
    file_exists = os.path.exists(mock_csv_path)
    
    try:
        import csv
        with open(mock_csv_path, "a", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            # 파일이 없으면 헤더 작성
            if not file_exists:
                writer.writerow(columns)
                log_message("[MOCK MODE] Written columns header to CSV.")
            
            # 데이터 작성
            for row in rows:
                formatted_row = ["" if val is None else val for val in row]
                writer.writerow(formatted_row)
        log_message(f"[MOCK MODE] Successfully simulated upload of {len(rows)} rows.")
        return True
    except Exception as e:
        log_message(f"[MOCK MODE] Simulation failed: {e}")
        return False

def main():
    # 실행 인자에 --mock이 있는지 확인
    is_mock = "--mock" in sys.argv
    
    log_message("Starting TOC DB Uploader...")
    if is_mock:
        log_message("[MOCK MODE] Running in simulation mode (No Google API connection required).")
    
    # 1. 마지막 업로드 시각 조회
    last_datetime = get_last_upload_time()
    log_message(f"Last upload datetime in config: {last_datetime or 'None (First Run)'}")
    
    # 2. SQLite DB에서 새 데이터 가져오기
    rows, columns = fetch_new_data(last_datetime)
    if not rows:
        log_message("No new data to upload. Process finished.")
        return
        
    log_message(f"Found {len(rows)} new rows to upload.")
    
    # 3. 구글 시트로 업로드 (또는 시뮬레이션 CSV 업로드)
    if is_mock:
        success = mock_upload_to_csv(rows, columns)
    else:
        success = upload_to_google_sheets(rows, columns)
    
    # 4. 성공 시 마지막 업로드 시각 기록
    if success:
        # 가져온 데이터 중 가장 최근(마지막 행)의 Date_Time을 구함
        # fetch_new_data에서 Date_Time ASC 정렬로 가져왔으므로 마지막 인덱스가 가장 최신임
        latest_row_time = rows[-1][0]
        save_last_upload_time(latest_row_time)
        log_message("Uploader completed successfully.")
    else:
        log_message("Uploader failed. Will retry on next schedule.")

if __name__ == "__main__":
    main()
