import io, sys
sys.stdout.reconfigure(encoding="utf-8")
p = "template.html"
s = io.open(p, encoding="utf-8").read()

anchor = """  <section>
    <h2>일자별 주간 / 야간</h2>"""

new = """  <section>
    <h2>점촌의 100 초과 — 헌팅인가, 실제 부하인가</h2>
    <p class="note">
      현장에서 "유입수가 100을 넘는다고 생각해 본 적이 없다"는 이야기가 나왔다.
      9일간 100 mg/L 이상은 표본 22건(3.1%), 사건으로 묶으면 5건이다.
      그런데 이 5건은 <b>모양이 두 종류로 확연히 갈린다.</b>
    </p>

    <div class="card">
      <div class="chart-head">
        <h3>피크 시각을 0으로 맞춰 겹친 것</h3>
        <span class="unit">가로축 = 피크로부터의 시간 · mg/L</span>
      </div>
      <div class="legend">
        <span><i class="swatch" style="background:var(--s1)"></i>추세형 — 여러 표본에 걸쳐 오르고 내린다</span>
        <span><i class="swatch" style="background:var(--muted)"></i>단일표본형 — 한 점만 튀고 곧바로 복귀</span>
      </div>
      <div class="plot" id="p-events"></div>
    </div>

    <div class="tablewrap">
      <table>
        <thead><tr>
          <th>사건</th><th>유형</th><th>피크</th><th>발치</th>
          <th>상승 시간</th><th>상승 속도</th><th>하강 속도</th><th>상승 표본수</th>
        </tr></thead>
        <tbody id="t-events"></tbody>
      </table>
    </div>

    <p class="note">
      <b>헌팅이 아니라는 판단은 데이터로 뒷받침된다.</b> 추세형 3건은 상승에 1.0~1.75시간,
      즉 <b>연속된 2~8개 표본</b>을 쓰며 그 사이 단 한 번도 뒤집히지 않는다(단조 증가).
      하강도 마찬가지로 매끈하다. 계측기 헌팅이나 기포·이물은 이렇게 움직이지 않는다 —
      단일표본형 2건이 그 대조군이다. 15분 만에 622 mg/L/h로 치솟았다 곧장 복귀한다.
    </p>

    <div class="cards">
      <div class="tile">
        <span class="k">추세형 상승 속도</span>
        <span class="v" style="color:var(--s1)">43~88</span>
        <span class="s">mg/L·h · 2~8개 표본에 걸침</span>
      </div>
      <div class="tile">
        <span class="k">단일표본형 상승 속도</span>
        <span class="v" style="color:var(--muted)">203~622</span>
        <span class="s">mg/L·h · 표본 1개 · 즉시 복귀</span>
      </div>
      <div class="tile">
        <span class="k">상승 : 하강 비대칭</span>
        <span class="v" style="color:var(--s1)">3~7배</span>
        <span class="s">빠르게 들어오고 천천히 빠진다</span>
      </div>
      <div class="tile">
        <span class="k">피크 시각 집중도</span>
        <span class="v" style="color:var(--s1)">R 0.89</span>
        <span class="s">5건 전부 10:57~16:30 · 평균 14.2시</span>
      </div>
    </div>

    <h3 style="margin-top:8px">주기가 있는가 — 답은 "아직 모른다", 그러나 무작위도 아니다</h3>

    <p class="note">
      추세형 3건의 발생 간격은 <b>5.0일, 2.9일</b>이다. 두 값이 다르므로 <b>주기라고 말할 수 없다.</b>
      사건이 3개뿐이라 어떤 통계도 이 표본 수를 이겨내지 못한다. 여기서 주기를 주장하면
      그건 데이터가 아니라 희망이다.
    </p>

    <p class="note">
      다만 <b>시각은 분명히 잠겨 있다.</b> 5건 모두 10:57~16:30 사이에서 터졌고 평균이 14.2시다.
      하루 중 이 5.6시간대에 들어 있는 표본은 전체의 26%뿐이므로, 5건이 모두 우연히
      여기 몰릴 확률은 <b>약 0.03%</b>다. 발생 날짜는 불규칙한데 발생 시각은 규칙적이다 —
      이것은 "주기"가 아니라 <b>위상 고정</b>이고, 성격이 전혀 다르다.
    </p>

    <div class="finding" style="border-bottom:1px solid var(--rule)">
      <div class="tag">해석</div>
      <p>
        연속 배출원이라면 농도가 이런 식으로 오르내리지 않는다. <strong>매일은 아니지만 터지면
        반드시 오후</strong>이고, <strong>빠르게 들어와 천천히 빠지는</strong> 비대칭 파형이다.
        이 둘을 같이 놓으면 <strong>간헐적인 배치성 유입</strong> — 사람이 시간을 정해 무언가를
        내보내는 행위 — 이 가장 자연스러운 설명이다. 관로를 타고 오는 동안 퍼지기 때문에
        하강이 상승보다 느리다.
      </p>
    </div>

    <p class="note">
      유량 자료 없이 원인을 특정하는 것은 이쪽 영역이 아니다. 다만 고객이 확인해 볼 만한 방향은
      좁힐 수 있다. <b>오후 시간대에 기록이 남는 반입·배출 행위</b>를 대조해 보는 것이다 —
      분뇨·정화조 수거차량 반입 대장, 관내 사업장의 배치 배출, 펌프장 강제 이송이나 관로 청소 일정.
      날짜만 맞춰 보면 대조는 몇 분이면 끝난다. 맞아떨어지면 원인이 특정되고,
      아니어도 후보 하나가 지워진다.
    </p>

    <div class="caveat">
      <p><b>이 결론을 굳히려면 자료가 더 필요하다. 기간이 아니라 사건 수가 문제다.</b>
      9일에 3건이면 한 달을 더 봐도 10건 남짓이다. 간격의 규칙성을 검정하려면 최소 그 정도는 있어야 한다.</p>
      <p><b>그리고 지금 자료에는 사건을 놓칠 구멍이 있다.</b>
      08-12 20:00 ~ 08-13 11:02 사이 <b>15시간이 통째로 비어 있고</b>,
      08-13부터는 측정 간격이 <b>15분에서 60분으로 바뀌었다.</b>
      상승에 1~1.75시간밖에 안 걸리는 사건은 60분 간격에서는 한 점으로만 잡히거나 통째로 지나간다.
      실제로 08-13 사건은 상승 구간이 표본 2개뿐이라 추세형인지 판정이 가장 약하다.
      <b>측정 간격을 15분으로 되돌리는 것이 먼저다.</b></p>
    </div>
  </section>

  <section>
    <h2>일자별 주간 / 야간</h2>"""

assert anchor in s
s = s.replace(anchor, new, 1)

hook = 'hourlyChart("p-hourly");'
chart = r'''/* ---------- 100 초과 사건 겹치기 ---------- */
function eventChart(id) {
  const host = document.getElementById(id);
  const W = 1000, H = 340, L = 46, R = 120, T = 16, B = 36;
  const svg = makeSvg(host, W, H), tip = tipFor(host);
  const ev = DATA.events;
  const ymax = niceMax(Math.max(...ev.flatMap(e => e.pts.map(p => p[1]))));
  const xlo = -3, xhi = 5;
  const X = h => L + (h - xlo) / (xhi - xlo) * (W - L - R);
  const Y = v => T + (H - T - B) * (1 - v / ymax);

  for (let i = 0; i <= 4; i++) {
    const g = ymax * i / 4;
    el("line", { class: "grid-line", x1: L, x2: W - R, y1: Y(g), y2: Y(g) }, svg);
    const t = el("text", { class: "tick", x: L - 8, y: Y(g) + 4, "text-anchor": "end" }, svg);
    t.textContent = g;
  }
  el("line", { class: "axis-line", x1: X(0), x2: X(0), y1: T, y2: H - B, "stroke-dasharray": "3 5" }, svg);
  for (let h = xlo; h <= xhi; h++) {
    const t = el("text", { class: "tick", x: X(h), y: H - 12, "text-anchor": "middle" }, svg);
    t.textContent = (h > 0 ? "+" : "") + h + "h";
  }
  el("line", { class: "axis-line", x1: L, x2: W - R, y1: Y(100), y2: Y(100), "stroke-dasharray": "2 4" }, svg);
  const th = el("text", { class: "tick", x: W - R + 6, y: Y(100) + 4 }, svg);
  th.textContent = "100";

  ev.forEach(e => {
    const trend = e.kind === "trend";
    const color = trend ? "var(--s1)" : "var(--muted)";
    const pts = e.pts.filter(p => p[0] >= xlo && p[0] <= xhi);
    const d = pts.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + " " + Y(p[1]).toFixed(1)).join(" ");
    el("path", {
      d, fill: "none", stroke: color, "stroke-width": trend ? 2 : 1.6,
      "stroke-linejoin": "round", "stroke-dasharray": trend ? "" : "5 4",
      opacity: trend ? 0.92 : 0.75
    }, svg);
    pts.forEach(p => {
      const c = el("circle", { cx: X(p[0]), cy: Y(p[1]), r: trend ? 3.2 : 2.6,
        fill: color, stroke: "var(--surface)", "stroke-width": 1.4 }, svg);
      c.addEventListener("pointerenter", () => {
        tip.innerHTML = "<b>" + e.label + "</b><br>" + p[1].toFixed(1) + " mg/L<br>피크 "
          + (p[0] > 0 ? "+" : "") + p[0].toFixed(2) + "h";
        tip.classList.add("on");
        const r = svg.getBoundingClientRect();
        place(tip, host, X(p[0]) * r.width / W, Y(p[1]) * r.height / H);
      });
      c.addEventListener("pointerleave", () => tip.classList.remove("on"));
    });
    const t = el("text", { class: "dlabel", x: W - R + 6, y: Y(e.peak) + 4, fill: color }, svg);
    t.textContent = e.label;
  });
}

function eventTable(id) {
  document.getElementById(id).innerHTML = DATA.events.map(e =>
    "<tr><td>" + e.label + "</td>"
    + "<td><span class=\"pill " + (e.kind === "trend" ? "hi" : "lo") + "\">"
    + (e.kind === "trend" ? "추세형" : "단일표본") + "</span></td>"
    + "<td>" + e.peak.toFixed(1) + "</td><td>" + e.foot.toFixed(1) + "</td>"
    + "<td>" + e.riseH + "h</td><td>" + e.riseRate + "</td>"
    + "<td>" + e.fallRate + "</td><td>" + e.nRise + "</td></tr>").join("");
}

hourlyChart("p-hourly");
eventChart("p-events");
eventTable("t-events");'''

assert hook in s
s = s.replace(hook, chart, 1)
io.open(p, "w", encoding="utf-8", newline="\n").write(s)

pl = io.open("payload.json", encoding="utf-8").read()
out = s.replace("__PAYLOAD__", pl)
io.open("toc_analysis.html", "w", encoding="utf-8", newline="\n").write(out)
io.open("preview.html", "w", encoding="utf-8", newline="\n").write(
    '<!doctype html><html><head><meta charset="utf-8"></head><body>' + out + "</body></html>")
print("ok")
