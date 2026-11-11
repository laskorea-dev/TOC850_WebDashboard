// 차트 선 색상 매핑 (채널명 기준 고정색)
export const LINE_COLORS = {
  '방류수': '#ff9f43',
  '유입수': '#00f2fe',
  '고농도': '#a55eea',
  '방류수 (Effluent)': '#ff9f43',
  '유입수 (Influent)': '#00f2fe',
  '1차처리 (Primary)': '#a55eea',
  '냉각수 (Cooling Water)': '#10b981',
  '기타 채널': '#a0a5b5'
};

// 고정색이 없는 채널명(예: 울산1공장 DW·CW·AW)에 채널 번호 순으로 나눠 줄 색
const FALLBACK_PALETTE = ['#00f2fe', '#ff9f43', '#a55eea', '#10b981', '#f43f5e', '#facc15', '#3b82f6', '#ec4899'];

/**
 * 차트에 나오는 채널명마다 선 색을 정한다.
 * - LINE_COLORS 에 있는 채널명은 지금까지와 같은 고정색.
 * - 고정색이 없는 채널명이 2개 이상이면 채널 번호 순으로 FALLBACK_PALETTE 에서
 *   아직 안 쓴 색을 하나씩 준다. (예전엔 모두 회색이라 범례 구분이 안 됐다)
 * - 고정색 없는 채널명이 1개뿐이면 예전처럼 '기타 채널' 회색을 유지한다.
 *   (단일 채널 사이트 화면이 바뀌지 않게)
 */
export function buildChannelColorMap(channelNames, nameToId = {}) {
  const colors = {};
  const unknown = [];
  channelNames.forEach(name => {
    if (LINE_COLORS[name]) colors[name] = LINE_COLORS[name];
    else unknown.push(name);
  });

  if (unknown.length <= 1) {
    unknown.forEach(name => { colors[name] = LINE_COLORS['기타 채널']; });
    return colors;
  }

  const used = new Set(Object.values(colors));
  const available = FALLBACK_PALETTE.filter(c => !used.has(c));
  const chNum = name => {
    const n = parseInt(nameToId[name], 10);
    return Number.isNaN(n) ? Number.MAX_SAFE_INTEGER : n;
  };
  const ordered = [...unknown].sort((a, b) => chNum(a) - chNum(b) || String(a).localeCompare(String(b)));
  ordered.forEach((name, i) => {
    colors[name] = available.length ? available[i % available.length] : LINE_COLORS['기타 채널'];
  });
  return colors;
}
