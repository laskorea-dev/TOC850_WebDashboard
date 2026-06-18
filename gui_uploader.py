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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


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
DEFAULT_DEVICE_ID = "DEVICE_01"
DEFAULT_TABLE_NAME = "measure_logs"

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
        self.last_alert_time = {}
        self.check_config_timer = 0
        self.is_mock = True  # 기본값 mock
        self.supabase_url = ""
        self.supabase_key = ""
        
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
        """uploader_config.json 파일로부터 설정을 읽어옴 (읽기 전용 - 파일에 쓰기 없음)"""
        if not os.path.exists(CONFIG_PATH):
            print(f"[경고] 설정 파일이 없습니다: {CONFIG_PATH}")
            return
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.db_path = config.get("db_path", DEFAULT_DB_PATH)
                self.sheet_name = config.get("google_sheet_name", DEFAULT_SHEET_NAME)
                self.supabase_table = config.get("supabase_table", DEFAULT_TABLE_NAME)
                self.device_id = config.get("device_id", DEFAULT_DEVICE_ID)
                self.interval_seconds = int(config.get("interval_seconds", DEFAULT_INTERVAL_SECONDS))
                self.last_query = config.get("last_query", "N/A")
                self.supabase_url = config.get("supabase_url", "")
                self.supabase_key = config.get("supabase_key", "")
                
                # SMTP email configuration
                self.smtp_server = config.get("smtp_server", "")
                self.smtp_port = int(config.get("smtp_port", 587))
                self.smtp_user = config.get("smtp_user", "")
                self.smtp_password = config.get("smtp_password", "")
                self.smtp_use_tls = config.get("smtp_use_tls", True)
                
                config_mock = config.get("is_mock", True)
                if self.supabase_url and self.supabase_key:
                    self.is_mock = config_mock
                else:
                    self.is_mock = True
                    
                if not os.path.exists(self.db_path) and os.path.exists(DEFAULT_DB_PATH):
                    self.db_path = DEFAULT_DB_PATH
        except Exception as e:
            print(f"Config loading failed: {e}")

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

    def update_device_id(self):
        """사용자가 입력한 장비 고유 ID(Device ID) 반영"""
        new_device_id = self.device_id_var.get().strip()
        if new_device_id:
            self.device_id = new_device_id
            self.log_to_viewer(f"[설정 변경] 계측 장비 ID 식별자가 변경되었습니다: '{new_device_id}'")
            self.refresh_destination_label()
            messagebox.showinfo("설정 적용", f"장비 고유 ID가 '{new_device_id}'로 이번 세션에 적용되었습니다.")
        else:
            messagebox.showerror("에러", "장비 ID는 빈칸으로 지정할 수 없습니다.")

    def update_supabase_url(self):
        """사용자가 입력한 Supabase URL 반영 및 MOCK 모드 분기 판단"""
        new_url = self.sub_url_var.get().strip()
        self.supabase_url = new_url
        self.log_to_viewer(f"[설정 변경] Supabase URL이 업데이트되었습니다: '{new_url}'")
        self.check_mock_status()
        self.refresh_destination_label()
        messagebox.showinfo("설정 적용", "Supabase Project URL이 이번 세션에 적용되었습니다.")

    def update_supabase_table(self):
        """사용자가 입력한 Supabase 테이블 이름 반영"""
        new_table = self.sub_table_var.get().strip()
        if new_table:
            self.supabase_table = new_table
            self.log_to_viewer(f"[설정 변경] Supabase 테이블 이름이 업데이트되었습니다: '{new_table}'")
            self.refresh_destination_label()
            messagebox.showinfo("설정 적용", f"테이블 이름이 '{new_table}'로 이번 세션에 적용되었습니다.")
        else:
            messagebox.showerror("에러", "테이블 이름은 빈칸으로 지정할 수 없습니다.")

    def update_supabase_key(self):
        """사용자가 입력한 Supabase Key 반영 및 MOCK 모드 분기 판단"""
        new_key = self.sub_key_var.get().strip()
        self.supabase_key = new_key
        self.log_to_viewer("[설정 변경] Supabase Anon Key가 업데이트되었습니다.")
        self.check_mock_status()
        self.refresh_destination_label()
        messagebox.showinfo("설정 적용", "Supabase Anon API Key가 이번 세션에 적용되었습니다.")

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
            
            # 10초마다 Supabase 설정에서 원격 테스트 메일 트리거 감지
            self.check_config_timer += 1
            if self.check_config_timer >= 10:
                self.check_config_timer = 0
                if self.supabase_url and self.supabase_key and not self.is_mock:
                    threading.Thread(target=self.bg_check_test_email_trigger, daemon=True).start()

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

    def query_server_latest_datetime(self):
        """백그라운드 스레드에서 호출: Supabase 서버의 가장 최신 Date_Time을 조회"""
        try:
            base_url = self.supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                req_url = f"{base_url}/{self.supabase_table}"
            else:
                req_url = f"{base_url}/rest/v1/{self.supabase_table}"
            
            req_url += "?select=Date_Time&order=Date_Time.desc&limit=1"
            
            req = urllib.request.Request(
                req_url,
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json"
                },
                method="GET"
            )
            
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
                if data and len(data) > 0:
                    return data[0]["Date_Time"]
                return None
        except Exception as e:
            self.msg_queue.put(("log", f"[서버 조회 오류] 최신 데이터 시각 확인 실패: {e}"))
            return None

    def uploader_worker_process(self):
        """백그라운드 스레드 Worker 실제 동작"""
        self.msg_queue.put(("log", "SQLite 로컬 DB 검사 시작..."))
        
        if not os.path.exists(self.db_path):
            self.msg_queue.put(("log", f"[오류] DB 파일이 지정된 경로에 존재하지 않습니다: {self.db_path}"))
            self.msg_queue.put(("error", "DB 파일 실종"))
            return
        
        # Supabase 서버에서 가장 최신 업로드 시각을 직접 조회하여 증분 기준점 확인
        if not self.is_mock:
            self.msg_queue.put(("log", "서버 최신 데이터 시각 조회 중..."))
            last_datetime = self.query_server_latest_datetime()
            if last_datetime:
                self.msg_queue.put(("log", f"서버 최신 데이터: {last_datetime}"))
            else:
                self.msg_queue.put(("log", "서버에 기존 데이터가 없습니다. 전체 데이터를 전송합니다."))
        else:
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
                    # 실시간 경고 검사 및 메일 전송
                    try:
                        self.check_and_send_alerts(json_payload)
                    except Exception as ex:
                        self.msg_queue.put(("log", f"[알림 이메일 검사 오류] {ex}"))
                    return True
                else:
                    self.msg_queue.put(("log", f"[Supabase 전송 실패] 서버 상태 코드: {status}"))
                    return False
        except Exception as e:
            self.msg_queue.put(("log", f"[Supabase API 연결 오류] 호스트 연결 실패: {e}"))
            return False

    def fetch_site_config(self):
        """Supabase에서 사이트 설정(임계값 및 이메일 수신 목록)을 실시간으로 가져옵니다."""
        try:
            base_url = self.supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                config_url = f"{base_url}/850_dashboard_site_config?site_id=eq.{self.device_id}"
            else:
                config_url = f"{base_url}/rest/v1/850_dashboard_site_config?site_id=eq.{self.device_id}"
                
            req = urllib.request.Request(
                config_url,
                headers={
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}"
                },
                method="GET"
            )
            
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_data = json.loads(response.read().decode('utf-8'))
                    if isinstance(res_data, list) and len(res_data) > 0:
                        return res_data[0]
        except Exception as e:
            self.msg_queue.put(("log", f"[설정 정보 로드 실패] 오류: {e}"))
        return None

    def send_alert_email(self, recipients, subject, body):
        """SMTP 서버를 사용하여 지정된 수신인들에게 이메일을 발송합니다."""
        if not recipients:
            self.msg_queue.put(("log", "[메일 발송 스킵] 수신인 주소가 없습니다."))
            return False
        
        # uploader_config에 SMTP 설정이 제공되었는지 확인
        smtp_server = getattr(self, "smtp_server", "")
        smtp_port = getattr(self, "smtp_port", 587)
        smtp_user = getattr(self, "smtp_user", "")
        smtp_password = getattr(self, "smtp_password", "")
        smtp_use_tls = getattr(self, "smtp_use_tls", True)
        
        if not smtp_server or not smtp_user or not smtp_password:
            self.msg_queue.put(("log", "[메일 발송 실패] uploader_config.json에 SMTP 설정이 올바르지 않습니다."))
            return False

        try:
            # 이메일 메시지 구성
            msg = MIMEMultipart()
            msg["From"] = smtp_user
            msg["To"] = recipients
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "html", "utf-8"))

            # SMTP 서버 연결
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            if smtp_use_tls:
                server.starttls()
            
            server.login(smtp_user, smtp_password)
            
            # 수신인 주소 분리 (쉼표 구분 대응)
            recipient_list = [r.strip() for r in recipients.split(",") if r.strip()]
            
            server.sendmail(smtp_user, recipient_list, msg.as_string())
            server.quit()
            
            self.msg_queue.put(("log", f"[메일 발송 성공] 수신자: {recipients}"))
            return True
        except Exception as e:
            self.msg_queue.put(("log", f"[메일 발송 실패] 오류: {e}"))
            return False

    def check_and_send_alerts(self, records):
        """새로 수집된 레코드들의 TOC 수치가 경고 임계값을 초과하는지 검사하고 이메일을 발송합니다."""
        # 1. 사이트 설정 로드 (임계값 및 이메일 수신 목록)
        config_data = self.fetch_site_config()
        
        toc_alert_high = {}
        alert_emails = ""
        site_name = self.device_id
        
        if config_data:
            site_name = config_data.get("site_name", self.device_id)
            alert_json = config_data.get("toc_alert_high")
            if isinstance(alert_json, str):
                try:
                    alert_json = json.loads(alert_json)
                except Exception:
                    pass
            if isinstance(alert_json, dict):
                toc_alert_high = alert_json
                alert_emails = alert_json.get("alert_emails", "")

        # 수신 이메일이 설정되어 있지 않으면 알림 검사 생략
        if not alert_emails:
            # self.msg_queue.put(("log", "[경고 알림] 웹 설정에 수신인 메일 주소가 등록되어 있지 않아 검사를 생략합니다."))
            return

        now_time = datetime.now()

        for rec in records:
            channel_id = str(rec.get("Channel", ""))
            channel_name = rec.get("Channel_Name", f"채널 {channel_id}")
            toc_val = rec.get("TOC_Conc", 0.0)
            date_time = rec.get("Date_Time", "")

            # 2. 임계값(경고치) 확인
            warning_limit = 6000.0

            # 채널별 요구사항 기반 초기값(폴백) 설정
            if channel_id == "3":  # 방류수
                warning_limit = 50.0
            elif channel_id == "2":  # 1차처리수 (고농도조 유력)
                warning_limit = 1000.0
            elif channel_id == "1":  # 유입수 (원수조 유력)
                warning_limit = 2000.0

            # DB 로드 값 적용
            ch_config = toc_alert_high.get(channel_id)
            if ch_config:
                if isinstance(ch_config, dict):
                    warning_limit = float(ch_config.get("warning", warning_limit))
                else:
                    # 구버전 단일 숫자 형태 대응
                    try:
                        warning_limit = float(ch_config)
                    except ValueError:
                        pass

            # 3. 경고 수치 초과 여부 확인
            if toc_val >= warning_limit:
                # 4. 이메일 쿨다운(1시간) 확인
                last_time = self.last_alert_time.get(channel_id)
                if last_time and (now_time - last_time).total_seconds() < 3600:
                    continue  # 쿨다운 미경과 시 전송 생략

                # 이메일 제목 및 본문 작성
                subject = f"[TOC 경고 알림] {site_name} - {channel_name} 경고 수치 초과 ({toc_val} ppm)"
                body = f"""
                <html>
                <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                        <div style="background-color: #ef4444; color: white; padding: 20px; text-align: center;">
                            <h2 style="margin: 0; font-size: 1.5rem;">🚨 TOC-850 경고 초과 알림</h2>
                        </div>
                        <div style="padding: 24px; background-color: #fff;">
                            <p style="font-size: 0.95rem; font-weight: bold; color: #ef4444;">
                                계측 수치가 설정된 경고 임계값을 초과하였습니다. 즉각적인 확인이 필요합니다.
                            </p>
                            <table style="width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 0.9rem;">
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold; width: 30%;">모니터링 사이트</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{site_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">계측 채널</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{channel_name} (Ch {channel_id})</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">측정 시간</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{date_time}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold; color: #ef4444;">현재 측정값</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold; color: #ef4444; font-size: 1.1rem;">{toc_val} ppm</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">경고 설정치</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{warning_limit} ppm</td>
                                </tr>
                            </table>
                            <p style="margin-top: 24px; font-size: 0.82rem; color: #64748b;">
                                * 본 메일은 경고 발생 시 1시간 간격으로 쿨다운 제한이 걸려 발송됩니다.<br/>
                                * 임계값 및 이메일 수신 주소는 대시보드 웹설정 창에서 언제든지 조정 가능합니다.
                            </p>
                        </div>
                        <div style="background-color: #f8fafc; padding: 16px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 0.8rem; color: #94a3b8;">
                            LAS KOREA 온라인 계측 모니터링 시스템
                        </div>
                    </div>
                </body>
                </html>
                """
                
                # 메일 전송 실행
                success = self.send_alert_email(alert_emails, subject, body)
                if success:
                    # 메일 전송 성공 시 쿨다운 타임 업데이트
                    self.last_alert_time[channel_id] = now_time

    def bg_check_test_email_trigger(self):
        """Supabase 설정을 GET 하여 trigger_test_email 플래그가 참인지 확인하고, 참이면 메일을 발송한 뒤 플래그를 내립니다."""
        config_data = self.fetch_site_config()
        if not config_data:
            return
            
        toc_alert_high = config_data.get("toc_alert_high")
        if isinstance(toc_alert_high, str):
            try:
                toc_alert_high = json.loads(toc_alert_high)
            except Exception:
                pass
                
        if not isinstance(toc_alert_high, dict):
            return
            
        trigger = toc_alert_high.get("trigger_test_email", False)
        if trigger:
            self.msg_queue.put(("log", "[알림 메일 테스트] 웹으로부터 테스트 메일 발송 신호를 감지했습니다!"))
            alert_emails = toc_alert_high.get("alert_emails", "")
            
            if not alert_emails:
                self.msg_queue.put(("log", "[알림 메일 테스트 실패] 수신인 이메일 주소가 비어있습니다."))
            else:
                site_name = config_data.get("site_name", self.device_id)
                subject = f"[TOC 모의 테스트 메일] {site_name} 알림 발송 검증"
                body = f"""
                <html>
                <body style="font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; color: #333;">
                    <div style="max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
                        <div style="background-color: #3b82f6; color: white; padding: 20px; text-align: center;">
                            <h2 style="margin: 0; font-size: 1.5rem;">✉️ TOC 이메일 연동 테스트 성공</h2>
                        </div>
                        <div style="padding: 24px; background-color: #fff;">
                            <p style="font-size: 0.95rem; font-weight: bold; color: #3b82f6;">
                                웹 설정 화면에서 요청하신 이메일 즉시 발송 검증이 완료되었습니다!
                            </p>
                            <p>이 이메일이 수신함에 정상 도착했다면, <b>계측기 로컬 SMTP 메일 서버와 Supabase 클라우드 간의 연동이 완벽하게 완료</b>된 것입니다.</p>
                            <table style="width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 0.9rem;">
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold; width: 30%;">테스트 사이트</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{site_name}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">발신 계정 (SMTP)</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{self.smtp_user} ({self.smtp_server})</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">수신인 목록</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{alert_emails}</td>
                                </tr>
                                <tr>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9; font-weight: bold;">테스트 시간</td>
                                    <td style="padding: 8px; border-bottom: 1px solid #f1f5f9;">{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</td>
                                </tr>
                            </table>
                            <p style="margin-top: 24px; font-size: 0.82rem; color: #64748b;">
                                * 향후 계측 데이터의 TOC 농도가 경고 설정값을 초과하는 위급 상황이 발생하면 본 수신처 목록으로 긴급 알림 메일이 즉시 자동 전송됩니다.
                            </p>
                        </div>
                        <div style="background-color: #f8fafc; padding: 16px; text-align: center; border-top: 1px solid #e2e8f0; font-size: 0.8rem; color: #94a3b8;">
                            LAS KOREA 온라인 계측 모니터링 시스템
                        </div>
                    </div>
                </body>
                </html>
                """
                # 메일 쏘기
                self.send_alert_email(alert_emails, subject, body)
                
            # 메일 발송 후 DB 플래그 원상 복구 (trigger_test_email: False)
            try:
                toc_alert_high["trigger_test_email"] = False
                base_url = self.supabase_url.rstrip('/')
                if "/rest/v1" in base_url:
                    config_url = f"{base_url}/850_dashboard_site_config?site_id=eq.{self.device_id}"
                else:
                    config_url = f"{base_url}/rest/v1/850_dashboard_site_config?site_id=eq.{self.device_id}"
                    
                req = urllib.request.Request(
                    config_url,
                    data=json.dumps({"toc_alert_high": toc_alert_high}).encode('utf-8'),
                    headers={
                        "apikey": self.supabase_key,
                        "Authorization": f"Bearer {self.supabase_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal"
                    },
                    method="PATCH"
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in [200, 201, 204]:
                        self.msg_queue.put(("log", "[알림 메일 테스트 완료] 웹의 테스트 발송 신호 플래그가 비활성화되었습니다."))
            except Exception as patch_ex:
                self.msg_queue.put(("log", f"[테스트 플래그 초기화 실패] 오류: {patch_ex}"))

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
                    self._auto_minimize_if_startup()
                elif msg_type == "success_empty":
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
