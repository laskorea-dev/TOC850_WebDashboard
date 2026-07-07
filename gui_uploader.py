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
from alerts import get_alert_sender


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
DEFAULT_TABLE_NAME = "measure_logs_v2"

class GUIUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TOC B2B 다중 계측기 자동 업로더 v5.0 (Supabase V2)")
        self.root.geometry("660x700")
        self.root.resizable(False, False)
        
        # 스레드 안전 통신용 큐
        self.msg_queue = queue.Queue()
        
        # 1. 설정값 초기화 (기본값 우선 지정 후 Config 로드)
        self.db_path = DEFAULT_DB_PATH
        self.sheet_name = DEFAULT_SHEET_NAME
        self.supabase_table = DEFAULT_TABLE_NAME
        self.device_id = DEFAULT_DEVICE_ID
        self.site_id = "auto"
        self.interval_seconds = DEFAULT_INTERVAL_SECONDS
        self.last_upload_time = "None (First Run)"
        self.last_query = "N/A"
        self.is_paused = False
        self.last_alert_time = {}
        self.check_config_timer = 0
        self.is_mock = True  # 기본값 mock
        self.supabase_url = ""
        self.supabase_key = ""
        self.telegram_bot_token = ""
        
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

    def get_unique_device_id(self):
        """PC의 Windows 컴퓨터 이름(Hostname)을 기반으로 기기 ID를 결정합니다."""
        try:
            import socket
            hostname = socket.gethostname()
            # 파일명이나 URL 파라미터로 안전하게 사용하기 위해 공백 제거 및 특수문자 정제
            safe_hostname = "".join(c for c in hostname if c.isalnum() or c in "-_").strip()
            if safe_hostname:
                return safe_hostname
            return "WIN_PC"
        except Exception as e:
            print(f"[컴퓨터 이름 조회 실패] {e}")
            return "WIN_PC_UNKNOWN"

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
                
                # site_id 와 device_id 분리 로드 (하위 호환성)
                site_id_raw = config.get("site_id", config.get("device_id", ""))
                if not site_id_raw or site_id_raw.strip() == "" or site_id_raw.lower() == "auto":
                    self.site_id = self.get_unique_device_id()
                else:
                    self.site_id = site_id_raw.strip()
                
                # site_name 로드
                self.site_name = config.get("site_name", "")
                if not self.site_name or self.site_name.strip() == "":
                    self.site_name = self.site_id

                # device_id는 항상 물리 PC 호스트네임 자동 획득
                self.device_id = self.get_unique_device_id()
                
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
                
                # Telegram bot configuration
                self.telegram_bot_token = config.get("telegram_bot_token", "")
                
                # Alert Sender Initialization
                self.alert_type = config.get("alert_type", "email")
                self.alert_sender = get_alert_sender(
                    self.alert_type,
                    smtp_server=self.smtp_server,
                    smtp_port=self.smtp_port,
                    smtp_user=self.smtp_user,
                    smtp_password=self.smtp_password,
                    smtp_use_tls=self.smtp_use_tls,
                    telegram_bot_token=self.telegram_bot_token,
                    log_queue=self.msg_queue
                )
                
                self.is_paused = config.get("is_paused", False)
                config_mock = config.get("is_mock", True)
                if self.supabase_url and self.supabase_key:
                    self.is_mock = config_mock
                else:
                    self.is_mock = True
                    
                if not os.path.exists(self.db_path) and os.path.exists(DEFAULT_DB_PATH):
                    self.db_path = DEFAULT_DB_PATH
        except Exception as e:
            print(f"Config loading failed: {e}")

    def bind_hover(self, widget, hover_bg, normal_bg):
        """마우스 호버 시 버튼 배경색 변경 애니메이션 바인딩"""
        widget.bind("<Enter>", lambda e: widget.config(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.config(bg=normal_bg))

    def get_dest_desc(self):
        """현재 업로드 목적지 요약 텍스트 반환"""
        return f"Supabase: {self.supabase_table}" if not self.is_mock else "로컬 모의 적재 (Mock Mode)"

    def build_ui(self):
        """새로운 B2B 컨셉에 맞춘 프리미엄 다크-블루 모던 GUI 빌드"""
        # 색상 세트 정의
        self.color_bg = "#0B0F19"       # 미래지향적 깊은 밤색
        self.color_card = "#111827"     # Slate-900 카드배경
        self.color_card_dark = "#030712" # 초고해상도 다크인풋배경
        self.color_border = "#1F2937"   # Gray-800 경계선
        self.color_cyan = "#06B6D4"     # Cyan-500 메인 포인트
        self.color_purple = "#8B5CF6"   # Violet-500 서브 포인트
        self.color_text_main = "#F3F4F6" # Gray-100 기본 텍스트
        self.color_text_muted = "#9CA3AF" # Gray-400 보조 텍스트
        self.color_green = "#10B981"    # Emerald-500 가동 상태
        self.color_orange = "#F59E0B"   # Amber-500 정지 상태
        self.color_red = "#EF4444"      # Red-500 오류

        self.root.configure(bg=self.color_bg)

        # Tkinter StringVars로 설정값 필드 매핑
        self.db_path_var = tk.StringVar(value=self.db_path)
        self.device_id_var = tk.StringVar(value=self.device_id)
        self.site_name_var = tk.StringVar(value=self.site_name)
        self.interval_var = tk.StringVar(value=str(self.interval_seconds // 60))
        self.start_active_var = tk.BooleanVar(value=not self.is_paused)
        self.sub_url_var = tk.StringVar(value=self.supabase_url)
        self.sub_table_var = tk.StringVar(value=self.supabase_table)
        self.sub_key_var = tk.StringVar(value=self.supabase_key)
        self.alert_type_var = tk.StringVar(value=self.alert_type)
        self.tg_token_var = tk.StringVar(value=self.telegram_bot_token)
        self.smtp_server_var = tk.StringVar(value=self.smtp_server)
        self.smtp_port_var = tk.StringVar(value=str(self.smtp_port))
        self.smtp_user_var = tk.StringVar(value=self.smtp_user)
        self.smtp_pw_var = tk.StringVar(value=self.smtp_password)
        self.smtp_tls_var = tk.BooleanVar(value=self.smtp_use_tls)

        # 1. Header Frame (고유 로고/Badge 대체 및 호스트네임)
        header_frame = tk.Frame(self.root, bg=self.color_bg, pady=12, padx=20)
        header_frame.pack(fill=tk.X, padx=10)
        
        # 가동 상태 캔버스 원형 인디케이터 (글로우 효과 연출)
        self.status_canvas = tk.Canvas(header_frame, width=20, height=20, bg=self.color_bg, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_circle = self.status_canvas.create_oval(2, 2, 18, 18, fill=self.color_green, outline="")
        
        title_label = tk.Label(
            header_frame, 
            text="TOC-850 B2B SYNC CLIENT", 
            font=("Segoe UI", 12, "bold"),
            fg=self.color_cyan, 
            bg=self.color_bg
        )
        title_label.pack(side=tk.LEFT)
        
        self.status_label = tk.Label(
            header_frame,
            text="가동 중 (ACTIVE)",
            font=("Segoe UI", 9, "bold"),
            fg=self.color_green,
            bg=self.color_bg
        )
        self.status_label.pack(side=tk.LEFT, padx=(8, 0))
        
        self.device_info_label = tk.Label(
            header_frame,
            text=f"PC: {self.device_id}",
            font=("Consolas", 9),
            fg=self.color_text_muted,
            bg=self.color_bg
        )
        self.device_info_label.pack(side=tk.RIGHT)

        # 얇은 구분 띠
        sep = tk.Frame(self.root, height=1, bg=self.color_border)
        sep.pack(fill=tk.X, padx=20, pady=(0, 10))

        # 2. Stats Card Frame (가동 대시보드 인포메이션)
        stats_frame = tk.Frame(self.root, bg=self.color_card, bd=0, highlightthickness=1, highlightbackground=self.color_border, pady=12, padx=15)
        stats_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        stats_frame.columnconfigure(0, weight=1)
        stats_frame.columnconfigure(1, weight=1)
        
        site_title = tk.Label(stats_frame, text="사이트 이름 (Site Name)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        site_title.grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self.site_val_label = tk.Label(stats_frame, text=self.site_name, font=("Segoe UI", 11, "bold"), fg=self.color_text_main, bg=self.color_card)
        self.site_val_label.grid(row=1, column=0, sticky=tk.W, pady=(0, 8))
        
        timer_title = tk.Label(stats_frame, text="다음 자동 동기화 카운트다운", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        timer_title.grid(row=0, column=1, sticky=tk.W, pady=(0, 2))
        self.timer_val_label = tk.Label(stats_frame, text="15분 00초 남음", font=("Segoe UI", 11, "bold"), fg=self.color_cyan, bg=self.color_card)
        self.timer_val_label.grid(row=1, column=1, sticky=tk.W, pady=(0, 8))
        
        last_success_title = tk.Label(stats_frame, text="최근 동기화 완료 시각", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        last_success_title.grid(row=2, column=0, sticky=tk.W, pady=(0, 2))
        self.last_success_val_label = tk.Label(stats_frame, text=self.last_upload_time, font=("Consolas", 10), fg=self.color_text_main, bg=self.color_card)
        self.last_success_val_label.grid(row=3, column=0, sticky=tk.W)

        dest_title = tk.Label(stats_frame, text="동기화 목적지 정보", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_card)
        dest_title.grid(row=2, column=1, sticky=tk.W, pady=(0, 2))
        self.dest_val_label = tk.Label(stats_frame, text=self.get_dest_desc(), font=("Segoe UI", 9, "bold"), fg=self.color_cyan if not self.is_mock else self.color_purple, bg=self.color_card, justify=tk.LEFT)
        self.dest_val_label.grid(row=3, column=1, sticky=tk.W)

        # 3. Settings LabelFrame (동기화 설정 영역)
        self.settings_frame = tk.LabelFrame(self.root, text=" ⚙️ 동기화 및 알림 설정 ", font=("Segoe UI", 9, "bold"), bg=self.color_bg, fg=self.color_cyan, bd=1, relief=tk.SOLID, padx=15, pady=10)
        self.settings_frame.pack(fill=tk.X, padx=20, pady=(0, 10))
        
        self.settings_frame.columnconfigure(0, weight=1)
        self.settings_frame.columnconfigure(1, weight=1)
        
        # SQLite DB 경로 입력
        db_label = tk.Label(self.settings_frame, text="로컬 SQLite DB 파일 경로 (db_path)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        db_label.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        db_input_frame = tk.Frame(self.settings_frame, bg=self.color_bg)
        db_input_frame.grid(row=1, column=0, columnspan=2, sticky=tk.EW, pady=(0, 10))
        db_input_frame.columnconfigure(0, weight=1)
        
        db_entry = tk.Entry(db_input_frame, textvariable=self.db_path_var, font=("Consolas", 9), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        db_entry.grid(row=0, column=0, sticky=tk.EW, ipady=4, padx=(0, 8))
        
        btn_browse = tk.Button(db_input_frame, text="찾기...", font=("Segoe UI", 8, "bold"), bg=self.color_card, fg=self.color_text_main, activebackground=self.color_border, bd=0, relief=tk.FLAT, padx=10, command=self.browse_db_file)
        btn_browse.grid(row=0, column=1, sticky=tk.E)
        self.bind_hover(btn_browse, self.color_border, self.color_card)
        
        # 사이트 이름 입력
        site_name_label = tk.Label(self.settings_frame, text="사이트 이름 (Site Name)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        site_name_label.grid(row=2, column=0, sticky=tk.W, pady=(0, 2), padx=(0, 5))
        
        site_name_entry = tk.Entry(self.settings_frame, textvariable=self.site_name_var, font=("Consolas", 9), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        site_name_entry.grid(row=3, column=0, sticky=tk.EW, ipady=4, pady=(0, 8), padx=(0, 5))

        # Device ID 장치명 (읽기 전용)
        device_id_label = tk.Label(self.settings_frame, text="인식된 장치명 (Device ID - 읽기 전용)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        device_id_label.grid(row=2, column=1, sticky=tk.W, pady=(0, 2), padx=(5, 0))
        
        device_id_entry = tk.Entry(self.settings_frame, textvariable=self.device_id_var, font=("Consolas", 9), bg=self.color_card_dark, fg=self.color_text_muted, bd=0, highlightthickness=1, highlightbackground=self.color_border, state="readonly")
        device_id_entry.grid(row=3, column=1, sticky=tk.EW, ipady=4, pady=(0, 8), padx=(5, 0))

        # 동기화 주기 (분) 입력
        interval_label = tk.Label(self.settings_frame, text="자동 동기화 주기 (분 단위)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        interval_label.grid(row=4, column=0, sticky=tk.W, pady=(0, 2), padx=(0, 5))
        
        interval_entry = tk.Entry(self.settings_frame, textvariable=self.interval_var, font=("Consolas", 9), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        interval_entry.grid(row=5, column=0, sticky=tk.EW, ipady=4, pady=(0, 8), padx=(0, 5))

        # 시작 시 자동 동기화 활성화 체크박스
        self.start_active_chk = tk.Checkbutton(
            self.settings_frame, 
            text="시작 시 자동 동기화 활성화", 
            variable=self.start_active_var, 
            fg=self.color_text_main, 
            bg=self.color_bg, 
            selectcolor=self.color_card_dark, 
            activebackground=self.color_bg, 
            activeforeground=self.color_text_main,
            font=("Segoe UI", 8, "bold")
        )
        self.start_active_chk.grid(row=5, column=1, sticky=tk.W, pady=(0, 8), padx=(5, 0))

        # 상세 설정 펼치기 트리거 버튼 (Collapsible Trigger)
        self.adv_trigger_btn = tk.Button(
            self.settings_frame,
            text="➕ 상세 인프라 설정 표시 (Supabase/SMTP/Telegram)",
            font=("Segoe UI", 8, "bold"),
            fg=self.color_text_muted,
            bg=self.color_bg,
            activeforeground=self.color_cyan,
            activebackground=self.color_bg,
            bd=0,
            cursor="hand2",
            command=self.toggle_advanced_settings
        )
        self.adv_trigger_btn.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))

        # 상세 인프라 설정 컨테이너 프레임 (초기에는 숨김 상태)
        self.adv_frame = tk.Frame(self.settings_frame, bg=self.color_bg)

        # 원클릭 환경설정 일괄 영구 저장 버튼
        self.btn_save_all = tk.Button(
            self.settings_frame,
            text="💾 모든 설정 및 자격 증명 저장",
            font=("Segoe UI", 9, "bold"),
            bg=self.color_cyan,
            fg=self.color_bg,
            activebackground="#0891b2",
            activeforeground=self.color_bg,
            bd=0,
            pady=6,
            command=self.save_config
        )
        self.btn_save_all.grid(row=8, column=0, columnspan=2, sticky=tk.EW, pady=(10, 5))
        self.bind_hover(self.btn_save_all, "#22d3ee", self.color_cyan)

        # 4. Recent SQL Query Box
        query_title = tk.Label(self.root, text="최근 업로드 증분 쿼리 (Consolas Query Log)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        query_title.pack(anchor=tk.W, padx=20, pady=(2, 2))
        
        self.query_text = tk.Label(
            self.root, 
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
            highlightthickness=0
        )
        self.query_text.pack(fill=tk.X, padx=20, pady=(0, 10))

        # 6. Bottom Controls Frame
        btn_frame = tk.Frame(self.root, bg=self.color_bg)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=(0, 15))
        
        self.btn_pause_text = tk.StringVar(value="일시정지 ⏸")
        self.btn_pause = tk.Button(
            btn_frame, 
            textvariable=self.btn_pause_text, 
            font=("Segoe UI", 9, "bold"), 
            bg=self.color_orange, 
            fg="#ffffff", 
            bd=0,
            width=20,
            pady=7,
            command=self.toggle_pause
        )
        self.btn_pause.pack(side=tk.LEFT)
        self.bind_hover(self.btn_pause, "#fbbf24", self.color_orange)
        
        self.btn_sync_now = tk.Button(
            btn_frame, 
            text="즉시 동기화 🔄", 
            font=("Segoe UI", 9, "bold"), 
            bg=self.color_cyan, 
            fg=self.color_bg, 
            bd=0,
            width=20,
            pady=7,
            command=self.trigger_sync_now
        )
        self.btn_sync_now.pack(side=tk.RIGHT)
        self.bind_hover(self.btn_sync_now, "#22d3ee", self.color_cyan)

        # 5. Logger Frame (가동 정보 로그)
        logger_frame = tk.Frame(self.root, bg=self.color_bg)
        logger_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))
        
        log_label = tk.Label(logger_frame, text="실시간 가동 로그 (Live System Logs)", font=("Segoe UI", 8, "bold"), fg=self.color_text_muted, bg=self.color_bg)
        log_label.pack(anchor=tk.W, pady=(0, 2))
        
        scrollbar = tk.Scrollbar(logger_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_viewer = tk.Text(
            logger_frame, 
            height=3, 
            bg=self.color_card_dark, 
            fg=self.color_text_main, 
            font=("Consolas", 8),
            bd=0,
            highlightthickness=1,
            highlightbackground=self.color_border,
            yscrollcommand=scrollbar.set
        )
        self.log_viewer.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_viewer.yview)

        # 디폴트 윈도우 사이즈 지정 및 초기화
        self.show_advanced = False
        self.root.geometry("640x605")
        self.update_status_badge()
        self.update_pause_button_style()

    def toggle_advanced_settings(self):
        """상세 설정 프레임을 토글하고 창 크기를 동적으로 조절합니다."""
        self.show_advanced = not self.show_advanced
        if self.show_advanced:
            self.adv_trigger_btn.configure(text="➖ 상세 인프라 설정 숨기기")
            self.build_advanced_ui()
            self.adv_frame.grid(row=7, column=0, columnspan=2, sticky=tk.NSEW, pady=(5, 5))
            self.root.geometry("640x845")
        else:
            self.adv_trigger_btn.configure(text="➕ 상세 인프라 설정 표시 (Supabase/SMTP/Telegram)")
            self.adv_frame.grid_forget()
            self.root.geometry("640x605")

    def build_advanced_ui(self):
        """숨겨진 상세 연결 및 알림 자격증명 UI 동적 생성"""
        for widget in self.adv_frame.winfo_children():
            widget.destroy()

        self.adv_frame.columnconfigure(0, weight=1)
        self.adv_frame.columnconfigure(1, weight=1)

        # Supabase 헤더
        s_title = tk.Label(self.adv_frame, text="⚡ Supabase 인프라 연결 설정", font=("Segoe UI", 8, "bold"), fg=self.color_cyan, bg=self.color_bg)
        s_title.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))

        url_lbl = tk.Label(self.adv_frame, text="Supabase URL", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        url_lbl.grid(row=1, column=0, sticky=tk.W)
        url_ent = tk.Entry(self.adv_frame, textvariable=self.sub_url_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        url_ent.grid(row=2, column=0, sticky=tk.EW, padx=(0, 10), ipady=3)

        tbl_lbl = tk.Label(self.adv_frame, text="Table Name", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        tbl_lbl.grid(row=1, column=1, sticky=tk.W)
        tbl_ent = tk.Entry(self.adv_frame, textvariable=self.sub_table_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        tbl_ent.grid(row=2, column=1, sticky=tk.EW, ipady=3)

        key_lbl = tk.Label(self.adv_frame, text="Supabase Anon / Service Role Key", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        key_lbl.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(3, 0))
        key_ent = tk.Entry(self.adv_frame, textvariable=self.sub_key_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        key_ent.grid(row=4, column=0, columnspan=2, sticky=tk.EW, ipady=3, pady=(0, 8))

        # 알림 서버 헤더
        a_title = tk.Label(self.adv_frame, text="🔔 실시간 알림 서버 설정", font=("Segoe UI", 8, "bold"), fg=self.color_cyan, bg=self.color_bg)
        a_title.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(5, 5))

        type_lbl = tk.Label(self.adv_frame, text="알림 전송 수단 (alert_type)", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        type_lbl.grid(row=6, column=0, sticky=tk.W)
        
        type_frame = tk.Frame(self.adv_frame, bg=self.color_bg)
        type_frame.grid(row=7, column=0, sticky=tk.W, padx=(0, 10), pady=(0, 8))
        
        rb_tg = tk.Radiobutton(type_frame, text="텔레그램", variable=self.alert_type_var, value="telegram", fg=self.color_text_main, bg=self.color_bg, selectcolor=self.color_card_dark, activebackground=self.color_bg, activeforeground=self.color_text_main)
        rb_tg.pack(side=tk.LEFT, padx=(0, 10))
        rb_em = tk.Radiobutton(type_frame, text="이메일", variable=self.alert_type_var, value="email", fg=self.color_text_main, bg=self.color_bg, selectcolor=self.color_card_dark, activebackground=self.color_bg, activeforeground=self.color_text_main)
        rb_em.pack(side=tk.LEFT)

        tg_lbl = tk.Label(self.adv_frame, text="텔레그램 봇 토큰 (telegram_bot_token)", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        tg_lbl.grid(row=6, column=1, sticky=tk.W)
        tg_ent = tk.Entry(self.adv_frame, textvariable=self.tg_token_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        tg_ent.grid(row=7, column=1, sticky=tk.EW, ipady=3, pady=(0, 8))

        # SMTP Host & Port
        smtp_lbl = tk.Label(self.adv_frame, text="SMTP 서버 주소 / 포트", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        smtp_lbl.grid(row=8, column=0, sticky=tk.W)
        
        smtp_box = tk.Frame(self.adv_frame, bg=self.color_bg)
        smtp_box.grid(row=9, column=0, sticky=tk.EW, padx=(0, 10), pady=(0, 5))
        smtp_box.columnconfigure(0, weight=3)
        smtp_box.columnconfigure(1, weight=1)
        
        smtp_srv = tk.Entry(smtp_box, textvariable=self.smtp_server_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        smtp_srv.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5), ipady=3)
        smtp_prt = tk.Entry(smtp_box, textvariable=self.smtp_port_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        smtp_prt.grid(row=0, column=1, sticky=tk.EW, ipady=3)

        tls_chk = tk.Checkbutton(self.adv_frame, text="TLS 사용", variable=self.smtp_tls_var, fg=self.color_text_main, bg=self.color_bg, selectcolor=self.color_card_dark, activebackground=self.color_bg, activeforeground=self.color_text_main)
        tls_chk.grid(row=9, column=1, sticky=tk.W, pady=(0, 5))

        # SMTP User & Password
        user_lbl = tk.Label(self.adv_frame, text="SMTP 계정명", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        user_lbl.grid(row=10, column=0, sticky=tk.W)
        user_ent = tk.Entry(self.adv_frame, textvariable=self.smtp_user_var, font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        user_ent.grid(row=11, column=0, sticky=tk.EW, padx=(0, 10), ipady=3)

        pw_lbl = tk.Label(self.adv_frame, text="SMTP 비밀번호", font=("Segoe UI", 8), fg=self.color_text_muted, bg=self.color_bg)
        pw_lbl.grid(row=10, column=1, sticky=tk.W)
        pw_ent = tk.Entry(self.adv_frame, textvariable=self.smtp_pw_var, show="*", font=("Consolas", 8), bg=self.color_card_dark, fg=self.color_text_main, bd=0, highlightthickness=1, highlightbackground=self.color_border, highlightcolor=self.color_cyan)
        pw_ent.grid(row=11, column=1, sticky=tk.EW, ipady=3)

    def make_supabase_request(self, url, data=None, headers=None, method="GET", timeout=30, max_retries=3):
        """Supabase API 요청을 재시도(Retry) 및 충분한 타임아웃과 함께 수행합니다."""
        last_exception = None
        for attempt in range(1, max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers=headers or {},
                    method=method
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    status = response.status
                    body = response.read()
                    return status, body
            except Exception as e:
                last_exception = e
                # SSL 핸드쉐이크 타임아웃이나 일반 커넥션 타임아웃 시 재시도 진행
                self.msg_queue.put(("log", f"[네트워크 시도 {attempt}/{max_retries}] 오류 발생으로 재시도합니다: {e}"))
                time.sleep(1.5)
        
        # 모든 시도가 실패했을 때 예외 발생
        raise last_exception

    def bg_update_site_name_on_supabase(self, site_id, site_name, supabase_url, supabase_key):
        """Supabase site_config_v2의 site_name 컬럼을 백그라운드에서 PATCH로 비동기 업데이트합니다."""
        if not supabase_url or not supabase_key:
            return
        try:
            base_url = supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                config_url = f"{base_url}/site_config_v2?site_id=eq.{urllib.parse.quote(site_id)}"
            else:
                config_url = f"{base_url}/rest/v1/site_config_v2?site_id=eq.{urllib.parse.quote(site_id)}"
            
            payload = {
                "site_name": site_name
            }
            data_bytes = json.dumps(payload).encode('utf-8')
            headers = {
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            status, _ = self.make_supabase_request(config_url, data=data_bytes, headers=headers, method="PATCH", timeout=30)
            if status in [200, 201, 204]:
                self.msg_queue.put(("log", f"[원격 설정 갱신] Supabase 지점 한글명이 '{site_name}'으로 실시간 업데이트되었습니다."))
        except Exception as e:
            self.msg_queue.put(("log", f"[원격 설정 갱신 오류] Supabase 사이트 한글명 업데이트 실패: {e}"))

    def save_config_quietly(self):
        """팝업 메시지창 없이 설정을 파일에 조용히 저장합니다."""
        try:
            config_data = {
                "db_path": self.db_path,
                "google_sheet_name": self.sheet_name,
                "supabase_table": self.supabase_table,
                "site_id": self.site_id,
                "device_id": self.device_id,
                "site_name": self.site_name,
                "interval_seconds": self.interval_seconds,
                "last_datetime": self.last_upload_time if self.last_upload_time != "None (First Run)" else "",
                "last_query": self.last_query,
                "is_paused": self.is_paused,
                "is_mock": self.is_mock,
                "supabase_url": self.supabase_url,
                "supabase_key": self.supabase_key,
                "smtp_server": self.smtp_server,
                "smtp_port": self.smtp_port,
                "smtp_user": self.smtp_user,
                "smtp_password": self.smtp_password,
                "smtp_use_tls": self.smtp_use_tls,
                "alert_type": self.alert_type,
                "telegram_bot_token": self.telegram_bot_token
            }
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to save config quietly: {e}")

    def save_config(self):
        """현재 UI상에 입력된 모든 설정을 uploader_config.json 파일에 영구 저장합니다."""
        try:
            db_path = self.db_path_var.get().strip()
            site_name = self.site_name_var.get().strip()
            
            # 동기화 주기 파싱 및 검증
            try:
                interval_minutes = float(self.interval_var.get().strip())
                if interval_minutes <= 0:
                    raise ValueError
                interval_seconds = int(interval_minutes * 60)
            except ValueError:
                messagebox.showerror("저장 실패", "동기화 주기는 0보다 큰 숫자여야 합니다.")
                return

            is_paused = not self.start_active_var.get()
            
            # 상세 설정 필드들은 StringVars가 존재할 경우에만 가져오고, 없으면 기존 값을 유지합니다.
            supabase_url = self.sub_url_var.get().strip() if hasattr(self, 'sub_url_var') else self.supabase_url
            supabase_table = self.sub_table_var.get().strip() if hasattr(self, 'sub_table_var') else self.supabase_table
            supabase_key = self.sub_key_var.get().strip() if hasattr(self, 'sub_key_var') else self.supabase_key
            alert_type = self.alert_type_var.get().strip() if hasattr(self, 'alert_type_var') else self.alert_type
            telegram_bot_token = self.tg_token_var.get().strip() if hasattr(self, 'tg_token_var') else self.telegram_bot_token
            smtp_server = self.smtp_server_var.get().strip() if hasattr(self, 'smtp_server_var') else self.smtp_server
            smtp_port = int(self.smtp_port_var.get().strip() or "587") if hasattr(self, 'smtp_port_var') else self.smtp_port
            smtp_user = self.smtp_user_var.get().strip() if hasattr(self, 'smtp_user_var') else self.smtp_user
            smtp_password = self.smtp_pw_var.get().strip() if hasattr(self, 'smtp_pw_var') else self.smtp_password
            smtp_use_tls = self.smtp_tls_var.get() if hasattr(self, 'smtp_tls_var') else self.smtp_use_tls

            if not db_path:
                messagebox.showerror("저장 실패", "SQLite DB 파일 경로는 필수 입력 항목입니다.")
                return
            if not site_name:
                messagebox.showerror("저장 실패", "사이트 이름은 필수 입력 항목입니다.")
                return

            config_data = {
                "db_path": db_path,
                "google_sheet_name": self.sheet_name,
                "supabase_table": supabase_table,
                "site_id": self.site_id,
                "device_id": self.device_id,
                "site_name": site_name,
                "interval_seconds": interval_seconds,
                "last_datetime": self.last_upload_time if self.last_upload_time != "None (First Run)" else "",
                "last_query": self.last_query,
                "is_paused": is_paused,
                "is_mock": self.is_mock,
                "supabase_url": supabase_url,
                "supabase_key": supabase_key,
                "smtp_server": smtp_server,
                "smtp_port": smtp_port,
                "smtp_user": smtp_user,
                "smtp_password": smtp_password,
                "smtp_use_tls": smtp_use_tls,
                "alert_type": alert_type,
                "telegram_bot_token": telegram_bot_token
            }

            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=4, ensure_ascii=False)

            self.db_path = db_path
            self.site_name = site_name
            self.interval_seconds = interval_seconds
            self.is_paused = is_paused
            self.supabase_url = supabase_url
            self.supabase_table = supabase_table
            self.supabase_key = supabase_key
            self.alert_type = alert_type
            self.telegram_bot_token = telegram_bot_token
            self.smtp_server = smtp_server
            self.smtp_port = smtp_port
            self.smtp_user = smtp_user
            self.smtp_password = smtp_password
            self.smtp_use_tls = smtp_use_tls

            # Supabase site_config_v2의 site_name 컬럼 비동기 업데이트
            if supabase_url and supabase_key:
                threading.Thread(
                    target=self.bg_update_site_name_on_supabase,
                    args=(self.site_id, site_name, supabase_url, supabase_key),
                    daemon=True
                ).start()

            # Alert Sender 모듈 재구축
            self.alert_sender = get_alert_sender(
                self.alert_type,
                smtp_server=self.smtp_server,
                smtp_port=self.smtp_port,
                smtp_user=self.smtp_user,
                smtp_password=self.smtp_password,
                smtp_use_tls=self.smtp_use_tls,
                telegram_bot_token=self.telegram_bot_token,
                log_queue=self.msg_queue
            )

            self.check_mock_status()
            self.refresh_destination_label()
            self.log_to_viewer("[설정 저장] 모든 설정을 uploader_config.json에 성공적으로 저장하고 엔진에 즉시 반영했습니다.")
            messagebox.showinfo("설정 완료", "모든 설정 정보가 성공적으로 저장 및 적용되었습니다.")
        except Exception as e:
            messagebox.showerror("저장 실패", f"설정 파일 저장 중 오류가 발생했습니다:\n{e}")


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
            self.log_to_viewer(f"[설정 변경] 연동 DB 경로가 임시 변경되었습니다: {file_path}")

    def check_mock_status(self):
        """Supabase 접속 정보 충족 유무에 따라 실시간 런타임 전송 모드 토글"""
        if self.supabase_url and self.supabase_key:
            self.is_mock = False
            self.log_to_viewer("[알림] Supabase 연결 설정이 충족되어 실시간 클라우드 모드로 작동합니다.")
        else:
            self.is_mock = True
            self.log_to_viewer("[알림] Supabase 접속 설정이 비어있어 로컬 모의 적재(Mock) 모드로 대기합니다.")

    def refresh_destination_label(self):
        """GUI 상에 표시되는 목적지 안내 라벨 실시간 갱신"""
        if hasattr(self, 'dest_val_label'):
            self.dest_val_label.configure(text=self.get_dest_desc())
        if hasattr(self, 'site_val_label'):
            self.site_val_label.configure(text=self.site_name)

    def log_to_viewer(self, message):
        """UI 가동 로그 창에 실시간 정보 추가"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}\n"
        
        self.log_viewer.configure(state=tk.NORMAL)
        self.log_viewer.insert(tk.END, log_line)
        self.log_viewer.see(tk.END)
        self.log_viewer.configure(state=tk.DISABLED)
        
        try:
            with open(LOG_PATH, "a", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

    def update_status_badge(self):
        """가동 중 / 일시정지 배지 인디케이터 색상 갱신"""
        if not hasattr(self, 'status_canvas') or not hasattr(self, 'status_label'):
            return
        if self.is_paused:
            self.status_canvas.itemconfig(self.status_circle, fill=self.color_orange)
            self.status_label.configure(text="일시정지 (PAUSED)", fg=self.color_orange)
        else:
            self.status_canvas.itemconfig(self.status_circle, fill=self.color_green)
            self.status_label.configure(text="가동 중 (ACTIVE)", fg=self.color_green)

    def update_pause_button_style(self):
        """일시정지 버튼 토글 스타일 갱신"""
        if not hasattr(self, 'btn_pause'):
            return
        if self.is_paused:
            self.btn_pause_text.set("업로드 재개 ▶")
            self.btn_pause.configure(bg=self.color_green)
            self.bind_hover(self.btn_pause, "#34d399", self.color_green)
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
                self.timer_val_label.configure(
                    text=f"{minutes}분 {seconds:02d}초 남음"
                )
                
                if self.time_left <= 0:
                    self.log_to_viewer("자동 타이머 만료. 정기 동기화를 가동합니다...")
                    self.run_upload_thread()
                    self.time_left = self.interval_seconds
            else:
                self.timer_val_label.configure(
                    text="일시정지 상태"
                )
            
            # 10초마다 Supabase 설정에서 원격 테스트 메일 트리거 감지
            self.check_config_timer += 1
            if self.check_config_timer >= 10:
                self.check_config_timer = 0
                if self.supabase_url and self.supabase_key and not self.is_mock:
                    threading.Thread(target=self.bg_check_test_alert_trigger, daemon=True).start()

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
            
            req_url += f"?select=Date_Time&Site_ID=eq.{urllib.parse.quote(self.site_id)}&order=Date_Time.desc&limit=1"
            
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json"
            }
            status, body = self.make_supabase_request(req_url, headers=headers, method="GET", timeout=30)
            data = json.loads(body.decode('utf-8'))
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

        # B2B 다중 기기 및 지점 식별을 위해 데이터에 Site_ID, Device_ID 컬럼 삽입 가공
        processed_columns = list(columns)
        processed_columns.insert(1, 'Site_ID')
        processed_columns.insert(2, 'Device_ID')
        
        processed_rows = []
        for row in rows:
            row_list = list(row)
            row_list.insert(1, self.site_id)
            row_list.insert(2, self.device_id)
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
                if col_name == 'MAXR':
                    continue
                val = row[idx]
                if col_name == 'Channel':
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
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal, resolution=ignore-duplicates"
            }
            status, _ = self.make_supabase_request(req_url, data=data_bytes, headers=headers, method="POST", timeout=30)
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

    def auto_register_site_config(self):
        """Supabase site_config_v2 테이블에 현재 site_id용 기본 설정을 자동 등록합니다."""
        try:
            base_url = self.supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                config_url = f"{base_url}/site_config_v2"
            else:
                config_url = f"{base_url}/rest/v1/site_config_v2"
                
            default_toc_alert = {
                "use_single_table": True,
                "alert_emails": "",
                "telegram_chat_ids": "",
                "1": { "warning": 2000 },
                "2": { "warning": 1000 },
                "3": { "warning": 50 }
            }
            
            payload = {
                "site_id": self.site_id,
                "site_name": self.site_id,
                "passcode": "850",
                "toc_alert_high": default_toc_alert,
                "use_single_table": True
            }
            
            data_bytes = json.dumps(payload).encode('utf-8')
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            status, _ = self.make_supabase_request(config_url, data=data_bytes, headers=headers, method="POST", timeout=30)
            if status in [200, 201, 204]:
                self.msg_queue.put(("log", f"[자동 등록 성공] Supabase에 '{self.site_id}' 사이트 설정이 성공적으로 자동 등록되었습니다!"))
                return True
            else:
                self.msg_queue.put(("log", f"[자동 등록 실패] 서버 응답 상태: {status}"))
        except Exception as e:
            self.msg_queue.put(("log", f"[자동 등록 오류] {e}"))
        return False

    def fetch_site_config(self, allow_auto_reg=True):
        """Supabase에서 사이트 설정(임계값 및 이메일 수신 목록)을 실시간으로 가져옵니다."""
        try:
            base_url = self.supabase_url.rstrip('/')
            if "/rest/v1" in base_url:
                config_url = f"{base_url}/site_config_v2?site_id=eq.{urllib.parse.quote(self.site_id)}"
            else:
                config_url = f"{base_url}/rest/v1/site_config_v2?site_id=eq.{urllib.parse.quote(self.site_id)}"
                
            headers = {
                "apikey": self.supabase_key,
                "Authorization": f"Bearer {self.supabase_key}"
            }
            status, body = self.make_supabase_request(config_url, headers=headers, method="GET", timeout=30)
            if status == 200:
                res_data = json.loads(body.decode('utf-8'))
                if isinstance(res_data, list) and len(res_data) > 0:
                    cfg = res_data[0]
                    remote_name = cfg.get("site_name")
                    if remote_name:
                        self.msg_queue.put(("site_name", remote_name))
                    return cfg
                elif isinstance(res_data, list) and len(res_data) == 0 and allow_auto_reg:
                    self.msg_queue.put(("log", f"[자동 등록] Supabase에 '{self.site_id}' 설정이 없어 새 등록을 시도합니다..."))
                    if self.auto_register_site_config():
                        return self.fetch_site_config(allow_auto_reg=False)
        except Exception as e:
            self.msg_queue.put(("log", f"[설정 정보 로드 실패] 오류: {e}"))
        return None

    def check_and_send_alerts(self, records):
        """새로 수집된 레코드들의 TOC 수치가 경고 임계값을 초과하는지 검사하고 알림을 발송합니다."""
        # 1. 사이트 설정 로드 (임계값 및 수신 목록)
        config_data = self.fetch_site_config()
        
        toc_alert_high = {}
        alert_emails = ""
        telegram_chat_ids = ""
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
                telegram_chat_ids = alert_json.get("telegram_chat_ids", "")

        # 알림 타입에 따라 수신인 선택
        recipients = ""
        if self.alert_type == "telegram":
            recipients = telegram_chat_ids
        else:
            recipients = alert_emails

        if not recipients:
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
                
                # 알림 전송 실행 (추상화된 알람 발송기 사용)
                success = self.alert_sender.send_alert(recipients, subject, body)
                if success:
                    # 전송 성공 시 쿨다운 타임 업데이트
                    self.last_alert_time[channel_id] = now_time

    def bg_check_test_alert_trigger(self):
        """Supabase 설정을 GET 하여 trigger_test_email 또는 trigger_test_telegram 플래그가 참인지 확인하고, 참이면 메일을 발송한 뒤 플래그를 내립니다."""
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
            
        trigger_email = toc_alert_high.get("trigger_test_email", False)
        trigger_telegram = toc_alert_high.get("trigger_test_telegram", False)
        
        updated = False
        site_name = config_data.get("site_name", self.device_id)
        
        if trigger_email:
            self.msg_queue.put(("log", "[알림 메일 테스트] 웹으로부터 테스트 메일 발송 신호를 감지했습니다!"))
            alert_emails = toc_alert_high.get("alert_emails", "")
            
            if not alert_emails:
                self.msg_queue.put(("log", "[알림 메일 테스트 실패] 수신인 이메일 주소가 비어있습니다."))
            else:
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
                        </div>
                    </div>
                </body>
                </html>
                """
                from alerts.email_sender import EmailAlertSender
                email_sender = EmailAlertSender(
                    smtp_server=self.smtp_server,
                    smtp_port=self.smtp_port,
                    smtp_user=self.smtp_user,
                    smtp_password=self.smtp_password,
                    smtp_use_tls=self.smtp_use_tls,
                    log_queue=self.msg_queue
                )
                email_sender.send_alert(alert_emails, subject, body)
                
            toc_alert_high["trigger_test_email"] = False
            updated = True

        if trigger_telegram:
            self.msg_queue.put(("log", "[텔레그램 알림 테스트] 웹으로부터 테스트 텔레그램 발송 신호를 감지했습니다!"))
            telegram_chat_ids = toc_alert_high.get("telegram_chat_ids", "")
            
            if not telegram_chat_ids:
                self.msg_queue.put(("log", "[텔레그램 알림 테스트 실패] 수신 대상 Chat ID가 비어있습니다."))
            else:
                subject = f"[TOC 모의 텔레그램 알람] {site_name} 발송 검증"
                body = f"""
                웹 설정 화면에서 요청하신 텔레그램 즉시 발송 검증이 완료되었습니다!
                
                이 메시지가 수신되었다면, <b>계측기 로컬 텔레그램 봇과 Supabase 클라우드 간의 연동이 완벽하게 완료</b>된 것입니다.
                
                테스트 시간: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                """
                from alerts.telegram_sender import TelegramAlertSender
                tg_sender = TelegramAlertSender(
                    bot_token=self.telegram_bot_token,
                    log_queue=self.msg_queue
                )
                tg_sender.send_alert(telegram_chat_ids, subject, body)
                
            toc_alert_high["trigger_test_telegram"] = False
            updated = True

        if updated:
            try:
                base_url = self.supabase_url.rstrip('/')
                if "/rest/v1" in base_url:
                    config_url = f"{base_url}/site_config_v2?site_id=eq.{urllib.parse.quote(self.site_id)}"
                else:
                    config_url = f"{base_url}/rest/v1/site_config_v2?site_id=eq.{urllib.parse.quote(self.site_id)}"
                
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal"
                }
                data_bytes = json.dumps({"toc_alert_high": toc_alert_high}).encode('utf-8')
                status, _ = self.make_supabase_request(config_url, data=data_bytes, headers=headers, method="PATCH", timeout=30)
                if status in [200, 201, 204]:
                    self.msg_queue.put(("log", "[원격 테스트] 웹 모의 테스트 요청 플래그를 리셋 완료했습니다."))
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
                    self.last_success_val_label.configure(
                        text=latest_time
                    )
                    self.log_to_viewer(f"데이터 동기화 완료! 장비 ID: {self.device_id} | 최신 측정 시간: {latest_time}")
                    self._auto_minimize_if_startup()
                elif msg_type == "site_name":
                    if content and content != self.site_name:
                        self.site_name = content
                        self.site_name_var.set(content)
                        self.save_config_quietly()
                        self.refresh_destination_label()
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
