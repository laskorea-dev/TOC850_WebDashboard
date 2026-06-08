import os
import sys
import json
import sqlite3
import threading
import queue
import time
from datetime import datetime
import urllib.request
import urllib.parse

# GUI libraries
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# PyInstaller 패키징(.exe) 실행 여부에 따른 진짜 실행 폴더 경로 탐색
if getattr(sys, 'frozen', False):
    # .exe 파일이 위치한 실제 현장 작업 폴더 반환
    BASE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # 일반 .py 스크립트 가동 시
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
CONFIG_PATH = os.path.join(BASE_DIR, "uploader_config.json")
LOG_PATH = os.path.join(BASE_DIR, "uploader.log")

# 기본 상수 설정 (설정 파일에 없을 시의 대체값)
DEFAULT_INTERVAL_SECONDS = 900  # 15분
DEFAULT_DB_NAME = "toc_db.db"
DEFAULT_DB_PATH = os.path.join(BASE_DIR, DEFAULT_DB_NAME)
DEFAULT_SHEET_NAME = "TOC_Measure_Dashboard"
DEFAULT_DEVICE_ID = "Samyang_Incheon"
DEFAULT_TABLE_NAME = "Samyang_Incheon"
DEFAULT_SUPABASE_URL = "https://abfjmqnurtjfbflquqsp.supabase.co/rest/v1/"
DEFAULT_SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiZmptcW51cnRqZmJmbHF1cXNwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTg3MjM4OCwiZXhwIjoyMDk1NDQ4Mzg4fQ.ejErBBFUNYlzBBCM0rLi_1mx49tuXQY_XArRuQ5dG0c"

class GUIUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TOC B2B 다중 계측기 자동 업로더 v4.2 (Supabase)")
        self.root.geometry("660x700")
        self.root.resizable(False, False)
        
        # 스레드 안전 통신용 큐
        self.msg_queue = queue.Queue()
        
        # 1. 설정값 초기화 (기본값 우선 지정 후 Config 로드)
        self.db_path = DEFAULT_DB_PATH
        self.sheet_name = DEFAULT_SHEET_NAME
        self.supabase_table = DEFAULT_TABLE_NAME
        self.device_id = DEFAULT_DEVICE_ID
        self.interval_seconds = DEFAULT_INTERVAL_SECONDS
        self.last_upload_time = "None (First Run)"
        self.last_query = "N/A"
        self.is_paused = False
        self.is_mock = True  # 기본값 mock
        self.supabase_url = DEFAULT_SUPABASE_URL
        self.supabase_key = DEFAULT_SUPABASE_KEY
        
        # 설정 파일에서 사용자 설정값 로드
        self.load_config()
        
        # 카운트다운 타이머 잔여 시간 설정
        self.time_left = self.interval_seconds
        
        # UI 스타일 테마 & 색상 정의
        self.color_bg = "#0d0e12"
        self.color_card = "#161822"
        self.color_card_dark = "#0f1016"
        self.color_border = "#2a2c3a"
        self.color_cyan = "#00f2fe"
        self.color_purple = "#7f00ff"
        self.color_text_main = "#f0f2f5"
        self.color_text_muted = "#a0a5b5"
        self.color_green = "#10b981"
        self.color_orange = "#f59e0b"
        self.color_red = "#ef4444"
        
        self.root.configure(bg=self.color_bg)
        
        # UI 레이아웃 빌드
        self.build_ui()
        
        # 1초 주기 카운트다운 루프 시작
        self.start_timer_loop()
        
        # 백그라운드 스레드 메시지 수신 리스너 시작
        self.listen_queue()
        
        self.log_to_viewer("TOC B2B GUI Uploader가 기동되었습니다.")
        self.log_to_viewer(f"[설정 로드] 기기 식별자 ID: '{self.device_id}'")
        self.log_to_viewer(f"[설정 로드] 연동 주기: {self.interval_seconds // 60}분 ({self.interval_seconds}초)")
        
        if self.is_mock:
            self.log_to_viewer("[동작 모드] 시뮬레이션 모드(Mock Mode) 활성화 됨.")
            self.log_to_viewer("-> 데이터는 대시보드 퍼블릭 CSV 폴더에 기기 ID와 함께 실시간 파일로 누적됩니다.")
        else:
            self.log_to_viewer("[동작 모드] Supabase 클라우드 실시간 전송 활성화 됨.")
            self.log_to_viewer(f"-> 전송 대상 URL: '{self.supabase_url}' | 테이블: '{self.supabase_table}'")

        # 기동 후 자동 1회 즉시 동기화 (3초 후 실행하여 UI 안정화 대기)
        self.startup_sync_pending = True
        self.root.after(3000, self.trigger_sync_now)

    def load_config(self):
        """uploader_config.json 파일로부터 설정을 읽어옴 (손상 시 백업에서 자동 복구)"""
        config_loaded = False
        for path in [CONFIG_PATH, CONFIG_PATH + ".bak"]:
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.db_path = config.get("db_path", DEFAULT_DB_PATH)
                    self.sheet_name = config.get("google_sheet_name", DEFAULT_SHEET_NAME)
                    self.supabase_table = config.get("supabase_table", DEFAULT_TABLE_NAME)
                    self.device_id = config.get("device_id", DEFAULT_DEVICE_ID)
                    self.interval_seconds = int(config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
                    self.last_upload_time = config.get("last_datetime", "None (First Run)")
                    self.last_query = config.get("last_query", "N/A")
                    self.is_paused = config.get("is_paused", False)
                    self.supabase_url = config.get("supabase_url", DEFAULT_SUPABASE_URL)
                    self.supabase_key = config.get("supabase_key", DEFAULT_SUPABASE_KEY)
                    
                    config_mock = config.get("is_mock", True)
                    if self.supabase_url and self.supabase_key:
                        self.is_mock = config_mock
                    else:
                        self.is_mock = True
                        
                    if not os.path.exists(self.db_path) and os.path.exists(DEFAULT_DB_PATH):
                        self.db_path = DEFAULT_DB_PATH
                    config_loaded = True
                    if path != CONFIG_PATH:
                        print(f"[복구] 백업 설정 파일에서 복구 성공: {path}")
                    break
            except Exception as e:
                print(f"Config loading from {path} failed: {e}")
        if not config_loaded:
            self.save_config()

    def save_config(self):
        """현재 상태를 uploader_config.json에 안전하게 저장 (원자적 쓰기로 손상 방지)"""
        try:
            config_data = {
                "db_path": self.db_path,
                "google_sheet_name": self.sheet_name,
                "supabase_table": self.supabase_table,
                "device_id": self.device_id,
                "interval_seconds": self.interval_seconds,
                "last_datetime": self.last_upload_time,
                "last_query": self.last_query,
                "is_paused": self.is_paused,
                "is_mock": self.is_mock,
                "supabase_url": self.supabase_url,
                "supabase_key": self.supabase_key
            }
            # 안전한 원자적 파일 쓰기: 임시 파일에 먼저 완전히 기록 후 교체
            tmp_path = CONFIG_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            # 기존 파일을 백업으로 보존 후 교체
            bak_path = CONFIG_PATH + ".bak"
            if os.path.exists(CONFIG_PATH):
                try:
                    if os.path.exists(bak_path):
                        os.remove(bak_path)
                    os.rename(CONFIG_PATH, bak_path)
                except Exception:
                    pass
            os.rename(tmp_path, CONFIG_PATH)
        except Exception as e:
            print(f"Config saving failed: {e}")

    def build_ui(self):
        # 1. Header Frame (Title & Status Badge)
        header_frame = tk.Frame(self.root, bg=self.color_bg, pady=8, padx=20)
        header_frame.pack(fill=tk.X, padx=20)
        
        title_label = tk.Label(
            header_frame, 
            text="TOC B2B CLOUD UPLOADER (Supabase)", 
            font=("Outfit", 14, "bold"),
            fg=self.color_cyan, 
            bg=self.color_bg
        )
        title_label.pack(side=tk.LEFT)
        
        self.status_badge = tk.Label(
            header_frame,
            text=" 가동 중 (ACTIVE) ",
            font=("Helvetica", 9, "bold"),
            bg=self.color_green if not self.is_paused else self.color_orange,
            fg="#ffffff",
            padx=10,
            pady=4,
            relief=tk.FLAT
        )
        self.status_badge.pack(side=tk.RIGHT)

        # 구분선
        sep = tk.Frame(self.root, height=1, bg=self.color_border)
        sep.pack(fill=tk.X, padx=20)

        # 2. Config Frame (사용자 설정 관리 판넬)
        config_frame = tk.Frame(self.root, bg=self.color_card, bd=1, relief=tk.FLAT, pady=10)
        config_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # SQLite DB 경로 입력 및 탐색
        db_label = tk.Label(config_frame, text="연동 SQLite DB 파일 경로", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        db_label.grid(row=0, column=0, sticky=tk.W, padx=15, pady=(0, 2))
        
        self.db_path_var = tk.StringVar(value=self.db_path)
        db_entry = tk.Entry(config_frame, textvariable=self.db_path_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=1, relief=tk.SOLID, width=54)
        db_entry.grid(row=1, column=0, padx=(15, 10), pady=(0, 5), sticky=tk.W)
        
        btn_browse = tk.Button(config_frame, text="찾아보기...", font=("Helvetica", 8), bg=self.color_border, fg=self.color_text_main, activebackground=self.color_cyan, relief=tk.GROOVE, command=self.browse_db_file)
        btn_browse.grid(row=1, column=1, padx=(0, 15), pady=(0, 5), sticky=tk.W)
        
        # 계측기 장비 고유 ID (Device ID) 설정
        device_label = tk.Label(config_frame, text="계측 장비 고유 ID 식별자 (Device ID)", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        device_label.grid(row=2, column=0, sticky=tk.W, padx=15, pady=(0, 2))
        
        self.device_id_var = tk.StringVar(value=self.device_id)
        device_entry = tk.Entry(config_frame, textvariable=self.device_id_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=1, relief=tk.SOLID, width=54)
        device_entry.grid(row=3, column=0, padx=(15, 10), pady=(0, 5), sticky=tk.W)
        
        btn_save_device = tk.Button(config_frame, text="장비ID 저장", font=("Helvetica", 8), bg=self.color_border, fg=self.color_text_main, activebackground=self.color_cyan, relief=tk.GROOVE, command=self.update_device_id)
        btn_save_device.grid(row=3, column=1, padx=(0, 15), pady=(0, 5), sticky=tk.W)
        
        # Supabase Project URL 설정
        sub_url_label = tk.Label(config_frame, text="Supabase Project URL (https://xxxx.supabase.co)", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        sub_url_label.grid(row=4, column=0, sticky=tk.W, padx=15, pady=(0, 2))
        
        self.sub_url_var = tk.StringVar(value=self.supabase_url)
        sub_url_entry = tk.Entry(config_frame, textvariable=self.sub_url_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=1, relief=tk.SOLID, width=54)
        sub_url_entry.grid(row=5, column=0, padx=(15, 10), pady=(0, 5), sticky=tk.W)
        
        btn_save_url = tk.Button(config_frame, text="URL 저장", font=("Helvetica", 8), bg=self.color_border, fg=self.color_text_main, activebackground=self.color_cyan, relief=tk.GROOVE, command=self.update_supabase_url)
        btn_save_url.grid(row=5, column=1, padx=(0, 15), pady=(0, 5), sticky=tk.W)

        # [신규] Supabase Table Name 설정 (사용자가 생성한 테이블 스펠링 매핑 가능!)
        sub_table_label = tk.Label(config_frame, text="Supabase 테이블 이름 (Database Table Name)", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        sub_table_label.grid(row=6, column=0, sticky=tk.W, padx=15, pady=(0, 2))
        
        self.sub_table_var = tk.StringVar(value=self.supabase_table)
        sub_table_entry = tk.Entry(config_frame, textvariable=self.sub_table_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=1, relief=tk.SOLID, width=54)
        sub_table_entry.grid(row=7, column=0, padx=(15, 10), pady=(0, 5), sticky=tk.W)
        
        btn_save_table = tk.Button(config_frame, text="테이블 저장", font=("Helvetica", 8), bg=self.color_border, fg=self.color_text_main, activebackground=self.color_cyan, relief=tk.GROOVE, command=self.update_supabase_table)
        btn_save_table.grid(row=7, column=1, padx=(0, 15), pady=(0, 5), sticky=tk.W)

        # Supabase Anon Key 설정
        sub_key_label = tk.Label(config_frame, text="Supabase Anon API Key", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        sub_key_label.grid(row=8, column=0, sticky=tk.W, padx=15, pady=(0, 2))
        
        self.sub_key_var = tk.StringVar(value=self.supabase_key)
        sub_key_entry = tk.Entry(config_frame, textvariable=self.sub_key_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=1, relief=tk.SOLID, width=54)
        sub_key_entry.grid(row=9, column=0, padx=(15, 10), pady=(0, 5), sticky=tk.W)
        
        btn_save_key = tk.Button(config_frame, text="Key 저장", font=("Helvetica", 8), bg=self.color_border, fg=self.color_text_main, activebackground=self.color_cyan, relief=tk.GROOVE, command=self.update_supabase_key)
        btn_save_key.grid(row=9, column=1, padx=(0, 15), pady=(0, 5), sticky=tk.W)

        # B2B 연동 상태 안내 정보
        dest_label = tk.Label(config_frame, text="실시간 클라우드 DB 연결 타겟", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        dest_label.grid(row=10, column=0, sticky=tk.W, padx=15, pady=(2, 2))
        
        dest_desc = f"Supabase Cloud [Table: '{self.supabase_table}'] (ID: {self.device_id})" if not self.is_mock else f"Local Simulated CSV [dashboard/public/mock_google_sheet.csv] (ID: {self.device_id})"
        self.dest_info = tk.Label(config_frame, text=dest_desc, font=("Helvetica", 9, "bold"), fg=self.color_cyan if not self.is_mock else self.color_purple, bg=self.color_card)
        self.dest_info.grid(row=11, column=0, columnspan=2, sticky=tk.W, padx=15, pady=(0, 2))

        # 3. Status Monitor Frame (실시간 모니터링 판넬)
        monitor_frame = tk.Frame(self.root, bg=self.color_card, bd=1, relief=tk.FLAT, pady=10)
        monitor_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        # 타이머 카운트다운 표시기
        self.timer_label = tk.Label(
            monitor_frame, 
            text="다음 자동 동기화까지: 15분 00초 남음", 
            font=("Helvetica", 10, "bold"), 
            fg=self.color_cyan, 
            bg=self.color_card
        )
        self.timer_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, padx=15, pady=(0, 6))
        
        # 최근 업로드 시간
        self.last_upload_label = tk.Label(
            monitor_frame,
            text=f"최근 동기화 성공 일시:  {self.last_upload_time}",
            font=("Helvetica", 9),
            fg=self.color_text_main,
            bg=self.color_card
        )
        self.last_upload_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=15, pady=(0, 6))
        
        # 최근 전송 쿼리 표시창
        query_title = tk.Label(monitor_frame, text="최근 업로드 증분 쿼리", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        query_title.grid(row=2, column=0, sticky=tk.W, padx=15, pady=(2, 2))
        
        self.query_text = tk.Label(
            monitor_frame, 
            text=self.last_query, 
            font=("Consolas", 8), 
            fg=self.color_text_muted, 
            bg=self.color_card_dark,
            anchor="w",
            justify=tk.LEFT,
            padx=10,
            pady=4,
            relief=tk.SOLID,
            bd=1,
            width=78
        )
        self.query_text.grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=15, pady=(0, 2))

        # 4. Logger Frame (실시간 가동 로그)
        logger_frame = tk.Frame(self.root, bg=self.color_bg)
        logger_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        log_label = tk.Label(logger_frame, text="실시간 가동 로그", font=("Helvetica", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        log_label.pack(anchor=tk.W, pady=(0, 2))
        
        scrollbar = tk.Scrollbar(logger_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_viewer = tk.Text(
            logger_frame, 
            height=3, 
            bg=self.color_card_dark, 
            fg=self.color_text_main, 
            font=("Consolas", 9),
            bd=1,
            relief=tk.SOLID,
            yscrollcommand=scrollbar.set
        )
        self.log_viewer.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_viewer.yview)

        # 5. Buttons Control Frame (Bottom)
        btn_frame = tk.Frame(self.root, bg=self.color_bg)
        btn_frame.pack(fill=tk.X, padx=20, pady=(0, 15))
        
        self.btn_pause_text = tk.StringVar(value="일시정지 ⏸")
        self.btn_pause = tk.Button(
            btn_frame, 
            textvariable=self.btn_pause_text, 
            font=("Helvetica", 9, "bold"), 
            bg=self.color_orange, 
            fg="#ffffff", 
            relief=tk.GROOVE, 
            width=18,
            pady=6,
            command=self.toggle_pause
        )
        self.btn_pause.pack(side=tk.LEFT)
        self.update_status_badge()
        self.update_pause_button_style()
        
        btn_sync_now = tk.Button(
            btn_frame, 
            text="즉시 전송 ⚡", 
            font=("Helvetica", 9, "bold"), 
            bg=self.color_cyan, 
            fg=self.color_bg, 
            relief=tk.GROOVE, 
            width=18,
            pady=6,
            command=self.trigger_sync_now
        )
        btn_sync_now.pack(side=tk.RIGHT)

    def browse_db_file(self):
        """SQLite DB 파일 찾아보기 브라우저 기동"""
        initial_dir = os.path.dirname(self.db_path) if os.path.exists(self.db_path) else BASE_DIR
        file_path = filedialog.askopenfilename(
            title="연동할 SQLite Database (.db) 파일 선택",
            initialdir=initial_dir,
            filetypes=[("Database Files", "*.db"), ("All Files", "*.*")]
        )
        if file_path:
            self.db_path = file_path
            self.db_path_var.set(file_path)
            self.log_to_viewer(f"[설정 변경] 연동 DB 경로가 변경되었습니다: {file_path}")
            self.save_config()

    def update_device_id(self):
        """사용자가 입력한 장비 고유 ID(Device ID) 반영"""
        new_device_id = self.device_id_var.get().strip()
        if new_device_id:
            self.device_id = new_device_id
            self.log_to_viewer(f"[설정 변경] 계측 장비 ID 식별자가 변경되었습니다: '{new_device_id}'")
            self.refresh_destination_label()
            self.save_config()
            messagebox.showinfo("설정 완료", f"장비 고유 ID가 '{new_device_id}'로 정상 적용되었습니다.")
        else:
            messagebox.showerror("에러", "장비 ID는 빈칸으로 지정할 수 없습니다.")

    def update_supabase_url(self):
        """사용자가 입력한 Supabase URL 반영 및 MOCK 모드 분기 판단"""
        new_url = self.sub_url_var.get().strip()
        self.supabase_url = new_url
        self.log_to_viewer(f"[설정 변경] Supabase URL이 업데이트되었습니다: '{new_url}'")
        self.check_mock_status()
        self.refresh_destination_label()
        self.save_config()
        messagebox.showinfo("설정 완료", "Supabase Project URL이 성공적으로 저장되었습니다.")

    def update_supabase_table(self):
        """사용자가 입력한 Supabase 테이블 이름 반영"""
        new_table = self.sub_table_var.get().strip()
        if new_table:
            self.supabase_table = new_table
            self.log_to_viewer(f"[설정 변경] Supabase 테이블 이름이 업데이트되었습니다: '{new_table}'")
            self.refresh_destination_label()
            self.save_config()
            messagebox.showinfo("설정 완료", f"데이터베이스 테이블 이름이 '{new_table}'로 변경되었습니다.")
        else:
            messagebox.showerror("에러", "테이블 이름은 빈칸으로 지정할 수 없습니다.")

    def update_supabase_key(self):
        """사용자가 입력한 Supabase Key 반영 및 MOCK 모드 분기 판단"""
        new_key = self.sub_key_var.get().strip()
        self.supabase_key = new_key
        self.log_to_viewer("[설정 변경] Supabase Anon Key가 업데이트되었습니다.")
        self.check_mock_status()
        self.refresh_destination_label()
        self.save_config()
        messagebox.showinfo("설정 완료", "Supabase Anon API Key가 성공적으로 저장되었습니다.")

    def check_mock_status(self):
        """Supabase 접속 정보 충족 유무에 따라 실시간 런타임 전송 모드 토글"""
        if self.supabase_url and self.supabase_key:
            self.is_mock = False
            self.log_to_viewer("[알림] Supabase 연결 설정이 완료되어 실제 실시간 클라우드 모드로 전환되었습니다!")
        else:
            self.is_mock = True
            self.log_to_viewer("[알림] Supabase 설정이 비어있어 로컬 시뮬레이션(Mock) 모드로 대기합니다.")

    def refresh_destination_label(self):
        """GUI 상에 표시되는 목적지 안내 라벨 실시간 갱신"""
        dest_desc = f"Supabase Cloud [Table: '{self.supabase_table}'] (ID: {self.device_id})" if not self.is_mock else f"Local Simulated CSV [dashboard/public/mock_google_sheet.csv] (ID: {self.device_id})"
        self.dest_info.configure(text=dest_desc)

    def log_to_viewer(self, message):
        """UI 가동 로그 창에 실시간 정보 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        self.log_viewer.configure(state=tk.NORMAL)
        self.log_viewer.insert(tk.END, log_line)
        self.log_viewer.see(tk.END)
        self.log_viewer.configure(state=tk.DISABLED)
        
        # uploader.log 파일 백업 누적
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

    def update_status_badge(self):
        """가동 중 / 일시정지 배지 데코레이션 갱신"""
        if self.is_paused:
            self.status_badge.configure(
                text=" 일시정지 (PAUSED) ",
                bg=self.color_orange
            )
        else:
            self.status_badge.configure(
                text=" 가동 중 (ACTIVE) ",
                bg=self.color_green
            )

    def update_pause_button_style(self):
        """일시정지 버튼 토글 스타일 갱신"""
        if self.is_paused:
            self.btn_pause_text.set("업로드 재개 ▶")
            self.btn_pause.configure(bg=self.color_green)
        else:
            self.btn_pause_text.set("일시정지 ⏸")
            self.btn_pause.configure(bg=self.color_orange)

    def toggle_pause(self):
        """타이머 스케줄러 일시정지 및 복구"""
        self.is_paused = not self.is_paused
        self.update_status_badge()
        self.update_pause_button_style()
        self.save_config()
        
        if self.is_paused:
            self.log_to_viewer("자동 동기화 스케줄이 일시정지 되었습니다.")
        else:
            self.log_to_viewer("자동 동기화 스케줄이 다시 활성화되었습니다.")

    def trigger_sync_now(self):
        """즉시 수동 업로드 실행"""
        self.log_to_viewer("수동 즉시 전송 명령을 받았습니다. 업로드 엔진을 준비합니다...")
        self.run_upload_thread()
        self.time_left = self.interval_seconds

    def start_timer_loop(self):
        """1초 주기 백그라운드 스레드 안전 카운트다운 타이머"""
        def tick():
            if not self.is_paused:
                self.time_left -= 1
                
                minutes = self.time_left // 60
                seconds = self.time_left % 60
                self.timer_label.configure(
                    text=f"다음 자동 동기화까지: {minutes}분 {seconds:02d}초 남음"
                )
                
                if self.time_left <= 0:
                    self.log_to_viewer("자동 타이머 만료. 정기 동기화를 가동합니다...")
                    self.run_upload_thread()
                    self.time_left = self.interval_seconds
            else:
                self.timer_label.configure(
                    text="자동 동기화 일시정지 상태"
                )
            
            self.root.after(1000, tick)
        
        tick()

    # =========================================================================
    # MULTI-THREADING BACKGROUND ENGINE
    # =========================================================================
    def run_upload_thread(self):
        """백그라운드 스레드 기동"""
        # 중복 실행 방지
        for t in threading.enumerate():
            if t.name == "UploaderEngineThread":
                self.log_to_viewer("[주의] 현재 다른 데이터 전송 작업이 가동 중입니다. 잠시만 대기하십시오.")
                return
        
        worker = threading.Thread(
            target=self.uploader_worker_process, 
            name="UploaderEngineThread"
        )
        worker.daemon = True
        worker.start()

    def uploader_worker_process(self):
        """백그라운드 스레드 Worker 실제 동작"""
        self.msg_queue.put(("log", "SQLite 로컬 DB 검사 시작..."))
        
        if not os.path.exists(self.db_path):
            self.msg_queue.put(("log", f"[오류] DB 파일이 지정된 경로에 존재하지 않습니다: {self.db_path}"))
            self.msg_queue.put(("error", "DB 파일 실종"))
            return
            
        last_datetime = self.last_upload_time if self.last_upload_time != "None (First Run)" else None
        
        # 증분 쿼리 구문 조합
        if last_datetime:
            query = f"SELECT * FROM Measure_Result_With_Channel_Name WHERE Date_Time > '{last_datetime}' ORDER BY Date_Time ASC"
        else:
            query = "SELECT * FROM Measure_Result_With_Channel_Name ORDER BY Date_Time ASC"
            
        self.msg_queue.put(("query", query))

        # SQLite 데이터 추출
        conn = None
        rows = []
        columns = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='Measure_Result_With_Channel_Name'")
            if not cursor.fetchone():
                self.msg_queue.put(("log", "[오류] 지정된 DB 내에 'Measure_Result_With_Channel_Name' 뷰가 존재하지 않습니다."))
                return
                
            if last_datetime:
                cursor.execute(
                    "SELECT * FROM Measure_Result_With_Channel_Name WHERE Date_Time > ? ORDER BY Date_Time ASC",
                    (last_datetime,)
                )
            else:
                cursor.execute("SELECT * FROM Measure_Result_With_Channel_Name ORDER BY Date_Time ASC")
                
            rows = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
        except Exception as e:
            self.msg_queue.put(("log", f"[DB 에러] 쿼리 실행 실패: {e}"))
            return
        finally:
            if conn:
                conn.close()

        if not rows:
            self.msg_queue.put(("log", "동기화할 최신 측정값이 없습니다. 대기 모드로 진입합니다."))
            self.msg_queue.put(("success_empty", None))
            return

        self.msg_queue.put(("log", f"SQLite 뷰에서 신규 데이터 {len(rows)}건을 로드했습니다. B2B 패킹 가공을 시작합니다..."))

        # B2B 다중 기기 식별을 위해 데이터에 Device_ID 컬럼 삽입 가공
        processed_columns = list(columns)
        processed_columns.insert(1, 'Device_ID')
        
        processed_rows = []
        for row in rows:
            row_list = list(row)
            row_list.insert(1, self.device_id)
            processed_rows.append(row_list)

        # 3. 전송 처리 (Mock CSV 시뮬레이션 또는 실제 Supabase API)
        success = False
        if self.is_mock:
            success = self.process_mock_csv(processed_rows, processed_columns)
        else:
            success = self.process_real_supabase(processed_rows, processed_columns)
            
        if success:
            latest_time = rows[-1][0]
            self.msg_queue.put(("success", (latest_time, query)))
        else:
            self.msg_queue.put(("log", "[에러] 데이터 동기화 전송 중 실패가 발생했습니다."))

    def process_mock_csv(self, rows, columns):
        """Vite React 웹 대시보드가 로드할 수 있게 public 폴더에 CSV 로컬 동기화"""
        vite_public_dir = os.path.join(BASE_DIR, "dashboard", "public")
        if os.path.exists(vite_public_dir):
            mock_csv_path = os.path.join(vite_public_dir, "mock_google_sheet.csv")
        else:
            mock_csv_path = os.path.join(BASE_DIR, "mock_google_sheet.csv")
            
        file_exists = os.path.exists(mock_csv_path)
        
        try:
            time.sleep(1.0)
            import csv
            with open(mock_csv_path, "a", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(columns)
                for row in rows:
                    formatted_row = ["" if val is None else val for val in row]
                    writer.writerow(formatted_row)
            self.msg_queue.put(("log", f"[B2B CSV 동기화 완료] 장비ID: '{self.device_id}' 데이터 {len(rows)}개를 로컬 CSV에 수록했습니다."))
            return True
        except Exception as e:
            self.msg_queue.put(("log", f"[CSV 쓰기 실패] 에러: {e}"))
            return False

    def process_real_supabase(self, rows, columns):
        """파이썬 기본 urllib 패키지만을 사용하여 추가 패키지 설치 없이 Supabase PostgreSQL REST API로 초고속 전송!"""
        self.msg_queue.put(("log", "Supabase HTTPS API 호출 연결 시도 중..."))
        
        # 행 데이터를 컬럼명에 맞추어 JSON 딕셔너리 구조 리스트로 파싱
        json_payload = []
        for row in rows:
            record = {}
            for idx, col_name in enumerate(columns):
                val = row[idx]
                if col_name in ['Channel', 'MAXR']:
                    record[col_name] = int(val) if val is not None else 0
                elif col_name in ['TOC_Conc', 'DilutionFactor', 'MSIG', 'SLOP', 'ICPT', 'FACT', 'OFST']:
                    record[col_name] = float(val) if val is not None else 0.0
                else:
                    record[col_name] = str(val) if val is not None else ""
            json_payload.append(record)

        try:
            # 사용자가 복사한 URL 끝에 /rest/v1/이 포함되었거나 생략되었을 때 자동 보정
            base_url = self.supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                req_url = f"{base_url}/{self.supabase_table}"
            else:
                req_url = f"{base_url}/rest/v1/{self.supabase_table}"
                
            data_bytes = json.dumps(json_payload).encode('utf-8')
            
            req = urllib.request.Request(
                req_url,
                data=data_bytes,
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal, resolution=ignore-duplicates"
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req, timeout=8) as response:
                status = response.status
                if status in [200, 201, 204]:
                    self.msg_queue.put(("log", f"[Supabase 전송 대성공!] 기기 ID '{self.device_id}' 신규 데이터 {len(rows)}건이 실시간 PostgreSQL 클라우드에 적재 완료되었습니다!"))
                    return True
                else:
                    self.msg_queue.put(("log", f"[Supabase 전송 실패] 서버 상태 코드: {status}"))
                    return False
        except Exception as e:
            self.msg_queue.put(("log", f"[Supabase API 연결 오류] 호스트 연결 실패: {e}"))
            return False

    # =========================================================================
    # QUEUE MESSAGE LISTENER (UI Thread)
    # =========================================================================
    def listen_queue(self):
        try:
            while True:
                msg_type, content = self.msg_queue.get_nowait()
                
                if msg_type == "log":
                    self.log_to_viewer(content)
                elif msg_type == "query":
                    self.last_query = content
                    self.query_text.configure(text=content)
                elif msg_type == "success":
                    latest_time, query = content
                    self.last_upload_time = latest_time
                    self.last_query = query
                    self.last_upload_label.configure(
                        text=f"최근 동기화 성공 일시:  {latest_time}"
                    )
                    self.log_to_viewer(f"데이터 동기화 완료! 장비 ID: {self.device_id} | 최신 측정 시간: {latest_time}")
                    self.save_config()
                    self._auto_minimize_if_startup()
                elif msg_type == "success_empty":
                    self.save_config()
                    self._auto_minimize_if_startup()
                elif msg_type == "error":
                    self.log_to_viewer(f"[경고] 백그라운드 엔진 경보: {content}")
                    
                self.msg_queue.task_done()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.listen_queue)

    def _auto_minimize_if_startup(self):
        """기동 후 첫 동기화 성공 시 자동 최소화하여 메인 프로그램이 전면에 표시되도록 함"""
        if self.startup_sync_pending:
            self.startup_sync_pending = False
            self.log_to_viewer("[자동 최소화] 초기 동기화 확인 완료. 프로그램을 최소화합니다.")
            self.root.after(2000, self.root.iconify)

def main():
    root = tk.Tk()
    style = ttk.Style()
    style.theme_use('clam')
    app = GUIUploaderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
