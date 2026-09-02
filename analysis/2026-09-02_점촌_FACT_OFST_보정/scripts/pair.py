"""채취시각 ↔ 계측기 측정값 매칭 → pairs.json

FACT/OFST 는 희석 전(검출기) 스케일에서 동작하므로, 양쪽을 그 스케일로 맞춰 남긴다.

    x = (MSIG - ICPT) / SLOP        계측기 희석 전 값
    y = 실험실 TOC / DilutionFactor  실험실값을 같은 희석배수로 나눈 것

fit.py 는 y = FACT·x + OFST 를 푼다. 그래서 나온 계수를 그대로 계측기에 넣으면 된다.

8/13 부터 측정 주기가 60분이라 채수 시각과 정확히 일치하는 값이 없다.
최근접 1점을 쓰되 ±60분을 넘으면 버리고, 참고용으로 ±2시간 평균도 같이 남긴다.
"""
import datetime as dt
import statistics as st

from common import LAB, load, raw, save

NEAR_LIMIT_MIN = 60
WINDOW_SEC = 7200

rows = load()
pairs = []

print(f"{'채취시각':<17}{'실험실':>7}{'계측기시각':>18}{'Δ분':>5}"
      f"{'표시값':>9}{'DF':>5}{'x(희석전)':>10}{'y(실험실/DF)':>12}{'비율':>7}")
for stamp, lab in LAB:
    t = dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    near = min(rows, key=lambda r: abs((r["t"] - t).total_seconds()))
    dmin = (near["t"] - t).total_seconds() / 60
    df = near["DilutionFactor"]
    x = raw(near)
    win = [raw(r) for r in rows
           if abs((r["t"] - t).total_seconds()) <= WINDOW_SEC and r["MSIG"] is not None]
    y = lab / df if lab is not None else None
    print(f"{stamp:<17}{(f'{lab:.1f}' if lab is not None else '-'):>7}"
          f"{near['t'].strftime('%m-%d %H:%M:%S'):>18}{dmin:>5.0f}"
          f"{near['TOC_Conc']:>9.2f}{df:>5.0f}{x:>10.3f}"
          f"{(f'{y:.3f}' if y is not None else '-'):>12}"
          f"{(f'{y/x:.3f}' if y is not None else '-'):>7}")
    if lab is not None and abs(dmin) <= NEAR_LIMIT_MIN:
        pairs.append({
            "stamp": stamp,
            "x": x,                     # 희석 전 계측기값
            "y": y,                     # 실험실값 / DF
            "df": df,
            "inst_display": near["TOC_Conc"],
            "lab": lab,
            "x_win2h": st.mean(win),    # 매칭 민감도 확인용
        })

save(pairs, "pairs.json")
print(f"\n유효쌍 {len(pairs)} / 실험실값 {sum(1 for _, v in LAB if v is not None)}")
