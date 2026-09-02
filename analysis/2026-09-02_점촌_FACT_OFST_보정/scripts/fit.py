"""FACT / OFST 추정 — 추정법과 부분집합을 바꿔가며 값이 얼마나 흔들리는지 본다.

한 가지 회귀만 돌려 숫자 하나를 뽑으면 안 되는 자료다. 표본이 14쌍뿐이고
고농도 점이 8/13 하나라 절편을 자유롭게 두면 부분집합마다 −7.5 ~ +6.1 로 요동친다.
그 요동 자체가 "OFST 는 0 으로 두라"는 근거다.
"""
import itertools
import json
import math
import os
import statistics as st

from common import HERE

with open(os.path.join(HERE, "pairs.json"), encoding="utf-8") as f:
    P = json.load(f)  # [계측기 최근접값, 실험실값, ±2h평균, 채취시각]


def ols(pts):
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    a = sum((p[0] - mx) * (p[1] - my) for p in pts) / sxx
    b = my - a * mx
    res = [p[1] - (a * p[0] + b) for p in pts]
    ss = sum(r * r for r in res)
    sst = sum((p[1] - my) ** 2 for p in pts)
    return a, b, 1 - ss / sst, math.sqrt(ss / n), math.sqrt(ss / (n - 2) / sxx)


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


def report(name, pts, xi=0):
    q = [(p[xi], p[1]) for p in pts]
    if len(q) < 3:
        return
    a, b, r2, rmse, se = ols(q)
    ta, tb, trmse = theilsen(q)
    pa, prmse = through_origin(q)
    ratio = [y / x for x, y in q]
    print(f"\n### {name}  (n={len(q)})")
    print(f"  OLS        FACT={a:.4f}  OFST={b:+.3f}   R2={r2:.3f} RMSE={rmse:5.2f}  (FACT SE={se:.3f})")
    print(f"  Theil-Sen  FACT={ta:.4f}  OFST={tb:+.3f}           RMSE={trmse:5.2f}")
    print(f"  원점통과   FACT={pa:.4f}  OFST= 0.000           RMSE={prmse:5.2f}")
    print(f"  비율       중앙={st.median(ratio):.4f} 평균={st.mean(ratio):.4f} "
          f"범위={min(ratio):.3f}~{max(ratio):.3f}")


print("=== 매칭 원자료 ===")
for inst, lab, win, stamp in P:
    print(f"  {stamp}  계측기={inst:7.2f}  실험실={lab:6.1f}  비율={lab/inst:.3f}  ±2h={win:7.2f}")

report("A. 전체 · 최근접값", P, 0)
report("A'. 전체 · ±2h 평균  (매칭 방식 민감도)", P, 2)
report("B. 8/28 이전만  (8/29 단차 이전)", [p for p in P if p[3] < "2026-08-29"], 0)

# 원수 TOC 10 미만은 비현실적이고 그날 계측기는 평온했다 → 실험실 쪽 이상치로 본다
credible = [p for p in P if p[1] >= 10]
report("C. 실험실<10 제외 (8/18, 8/25)", credible, 0)

a, b, *_ = ols([(p[0], p[1]) for p in credible])
ranked = sorted(((abs(p[1] - (a * p[0] + b)), p) for p in credible), key=lambda x: -x[0])
print("\n  C 잔차 상위:", [(f"{r:.1f}", p[3][:10]) for r, p in ranked[:4]])
report("D. C 에서 잔차 상위 2점 추가 제외", [p for _, p in ranked[2:]], 0)

# 8/13 이 유일한 고농도 점이다. 빼면 기울기가 결정되지 않는다는 것을 보인다
report("E. 8/13 제외  (레버리지 확인 — 이 결과는 채택하지 않는다)",
       [p for p in P if not p[3].startswith("2026-08-13")], 0)
