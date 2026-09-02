"""공용 자료 — 실험실 대조값, 계측기 원자료 로더, 계측기 공식.

계측기 적용 순서 (현장 확인, 2026-09-02):

    TOC_Conc = ( (MSIG - ICPT) / SLOP * FACT + OFST ) * DilutionFactor

FACT/OFST 가 먼저 걸리고 희석배수가 마지막에 곱해진다. 즉 FACT/OFST 는
**희석 전(검출기) 스케일**에서 동작한다. 그래서 보정계수를 구할 때는
계측기 표시값과 실험실값을 둘 다 DF 로 나눠 같은 스케일로 맞춰야 한다.

주의: FACT=1 / OFST=0 인 상태에서는 이 식과
`(MSIG-ICPT)/SLOP * DF * FACT + OFST` 가 대수적으로 같다.
저장된 자료만으로는 두 순서를 구분할 수 없다 (verify_formula.py 참조).
"""
import datetime as dt
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"D:\antigravity\db_upload_and_dashboard"

# (채취시각, 실험실 TOC mg/L) — 점촌하수처리장 원수 수기 기록.
# None 은 채수만 하고 분석값이 오지 않은 날.
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


def raw(r):
    """희석 전(검출기) 스케일 값 = (MSIG - ICPT) / SLOP.

    FACT/OFST 가 실제로 곱해지고 더해지는 대상이 이 값이다.
    MSIG 에서 직접 계산하므로 DF 가 중간에 바뀌어도 안전하다.
    """
    return (r["MSIG"] - r["ICPT"]) / r["SLOP"]


def display(r, fact, ofst):
    """FACT/OFST 를 넣었을 때 계측기가 표시할 값."""
    return (raw(r) * fact + ofst) * r["DilutionFactor"]


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
        json.dump(obj, f, ensure_ascii=False, indent=1)
