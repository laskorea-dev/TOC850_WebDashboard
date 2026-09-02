"""FACT / OFST 추정 — 희석 전 스케일에서 y = FACT·x + OFST 를 푼다.

    x = (MSIG-ICPT)/SLOP      계측기 희석 전 값
    y = 실험실 TOC / DF        실험실값을 같은 희석배수로 나눈 것

나온 계수를 그대로 계측기에 입력하면 된다.
FACT 는 두 축을 같은 배수로 나눈 것이라 표시값 스케일에서 구한 값과 같다(스케일 불변).
OFST 만 1/DF 로 줄어든다 — 바꿔 말하면 **입력한 OFST 는 표시값에 DF 배로 증폭돼 나타난다.**

한 가지 회귀만 돌려 숫자 하나를 뽑으면 안 되는 자료다. 표본이 14쌍뿐이고
고농도 점이 8/13 하나라 절편을 자유롭게 두면 부분집합마다 요동친다.
그 요동 자체가 "OFST 는 0 으로 두라"는 근거다.
"""
import itertools
import json
import math
import os
import statistics as st

from common import HERE

with open(os.path.join(HERE, "pairs.json"), encoding="utf-8") as f:
    P = json.load(f)


def ols(pts):
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    a = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    b = my - a * mx
    res = [p[1] - (a * p[0] + b) for p in pts]
    ss = sum(r * r for r in res)
    s2 = ss / (n - 2)
    sst = sum((p[1] - my) ** 2 for p in pts)
    return {
        "a": a, "b": b, "r2": 1 - ss / sst, "rmse": math.sqrt(ss / n),
        "se_a": math.sqrt(s2 / sxx),
        "se_b": math.sqrt(s2 * (1 / n + mx * mx / sxx)),
    }


def theilsen(pts):
    """이상치에 둔감한 중앙값 기반 기울기."""
    slopes = [(q[1] - p[1]) / (q[0] - p[0])
              for p, q in itertools.combinations(pts, 2) if q[0] != p[0]]
    a = st.median(slopes)
    b = st.median(p[1] - a * p[0] for p in pts)
    res = [p[1] - (a * p[0] + b) for p in pts]
    return a, b, math.sqrt(sum(r * r for r in res) / len(res))


def through_origin(pts):
    """OFST=0 으로 고정한 원점 통과 회귀. 권장안이 쓰는 모델."""
    a = sum(p[0] * p[1] for p in pts) / sum(p[0] ** 2 for p in pts)
    res = [p[1] - a * p[0] for p in pts]
    return a, math.sqrt(sum(r * r for r in res) / len(res))


def report(name, rows, xkey="x"):
    pts = [(r[xkey], r["y"]) for r in rows]
    if len(pts) < 3:
        return
    df = st.median(r["df"] for r in rows)
    m = ols(pts)
    ta, tb, trmse = theilsen(pts)
    pa, prmse = through_origin(pts)
    ratio = [y / x for x, y in pts]
    tstat = m["b"] / m["se_b"]
    print(f"\n### {name}  (n={len(pts)})")
    print(f"  OLS        FACT={m['a']:.4f} ±{m['se_a']:.4f}   OFST={m['b']:+.4f} ±{m['se_b']:.4f}"
          f"   R2={m['r2']:.3f} RMSE={m['rmse']:.3f}")
    print(f"             OFST t={tstat:+.2f} → 0 과 구분 {'불가' if abs(tstat) < 2.2 else '가능'}"
          f" / 표시값 환산 {m['b'] * df:+.2f} PPM")
    print(f"  Theil-Sen  FACT={ta:.4f}          OFST={tb:+.4f}"
          f"                    RMSE={trmse:.3f}")
    print(f"  원점통과   FACT={pa:.4f}          OFST= 0.0000"
          f"                    RMSE={prmse:.3f}")
    print(f"  비율       중앙={st.median(ratio):.4f} 평균={st.mean(ratio):.4f} "
          f"범위={min(ratio):.3f}~{max(ratio):.3f}")


print("=== 매칭 원자료 (희석 전 스케일) ===")
for r in P:
    print(f"  {r['stamp']}  표시={r['inst_display']:7.2f} ÷{r['df']:.0f}  "
          f"x={r['x']:7.3f}  y={r['y']:6.3f} (실험실 {r['lab']:5.1f})  비율={r['y']/r['x']:.3f}")

report("A. 전체 · 최근접값", P)
report("A'. 전체 · ±2h 평균  (매칭 방식 민감도)", P, "x_win2h")
report("B. 8/28 이전만  (8/29 단차 이전)", [r for r in P if r["stamp"] < "2026-08-29"])

# 원수 TOC 10 미만은 비현실적이고 그날 계측기는 평온했다 → 실험실 쪽 이상치로 본다
credible = [r for r in P if r["lab"] >= 10]
report("C. 실험실<10 제외 (8/18, 8/25)", credible)

m = ols([(r["x"], r["y"]) for r in credible])
ranked = sorted(credible, key=lambda r: -abs(r["y"] - (m["a"] * r["x"] + m["b"])))
print("\n  C 잔차 상위:",
      [(f"{abs(r['y'] - (m['a']*r['x'] + m['b'])):.2f}", r["stamp"][:10]) for r in ranked[:4]])
report("D. C 에서 잔차 상위 2점 추가 제외", ranked[2:])

# 8/13 이 유일한 고농도 점이다. 빼면 기울기가 결정되지 않는다는 것을 보인다
report("E. 8/13 제외  (레버리지 확인 — 이 결과는 채택하지 않는다)",
       [r for r in P if not r["stamp"].startswith("2026-08-13")])
