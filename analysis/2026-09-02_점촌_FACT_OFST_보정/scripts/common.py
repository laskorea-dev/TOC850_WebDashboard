"""공용 자료 — 실험실 대조값과 계측기 원자료 로더.

실험실 데이터는 점촌하수처리장에서 넘겨받은 수기 기록이다(원수 채수, TOC mg/L).
값이 None 인 날은 채수만 하고 분석값이 오지 않은 날.
"""
import datetime as dt
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\antigravity\db_upload_and_dashboard"

# (채취시각, 실험실 TOC mg/L)
LAB = [
    ("2026-08-13 14:25", 70.6),
    ("2026-08-14 09:07", 18.7),
    ("2026-08-15 09:30", 27.0),
    ("2026-08-16 09:30", 24.6),
    ("2026-08-17 09:10", 21.9),
    ("2026-08-18 09:15", 9.6),
    ("2026-08-19 09:05", 32.2),
    ("2026-08-20 09:33", 27.9),
    ("2026-08-21 09:39", 23.3),
    ("2026-08-22 09:11", None),
    ("2026-08-23 09:05", None),
    ("2026-08-24 09:33", 24.0),
    ("2026-08-25 09:33", 7.2),
    ("2026-08-26 09:34", 21.6),
    ("2026-08-28 09:45", 20.6),
    ("2026-08-29 09:33", None),
    ("2026-08-30 09:40", None),
    ("2026-09-01 09:30", 12.5),
]


def config():
    """Supabase 접속정보. 자격증명은 저장소에 넣지 않고 여기서만 읽는다."""
    with open(os.path.join(ROOT, "uploader_config.json"), encoding="utf-8") as f:
        cfg = json.load(f)
    key = cfg["supabase_key"]
    return cfg["supabase_url"].rstrip("/"), {"apikey": key, "Authorization": f"Bearer {key}"}


def load(name="data.json"):
    """fetch.py 가 저장한 계측기 원자료. Date_Time 을 파싱해 t 로 붙이고 시각순 정렬."""
    with open(os.path.join(HERE, name), encoding="utf-8") as f:
        rows = json.load(f)
    for r in rows:
        r["t"] = dt.datetime.fromisoformat(r["Date_Time"])
    rows.sort(key=lambda r: r["t"])
    return rows


def save(obj, name):
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
