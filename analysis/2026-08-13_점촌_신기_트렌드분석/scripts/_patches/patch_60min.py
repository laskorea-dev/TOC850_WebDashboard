import io, sys
sys.stdout.reconfigure(encoding="utf-8")
p = "template.html"
s = io.open(p, encoding="utf-8").read()

# 1) 희석배수 caveat — 값이 이미 보정되어 있음을 실측으로 확인했으므로 완화
old = """    <div class="caveat">
      <p><b>희석배수가 기간 중에 바뀌었다.</b> 점촌은 07-30 13:53부터 ×1 → ×5,
      신기는 08-05 14:06부터 ×1 → ×20이다. 분석 구간(08-05~)은 양쪽 모두 변경 이후라
      내부 비교에는 영향이 없지만, <b>7월 데이터와 8월 데이터를 한 그래프에서 비교하면 안 된다.</b></p>
    </div>"""
new = """    <div class="caveat">
      <p><b>희석배수 변경은 값에 단차를 남기지 않았다.</b> 점촌은 07-30 13:53부터 ×1 → ×5,
      신기는 08-05 14:06부터 ×1 → ×20이다. 전환 직전·직후 값을 대조하면
      <code>95.91(×1) → 99.23(×5)</code>로 이어져 단차가 없다 —
      <b><code>TOC_Conc</code>는 이미 희석 보정된 값</b>이라는 뜻이다.
      따라서 배수가 다른 기간끼리도 농도 자체는 비교할 수 있다.
      다만 배수가 높을수록 분해능과 저농도 정확도가 떨어지므로 미세한 변동은 조심해서 볼 것.</p>
    </div>"""
assert old in s
s = s.replace(old, new, 1)

# 2) 60분 간격 caveat — 대응 규칙을 실측으로 제시
old2 = """      <p><b>그리고 지금 자료에는 사건을 놓칠 구멍이 있다.</b>
      08-12 20:00 ~ 08-13 11:02 사이 <b>15시간이 통째로 비어 있고</b>,
      08-13부터는 측정 간격이 <b>15분에서 60분으로 바뀌었다.</b>
      상승에 1~1.75시간밖에 안 걸리는 사건은 60분 간격에서는 한 점으로만 잡히거나 통째로 지나간다.
      실제로 08-13 사건은 상승 구간이 표본 2개뿐이라 추세형인지 판정이 가장 약하다.
      <b>측정 간격을 15분으로 되돌리는 것이 먼저다.</b></p>
    </div>"""
new2 = """      <p><b>08-13부터 측정 간격이 15분에서 60분으로 바뀌었다</b>(고객 요청 · 증류수 소비 절감).
      또 08-12 20:00 ~ 08-13 11:02 사이 15시간이 비어 있다.
      이 조건에서 무엇이 남고 무엇이 사라지는지는 아래에서 실측했다.</p>
    </div>

    <div class="card">
      <h3>60분 간격에서도 살아남는 것 — 15분 자료를 솎아 실측</h3>
      <p class="note">
        08-05~08-12의 15분 자료(705점)를 60분으로 솎아 냈다. 어느 분(分)에서 시작하느냐에 따라
        결과가 달라질 수 있으므로 <b>+0 / +15 / +30 / +45분 네 가지 위상을 모두</b> 돌렸다.
      </p>
      <div class="tablewrap">
        <table>
          <thead><tr><th>판정 대상</th><th>15분 원자료</th><th>60분 · 네 위상 전부</th><th>판정</th></tr></thead>
          <tbody>
            <tr><td>일주기 자기상관(24h)</td><td>+0.256</td><td>+0.242 ~ +0.292</td>
              <td><span class="pill lo">영향 없음</span></td></tr>
            <tr><td>최저점 시각</td><td>09시</td><td>08~10시</td>
              <td><span class="pill lo">영향 없음</span></td></tr>
            <tr><td>일주기 진폭</td><td>30.6</td><td>32.6 ~ 35.0</td>
              <td><span class="pill lo">영향 없음</span></td></tr>
            <tr><td>추세형 사건 검출 <b>(연속 2점 규칙)</b></td><td>2건</td><td>4개 위상 모두 2건</td>
              <td><span class="pill lo">전부 검출</span></td></tr>
            <tr><td>단일표본 헌팅 오검출 <b>(연속 2점 규칙)</b></td><td>0건</td><td>4개 위상 모두 0건</td>
              <td><span class="pill lo">전부 걸러짐</span></td></tr>
            <tr><td>단일표본 헌팅 오검출 <b>(1점 규칙)</b></td><td>2건</td><td>위상에 따라 0~1건</td>
              <td><span class="pill hi">쓰지 말 것</span></td></tr>
            <tr><td>상승 속도 · 파형 모양</td><td>2~8점으로 판정</td><td>사건당 2~3점</td>
              <td><span class="pill hi">정량 불가</span></td></tr>
          </tbody>
        </table>
      </div>
      <p class="note">
        <b>일주기 분석은 60분에서도 그대로다.</b> 하루 24점이면 24시간 주기를 잡는 데 충분하고,
        자기상관·위상·진폭 어느 것도 의미 있게 변하지 않았다.
        <b>사건 검출도 규칙만 바꾸면 유지된다</b> — 모양(단조 증가) 대신
        <b>지속성(100 초과가 연속 2점 = 최소 1시간)</b>으로 판정하면
        네 위상 전부에서 추세형 2건을 다 잡고 헌팅 2건을 다 걸렀다.
        <b>잃는 것은 사건의 크기와 모양을 정량하는 능력 하나</b>다.
      </p>
    </div>"""
assert old2 in s
s = s.replace(old2, new2, 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
pl = io.open("payload.json", encoding="utf-8").read()
out = s.replace("__PAYLOAD__", pl)
io.open("toc_analysis.html", "w", encoding="utf-8", newline="\n").write(out)
io.open("preview.html", "w", encoding="utf-8", newline="\n").write(
    '<!doctype html><html><head><meta charset="utf-8"></head><body>' + out + "</body></html>")
print("ok")
