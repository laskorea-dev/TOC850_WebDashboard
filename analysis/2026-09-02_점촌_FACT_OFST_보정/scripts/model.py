"""오차가 곱셈형인가 덧셈형인가 — OFST 를 0 으로 두는 근거.

FACT/OFST 가 희석 앞에 걸리므로 OFST 는 물리적으로 "희석수가 들고 들어오는 TOC"를
빼주는 자리다. ×DF 희석에서 희석수 TOC 가 C_w 라면 검출기가 보는 값은

    x = C_true/DF + (1 - 1/DF)·C_w

이고, 이를 되돌리려면 OFST = -(1 - 1/DF)·C_w 여야 한다.
따라서 적합된 OFST 를 C_w 로 환산해 그 값이 현실적인지 보면 모델을 판별할 수 있다.

같은 자료에 곱셈형(FACT 만) / 덧셈형(OFST 만) 을 태워 비교하고,
권장안을 적용했을 때의 잔차를 남긴다.
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
    num = sum((u - ma) * (v - mb) for u, v in zip(a, b))
    den = math.sqrt(sum((u - ma) ** 2 for u in a) * sum((v - mb) ** 2 for v in b))
    return num / den


def rmse(res):
    return math.sqrt(sum(r * r for r in res) / len(res))


print("=== 곱셈형(FACT) vs 덧셈형(OFST) — 희석 전 스케일 ===")
for name, rows in [("전체", P), ("실험실<10 제외", [r for r in P if r["lab"] >= 10])]:
    x = [r["x"] for r in rows]
    y = [r["y"] for r in rows]
    df = st.median(r["df"] for r in rows)
    a = sum(u * v for u, v in zip(x, y)) / sum(u * u for u in x)
    b = st.mean(v - u for u, v in zip(x, y))
    print(f"\n{name}  n={len(x)}  (DF=×{df:.0f})")
    print(f"  곱셈형  FACT={a:.4f} OFST=0        RMSE={rmse([v - a*u for u, v in zip(x, y)]):.3f}")
    print(f"  덧셈형  FACT=1      OFST={b:+.3f}   RMSE={rmse([v - (u + b) for u, v in zip(x, y)]):.3f}"
          f"   → 희석수 C_w={-b/(1-1/df):.1f} mg/L (비현실적)")
    print(f"  (계측기−실험실) vs 계측기값  r={corr(x, [u - v for u, v in zip(x, y)]):+.3f}"
          "   → +1 에 가까우면 오차가 농도에 비례 = 곱셈형")
    print(f"  (실험실/계측기) vs 계측기값  r={corr(x, [v / u for u, v in zip(x, y)]):+.3f}"
          "   → 0 에 가까우면 비율이 농도와 무관 = 곱셈형 타당")

# 절편을 자유롭게 둔 적합에서 희석수 TOC 를 역산
cred = [r for r in P if r["lab"] >= 10]
x = [r["x"] for r in cred]
y = [r["y"] for r in cred]
n = len(x)
mx, my = st.mean(x), st.mean(y)
sxx = sum((u - mx) ** 2 for u in x)
a = sum((u - mx) * (v - my) for u, v in zip(x, y)) / sxx
b = my - a * mx
s2 = sum((v - (a * u + b)) ** 2 for u, v in zip(x, y)) / (n - 2)
se_b = math.sqrt(s2 * (1 / n + mx * mx / sxx))
df = st.median(r["df"] for r in cred)
lo, hi = b - 2.23 * se_b, b + 2.23 * se_b
print(f"\n=== 희석수 TOC 역산 (실험실<10 제외, n={n}) ===")
print(f"  OFST = {b:+.4f} ± {se_b:.4f}  (t={b/se_b:+.2f}, 95%CI {lo:+.3f} ~ {hi:+.3f})")
print(f"  C_w = -OFST/(1-1/DF) = {-b/(1-1/df):.2f} mg/L   "
      f"(95%CI {-hi/(1-1/df):.2f} ~ {-lo/(1-1/df):.2f})")
print("  0 과 구분되지 않는다 → 희석수는 깨끗하다. OFST 를 쓸 이유가 없다.")

print(f"\n=== 권장안 FACT={FACT_REC}, OFST={OFST_REC} 적용 ===")
print(f"{'채취시각':<17}{'표시값':>9}{'보정후':>9}{'실험실':>8}{'오차':>8}{'오차%':>8}")
err = []
for r in P:
    corrected = (r["x"] * FACT_REC + OFST_REC) * r["df"]
    err.append(corrected - r["lab"])
    print(f"{r['stamp']:<17}{r['inst_display']:>9.2f}{corrected:>9.1f}{r['lab']:>8.1f}"
          f"{corrected-r['lab']:>+8.1f}{100*(corrected-r['lab'])/r['lab']:>+8.1f}")
print(f"  전체          평균오차={st.mean(err):+.2f}  RMSE={rmse(err):.2f}")
e2 = [e for e, r in zip(err, P) if r["lab"] >= 10]
print(f"  실험실<10 제외 평균오차={st.mean(e2):+.2f}  RMSE={rmse(e2):.2f}")

ratio = [r["y"] / r["x"] for r in cred]
m, s = st.mean(ratio), st.stdev(ratio)
print(f"\n비율 평균={m:.4f} 표준편차={s:.4f} n={n}"
      f"   95%CI ≈ {m-1.96*s/math.sqrt(n):.3f} ~ {m+1.96*s/math.sqrt(n):.3f}")

pos = [e for e in e2 if e > 0]
neg = [e for e in e2 if e <= 0]
print(f"\n잔차 비대칭: 양(+) {len(pos)}건 최대 {max(pos):+.1f} / "
      f"음(−) {len(neg)}건 최대 {min(neg):+.1f}")
print("  큰 잔차가 한쪽(계측기가 높은 방향)으로만 몰린다.")
print("  채수 후 방치·침전이나 실험실 전처리에서 TOC 가 빠지는 쪽이 의심된다.")

print("\n=== OFST 민감도: 입력한 값이 표시값에 DF 배로 증폭된다 ===")
for d in (1, 5, 10, 20):
    print(f"  DF=×{d:<3d}  OFST 1.0 입력 → 표시값 {1.0*d:+.1f} PPM 이동")
print("  희석배수를 바꾸면 OFST 의 효과도 같이 바뀐다. 0 이 아니면 매번 다시 잡아야 한다.")
