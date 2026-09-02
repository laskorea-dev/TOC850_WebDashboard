"""오차가 곱셈형인가 덧셈형인가 — OFST 를 0 으로 두는 근거.

희석수에 TOC 가 섞여 들어오는 오염이라면 오차는 덧셈형이어야 한다.
×5 희석에서 희석수 TOC 가 C_w 라면 표시값 = 실제 + 4·C_w 이므로 기울기는 1 이고
절편만 음수로 붙는다. 반대로 교정 기울기(span) 문제라면 오차는 농도에 비례한다.
두 모델을 같은 자료에 태워 비교하고, 권장안을 적용했을 때의 잔차를 남긴다.
"""
import json
import math
import os
import statistics as st

from common import HERE

FACT_REC, OFST_REC = 0.55, 0.0

with open(os.path.join(HERE, "pairs.json"), encoding="utf-8") as f:
    P = json.load(f)


def corr(a, b):
    ma, mb = st.mean(a), st.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
    return num / den


def rmse(res):
    return math.sqrt(sum(r * r for r in res) / len(res))


print("=== 곱셈형(FACT) vs 덧셈형(OFST) ===")
for name, pts in [("전체", P), ("실험실<10 제외", [p for p in P if p[1] >= 10])]:
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    a = sum(xi * yi for xi, yi in zip(x, y)) / sum(xi * xi for xi in x)
    b = st.mean(yi - xi for xi, yi in zip(x, y))
    print(f"\n{name}  n={len(x)}")
    print(f"  곱셈형  FACT={a:.4f} OFST=0        RMSE={rmse([yi - a*xi for xi, yi in zip(x, y)]):5.2f}")
    print(f"  덧셈형  FACT=1      OFST={b:+.2f}   RMSE={rmse([yi - (xi + b) for xi, yi in zip(x, y)]):5.2f}")
    print(f"  (계측기−실험실) vs 계측기값  r={corr(x, [xi - yi for xi, yi in zip(x, y)]):+.3f}"
          "   → +1 에 가까우면 오차가 농도에 비례 = 곱셈형")
    print(f"  (실험실/계측기) vs 계측기값  r={corr(x, [yi / xi for xi, yi in zip(x, y)]):+.3f}"
          "   → 0 에 가까우면 비율이 농도와 무관 = 곱셈형 타당")

print(f"\n=== 권장안 FACT={FACT_REC}, OFST={OFST_REC} 적용 ===")
print(f"{'채취시각':<17}{'계측기':>9}{'보정후':>9}{'실험실':>8}{'오차':>8}{'오차%':>8}")
err = []
for inst, lab, win, stamp in P:
    c = FACT_REC * inst + OFST_REC
    err.append(c - lab)
    print(f"{stamp:<17}{inst:>9.2f}{c:>9.1f}{lab:>8.1f}{c-lab:>+8.1f}{100*(c-lab)/lab:>+8.1f}")
print(f"  전체          평균오차={st.mean(err):+.2f}  RMSE={rmse(err):.2f}")
e2 = [e for e, p in zip(err, P) if p[1] >= 10]
print(f"  실험실<10 제외 평균오차={st.mean(e2):+.2f}  RMSE={rmse(e2):.2f}")

ratio = [p[1] / p[0] for p in P if p[1] >= 10]
m, s, n = st.mean(ratio), st.stdev(ratio), len(ratio)
print(f"\n비율 평균={m:.4f} 표준편차={s:.4f} n={n}"
      f"   95%CI ≈ {m-1.96*s/math.sqrt(n):.3f} ~ {m+1.96*s/math.sqrt(n):.3f}")

pos = [e for e in e2 if e > 0]
neg = [e for e in e2 if e <= 0]
print(f"\n잔차 비대칭: 양(+) {len(pos)}건 최대 {max(pos):+.1f} / "
      f"음(−) {len(neg)}건 최대 {min(neg):+.1f}")
print("  큰 잔차가 한쪽(계측기가 높은 방향)으로만 몰린다.")
print("  채수 후 방치·침전이나 실험실 전처리에서 TOC 가 빠지는 쪽이 의심된다.")
