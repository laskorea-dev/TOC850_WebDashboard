import io, sys
sys.stdout.reconfigure(encoding="utf-8")
p = "template.html"
s = io.open(p, encoding="utf-8").read()

old = """    const t = el("text", { class: "dlabel", x: W - R + 6, y: Y(e.peak) + 4, fill: color }, svg);
    t.textContent = e.label;
  });
}"""
new = """    labels.push({ y: Y(e.peak) + 4, text: e.label, color });
  });

  // 라벨 겹침 방지 — 위에서 아래로 최소 15px 간격 확보
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    if (labels[i].y < labels[i - 1].y + 15) labels[i].y = labels[i - 1].y + 15;
  }
  labels.forEach(l => {
    const t = el("text", { class: "dlabel", x: W - R + 6, y: l.y, fill: l.color }, svg);
    t.textContent = l.text;
  });
}"""
assert old in s
s = s.replace(old, new, 1)

old2 = "  ev.forEach(e => {\n    const trend = e.kind === \"trend\";"
new2 = "  const labels = [];\n  ev.forEach(e => {\n    const trend = e.kind === \"trend\";"
assert old2 in s
s = s.replace(old2, new2, 1)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
pl = io.open("payload.json", encoding="utf-8").read()
out = s.replace("__PAYLOAD__", pl)
io.open("toc_analysis.html", "w", encoding="utf-8", newline="\n").write(out)
io.open("preview.html", "w", encoding="utf-8", newline="\n").write(
    '<!doctype html><html><head><meta charset="utf-8"></head><body>' + out + "</body></html>")
print("ok")
