"""채취시각 ↔ 계측기 측정값 매칭 → pairs.json

8/13 부터 측정 주기가 60분이라 정확히 같은 시각의 값이 없다.
최근접 1점을 쓰되 ±60분을 넘으면 버리고, 참고용으로 ±2시간 평균도 같이 남긴다.
(fit.py 에서 두 방식의 결과가 갈리지 않는지 확인한다)
"""
import datetime as dt
import statistics as st

from common import LAB, load, save

NEAR_LIMIT_MIN = 60
WINDOW_SEC = 7200

rows = load()
pairs = []

print(f"{'채취시각':<17}{'실험실':>7}{'계측기시각':>18}{'Δ분':>6}{'계측기':>9}{'MSIG':>10}{'±2h평균':>9}{'n':>4}")
for stamp, lab in LAB:
    t = dt.datetime.strptime(stamp, "%Y-%m-%d %H:%M")
    near = min(rows, key=lambda r: abs((r["t"] - t).total_seconds()))
    dmin = (near["t"] - t).total_seconds() / 60
    win = [r["TOC_Conc"] for r in rows
           if abs((r["t"] - t).total_seconds()) <= WINDOW_SEC and r["TOC_Conc"] is not None]
    wmean = st.mean(win) if win else float("nan")
    print(f"{stamp:<17}{(f'{lab:.1f}' if lab is not None else '-'):>7}"
          f"{near['t'].strftime('%m-%d %H:%M:%S'):>18}{dmin:>6.0f}"
          f"{near['TOC_Conc']:>9.2f}{near['MSIG']:>10.2f}{wmean:>9.2f}{len(win):>4}")
    if lab is not None and abs(dmin) <= NEAR_LIMIT_MIN:
        pairs.append([near["TOC_Conc"], lab, wmean, stamp])

save(pairs, "pairs.json")
print(f"\n유효쌍 {len(pairs)} / 실험실값 {sum(1 for _, v in LAB if v is not None)}")
