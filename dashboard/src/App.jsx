import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  LineChart,
  Line,
  Brush
} from 'recharts';

// =========================================================================
// Supabase 연결 설정
// =========================================================================
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "https://abfjmqnurtjfbflquqsp.supabase.co/rest/v1/";
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiZmptcW51cnRqZmJmbHF1cXNwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTg3MjM4OCwiZXhwIjoyMDk1NDQ4Mzg4fQ.ejErBBFUNYlzBBCM0rLi_1mx49tuXQY_XArRuQ5dG0c";
const SUPABASE_TABLE = import.meta.env.VITE_SUPABASE_TABLE || "Samyang_Incheon";
const PAGE_SIZE = 1000; // Supabase 기본 limit

// 차트 선 색상 매핑
const LINE_COLORS = {
  '방류수': '#ff9f43',
  '유입수': '#00f2fe',
  '고농도': '#a55eea',
  '방류수 (Effluent)': '#ff9f43',
  '유입수 (Influent)': '#00f2fe',
  '1차처리 (Primary)': '#a55eea',
  '냉각수 (Cooling Water)': '#10b981',
  '기타 채널': '#a0a5b5'
};

// 데이터 표준화 헬퍼
const normalizeData = (items) => {
  if (!Array.isArray(items)) return [];
  return items.map(item => {
    const tocVal = parseFloat(item.TOC_Conc);
    const channelNum = parseInt(item.Channel);

    // DB Channel_Name 우선 사용, 깨진 문자(Լ 등)일 때만 폴백
    let resolvedChannelName = item.Channel_Name;
    if (!resolvedChannelName || resolvedChannelName === '' || resolvedChannelName.includes('Լ')) {
      const fallbackMap = { 1: '방류수', 2: '유입수', 3: '고농도', 4: '냉각수' };
      resolvedChannelName = fallbackMap[channelNum] || `채널 ${channelNum}`;
    }

    return {
      Date_Time: item.Date_Time,
      Device_ID: item.Device_ID || 'DEVICE_01',
      Channel: channelNum,
      Channel_Name: resolvedChannelName,
      TOC_Conc: isNaN(tocVal) ? 0 : tocVal,
      DilutionFactor: parseFloat(item.DilutionFactor) || 1.0,
      MSIG: parseFloat(item.MSIG) || 0.0,
      SLOP: parseFloat(item.SLOP) || 0.0,
      ICPT: parseFloat(item.ICPT) || 0.0,
      FACT: parseFloat(item.FACT) || 0.0,
      OFST: parseFloat(item.OFST) || 0.0,
      MAXR: parseInt(item.MAXR) || 200,
      Add_note: item.Add_note || ''
    };
  });
};

// 날짜 파싱 유틸 (YYYY-MM-DD HH:MM:SS → Date)
const parseDate = (dateStr) => {
  if (!dateStr) return new Date(0);
  return new Date(dateStr.replace(/-/g, '/'));
};

// ISO datetime-local 포맷 (input용)
const toDatetimeLocal = (date) => {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState('');
  const [error, setError] = useState(null);

  // 보안 접속
  const [passcode, setPasscode] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [loginError, setLoginError] = useState(false);

  // 트렌드 차트 필터
  const [selectedAttr, setSelectedAttr] = useState('TOC_Conc');
  const [timeRange, setTimeRange] = useState('7d');
  const [customStart, setCustomStart] = useState('');
  const [customEnd, setCustomEnd] = useState('');

  // 차트 채널 표시/숨김 토글
  const [hiddenChannels, setHiddenChannels] = useState(new Set());

  // 테이블 필터
  const [tableChannelFilter, setTableChannelFilter] = useState('All');
  const [tableTocMin, setTableTocMin] = useState('');
  const [tableTocMax, setTableTocMax] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(50);

  // =========================================================================
  // Supabase 페이지네이션 Fetch — 전체 레코드 가져오기
  // =========================================================================
  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);
    setLoadProgress('연결 중...');
    try {
      if (!SUPABASE_URL || !SUPABASE_KEY) {
        throw new Error('Supabase 연결 정보가 설정되지 않았습니다.');
      }

      const baseUrl = SUPABASE_URL.replace(/\/$/, '');
      const endpoint = baseUrl.includes('/rest/v1')
        ? `${baseUrl}/${SUPABASE_TABLE}`
        : `${baseUrl}/rest/v1/${SUPABASE_TABLE}`;

      let allData = [];
      let from = 0;
      let hasMore = true;

      while (hasMore) {
        const to = from + PAGE_SIZE - 1;
        setLoadProgress(`${allData.length.toLocaleString()}건 로딩 중...`);

        const response = await fetch(
          `${endpoint}?select=*&order=Date_Time.asc`,
          {
            headers: {
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Range': `${from}-${to}`,
              'Prefer': 'count=exact'
            }
          }
        );

        // 206 Partial Content 또는 200 OK 둘 다 처리
        if (!response.ok && response.status !== 206) {
          throw new Error(`Supabase fetch 실패: ${response.status} ${response.statusText}`);
        }

        const chunk = await response.json();

        if (!Array.isArray(chunk) || chunk.length === 0) {
          hasMore = false;
        } else {
          allData = allData.concat(chunk);
          from += PAGE_SIZE;

          // 반환된 건수가 PAGE_SIZE보다 적으면 마지막 페이지
          if (chunk.length < PAGE_SIZE) {
            hasMore = false;
          }
        }
      }

      setLoadProgress(`총 ${allData.length.toLocaleString()}건 로드 완료`);
      const normalized = normalizeData(allData);
      setData(normalized);

      // 데이터 로드 후 커스텀 시간 범위 기본값 설정
      if (normalized.length > 0 && !customStart) {
        const first = parseDate(normalized[0].Date_Time);
        const last = parseDate(normalized[normalized.length - 1].Date_Time);
        setCustomStart(toDatetimeLocal(first));
        setCustomEnd(toDatetimeLocal(last));
      }
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [customStart]);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, []);

  // =========================================================================
  // 전체 데이터에서 사용 가능한 채널 목록
  // =========================================================================
  const allChannels = useMemo(() => {
    const channels = new Set();
    data.forEach(item => channels.add(item.Channel_Name));
    return Array.from(channels).sort();
  }, [data]);

  // =========================================================================
  // 트렌드 차트용 시간 필터링된 데이터
  // =========================================================================
  const trendFilteredData = useMemo(() => {
    if (data.length === 0) return [];

    const lastDate = parseDate(data[data.length - 1].Date_Time);

    return data.filter(item => {
      const itemDate = parseDate(item.Date_Time);

      if (timeRange === '24h') {
        return (lastDate - itemDate) <= 24 * 60 * 60 * 1000;
      } else if (timeRange === '7d') {
        return (lastDate - itemDate) <= 7 * 24 * 60 * 60 * 1000;
      } else if (timeRange === '30d') {
        return (lastDate - itemDate) <= 30 * 24 * 60 * 60 * 1000;
      } else if (timeRange === 'custom') {
        const start = customStart ? new Date(customStart) : new Date(0);
        const end = customEnd ? new Date(customEnd) : new Date();
        return itemDate >= start && itemDate <= end;
      }
      // 'All'
      return true;
    });
  }, [data, timeRange, customStart, customEnd]);

  // =========================================================================
  // 동적 버킷 크기 결정 + 다중 채널 시계열 차트 데이터 생성
  // =========================================================================
  const chartData = useMemo(() => {
    if (trendFilteredData.length === 0) return [];

    // 데이터 포인트 수에 따라 버킷 크기 자동 결정
    const dataCount = trendFilteredData.length;
    let bucketMinutes;
    if (dataCount <= 200) {
      bucketMinutes = 15;    // 15분 버킷
    } else if (dataCount <= 1000) {
      bucketMinutes = 30;    // 30분 버킷
    } else if (dataCount <= 3000) {
      bucketMinutes = 60;    // 1시간 버킷
    } else if (dataCount <= 8000) {
      bucketMinutes = 240;   // 4시간 버킷
    } else {
      bucketMinutes = 1440;  // 1일 버킷
    }

    const timeSlots = {};

    trendFilteredData.forEach(item => {
      const d = parseDate(item.Date_Time);
      if (isNaN(d.getTime())) return;

      // 버킷 시간 계산
      const totalMinutes = d.getHours() * 60 + d.getMinutes();
      const bucketStart = Math.floor(totalMinutes / bucketMinutes) * bucketMinutes;
      const bucketHour = String(Math.floor(bucketStart / 60)).padStart(2, '0');
      const bucketMin = String(bucketStart % 60).padStart(2, '0');

      const datePart = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
      const timeBucket = `${datePart} ${bucketHour}:${bucketMin}`;

      if (!timeSlots[timeBucket]) {
        timeSlots[timeBucket] = {
          TimeBucket: timeBucket,
          ShortTime: `${datePart.slice(5)} ${bucketHour}:${bucketMin}`,
          _counts: {}
        };
      }

      const chName = item.Channel_Name;
      const val = selectedAttr === 'TOC_Conc' ? item.TOC_Conc : item.MSIG;

      // 같은 버킷/채널에 여러 값이 있으면 평균 계산
      if (!timeSlots[timeBucket]._counts[chName]) {
        timeSlots[timeBucket]._counts[chName] = { sum: 0, count: 0 };
      }
      timeSlots[timeBucket]._counts[chName].sum += val;
      timeSlots[timeBucket]._counts[chName].count += 1;
    });

    // 평균값 계산 후 _counts 제거
    const result = Object.values(timeSlots).map(slot => {
      const entry = { TimeBucket: slot.TimeBucket, ShortTime: slot.ShortTime };
      for (const [chName, agg] of Object.entries(slot._counts)) {
        entry[chName] = parseFloat((agg.sum / agg.count).toFixed(2));
      }
      return entry;
    });

    return result;
  }, [trendFilteredData, selectedAttr]);

  // 트렌드에 실제 등장하는 채널들
  const trendChannels = useMemo(() => {
    const channels = new Set();
    trendFilteredData.forEach(item => channels.add(item.Channel_Name));
    return Array.from(channels);
  }, [trendFilteredData]);

  // 현재 표시 중인 채널들 (숨긴 채널 제외)
  const visibleChannels = useMemo(() => {
    return trendChannels.filter(ch => !hiddenChannels.has(ch));
  }, [trendChannels, hiddenChannels]);

  // Y축 도메인: 표시 중인 채널 데이터만 기준으로 오토스케일
  const yDomain = useMemo(() => {
    if (visibleChannels.length === 0 || chartData.length === 0) return ['auto', 'auto'];
    let min = Infinity;
    let max = -Infinity;
    chartData.forEach(slot => {
      visibleChannels.forEach(ch => {
        const val = slot[ch];
        if (val !== undefined && val !== null) {
          if (val < min) min = val;
          if (val > max) max = val;
        }
      });
    });
    if (min === Infinity) return ['auto', 'auto'];
    // 상하 5% 여백
    const padding = (max - min) * 0.05 || 1;
    return [Math.max(0, Math.floor(min - padding)), Math.ceil(max + padding)];
  }, [visibleChannels, chartData]);

  // 범례 클릭 핸들러: 채널 표시/숨김 토글
  const handleLegendClick = useCallback((entry) => {
    const chName = entry.dataKey || entry.value;
    setHiddenChannels(prev => {
      const next = new Set(prev);
      if (next.has(chName)) {
        next.delete(chName);
      } else {
        // 최소 1개는 표시
        if (trendChannels.length - next.size > 1) {
          next.add(chName);
        }
      }
      return next;
    });
  }, [trendChannels]);

  // 데이터 시간 범위 표시
  const dataTimeRange = useMemo(() => {
    if (trendFilteredData.length === 0) return '';
    const first = trendFilteredData[0].Date_Time;
    const last = trendFilteredData[trendFilteredData.length - 1].Date_Time;
    return `${first} ~ ${last}`;
  }, [trendFilteredData]);

  // =========================================================================
  // 테이블용 필터링 + 정렬 (최근 데이터 먼저)
  // =========================================================================
  const tableFilteredData = useMemo(() => {
    return data.filter(item => {
      // 채널 필터
      if (tableChannelFilter !== 'All' && item.Channel_Name !== tableChannelFilter) {
        return false;
      }
      // TOC 농도 범위 필터
      if (tableTocMin !== '' && item.TOC_Conc < parseFloat(tableTocMin)) {
        return false;
      }
      if (tableTocMax !== '' && item.TOC_Conc > parseFloat(tableTocMax)) {
        return false;
      }
      // 텍스트 검색
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        const match = item.Date_Time.toLowerCase().includes(q)
          || item.Channel_Name.toLowerCase().includes(q)
          || item.Device_ID.toLowerCase().includes(q)
          || item.Add_note.toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    }).sort((a, b) => {
      // 최근 데이터 먼저 (desc)
      return parseDate(b.Date_Time) - parseDate(a.Date_Time);
    });
  }, [data, tableChannelFilter, tableTocMin, tableTocMax, searchQuery]);

  // CSV 다운로드
  const downloadCSV = useCallback(() => {
    if (tableFilteredData.length === 0) return;
    const headers = ['Date_Time','Device_ID','Channel','Channel_Name','TOC_Conc','DilutionFactor','MSIG','SLOP','ICPT','FACT','OFST','Add_note'];
    const rows = [headers.join(',')];
    tableFilteredData.forEach(r => {
      rows.push([
        r.Date_Time, r.Device_ID, r.Channel, `"${r.Channel_Name}"`,
        r.TOC_Conc, r.DilutionFactor, r.MSIG, r.SLOP, r.ICPT, r.FACT, r.OFST,
        `"${(r.Add_note || '').replace(/"/g, '""')}"`
      ].join(','));
    });
    const blob = new Blob(['\uFEFF' + rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `TOC_Data_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }, [tableFilteredData]);

  // 테이블 페이징
  const totalPages = Math.ceil(tableFilteredData.length / itemsPerPage);
  const paginatedData = tableFilteredData.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  // 페이지 초기화 (필터 변경 시)
  useEffect(() => {
    setCurrentPage(1);
  }, [tableChannelFilter, tableTocMin, tableTocMax, searchQuery, itemsPerPage]);

  // =========================================================================
  // 보안 접속 화면
  // =========================================================================
  if (!isUnlocked) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-primary)',
        fontFamily: 'var(--font-body)',
        color: 'var(--text-main)',
        padding: '20px'
      }}>
        <div className="glass-card" style={{ maxWidth: '400px', width: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}>LAS TOC-850 보안 접속</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>대시보드 열람을 위해 보안 코드를 입력해 주세요.</p>
          <input
            type="password"
            placeholder="보안 코드 입력..."
            className="custom-select"
            style={{ width: '100%', textAlign: 'center', letterSpacing: '8px', fontSize: '1.2rem', cursor: 'text' }}
            value={passcode}
            onChange={(e) => { setPasscode(e.target.value); setLoginError(false); }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                if (passcode === '850') setIsUnlocked(true);
                else setLoginError(true);
              }
            }}
          />
          {loginError && <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>올바르지 않은 코드입니다. 다시 시도해 주세요.</p>}
          <button
            className="sim-btn"
            style={{ width: '100%' }}
            onClick={() => {
              if (passcode === '850') setIsUnlocked(true);
              else setLoginError(true);
            }}
          >
            대시보드 접속 🔑
          </button>
        </div>
      </div>
    );
  }

  // =========================================================================
  // 메인 대시보드
  // =========================================================================
  return (
    <div className="dashboard-container">
      {/* HEADER */}
      <header className="dashboard-header">
        <div className="header-title-section">
          <h1>LAS TOC-850 온라인 계측 모니터링 대시보드</h1>
          <p>LAS KOREA 제공 · 총 {data.length.toLocaleString()}건 수집</p>
        </div>
        <div className="header-controls">
          <button className="filter-btn active" onClick={loadData}>
            {loading ? '로딩 중...' : '새로고침 🔄'}
          </button>
        </div>
      </header>

      {/* LOADING / ERROR */}
      {loading && data.length === 0 ? (
        <div className="glass-card empty-placeholder">
          <div className="status-dot" style={{ width: '40px', height: '40px' }}></div>
          <h2>데이터 로딩 중...</h2>
          <p>{loadProgress}</p>
        </div>
      ) : error && data.length === 0 ? (
        <div className="glass-card empty-placeholder" style={{ borderColor: 'var(--accent-rose)' }}>
          <h2 style={{ color: 'var(--accent-rose)' }}>클라우드 연결 오류</h2>
          <p>{error}</p>
          <button className="sim-btn" style={{ background: 'var(--accent-rose)' }} onClick={loadData}>연결 재시도 🔄</button>
        </div>
      ) : (
        <>
          {/* ============================================ */}
          {/* TOC & Signal Multi-Series Trend              */}
          {/* ============================================ */}
          <section className="glass-card chart-card">
            <div className="chart-header">
              <div>
                <h3 className="chart-title">TOC & Signal Multi-Series Trend</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', marginTop: '4px' }}>
                  {dataTimeRange && `📅 ${dataTimeRange}`}
                  {trendFilteredData.length > 0 && ` · ${trendFilteredData.length.toLocaleString()}건`}
                </p>
              </div>

              <div className="header-controls" style={{ gap: '8px', flexWrap: 'wrap' }}>
                {/* TOC / MSIG 전환 */}
                <div className="filter-button-group">
                  <button
                    className={`filter-btn ${selectedAttr === 'TOC_Conc' ? 'active' : ''}`}
                    onClick={() => setSelectedAttr('TOC_Conc')}
                  >
                    TOC 농도
                  </button>
                  <button
                    className={`filter-btn ${selectedAttr === 'MSIG' ? 'active' : ''}`}
                    onClick={() => setSelectedAttr('MSIG')}
                  >
                    MSIG
                  </button>
                </div>

                {/* 시간 범위 드롭다운 */}
                <select
                  className="custom-select"
                  style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                  value={timeRange}
                  onChange={(e) => setTimeRange(e.target.value)}
                >
                  <option value="24h">최근 24시간</option>
                  <option value="7d">최근 7일</option>
                  <option value="30d">최근 30일</option>
                  <option value="All">전체 기간</option>
                  <option value="custom">직접 지정</option>
                </select>
              </div>
            </div>

            {/* 커스텀 시간 범위 입력 */}
            {timeRange === 'custom' && (
              <div className="custom-time-range">
                <label>
                  <span>시작</span>
                  <input
                    type="datetime-local"
                    className="custom-select datetime-input"
                    value={customStart}
                    onChange={(e) => setCustomStart(e.target.value)}
                  />
                </label>
                <span className="time-range-separator">~</span>
                <label>
                  <span>종료</span>
                  <input
                    type="datetime-local"
                    className="custom-select datetime-input"
                    value={customEnd}
                    onChange={(e) => setCustomEnd(e.target.value)}
                  />
                </label>
              </div>
            )}

            {/* 채널 토글 칩 */}
            <div className="channel-chips">
              {trendChannels.map(chName => {
                const isHidden = hiddenChannels.has(chName);
                const color = LINE_COLORS[chName] || LINE_COLORS['기타 채널'];
                return (
                  <button
                    key={chName}
                    className={`channel-chip ${isHidden ? 'hidden' : ''}`}
                    style={{
                      '--chip-color': color,
                      borderColor: isHidden ? 'var(--border-color)' : color,
                      background: isHidden ? 'transparent' : `${color}15`
                    }}
                    onClick={() => handleLegendClick({ dataKey: chName })}
                  >
                    <span className="chip-dot" style={{ background: isHidden ? 'var(--text-muted)' : color }}></span>
                    {chName}
                  </button>
                );
              })}
              {hiddenChannels.size > 0 && (
                <button
                  className="channel-chip reset-chip"
                  onClick={() => setHiddenChannels(new Set())}
                >
                  전체 표시
                </button>
              )}
            </div>

            <div style={{ width: '100%', height: 420 }}>
              {chartData.length === 0 ? (
                <div className="empty-placeholder" style={{ padding: '40px 0' }}>
                  <p>선택한 조건에 부합하는 시계열 데이터가 없습니다.</p>
                </div>
              ) : (
                <ResponsiveContainer>
                  <LineChart data={chartData} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                    <XAxis
                      dataKey="ShortTime"
                      stroke="var(--text-muted)"
                      fontSize={11}
                      interval="preserveStartEnd"
                      tickCount={8}
                    />
                    <YAxis
                      stroke="var(--text-muted)"
                      fontSize={11}
                      domain={yDomain}
                      allowDataOverflow={true}
                    />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: 'var(--bg-tertiary)',
                        borderColor: 'var(--border-hover)',
                        borderRadius: '8px',
                        color: 'var(--text-main)'
                      }}
                    />
                    {trendChannels.map(chName => (
                      <Line
                        key={chName}
                        type="monotone"
                        dataKey={chName}
                        name={chName}
                        stroke={LINE_COLORS[chName] || LINE_COLORS['기타 채널']}
                        strokeWidth={hiddenChannels.has(chName) ? 0 : 2}
                        dot={!hiddenChannels.has(chName) && chartData.length <= 100 ? { r: 3, strokeWidth: 1 } : false}
                        activeDot={hiddenChannels.has(chName) ? false : { r: 5 }}
                        connectNulls={true}
                        hide={hiddenChannels.has(chName)}
                      />
                    ))}
                    {chartData.length > 20 && (
                      <Brush
                        dataKey="ShortTime"
                        height={28}
                        stroke="var(--accent-cyan)"
                        fill="var(--bg-tertiary)"
                        travellerWidth={10}
                      />
                    )}
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          {/* ============================================ */}
          {/* 측정 이력 상세 데이터                         */}
          {/* ============================================ */}
          <section className="glass-card table-card">
            <div className="chart-header">
              <div>
                <h3 className="chart-title">측정 이력 상세 데이터</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  총 {data.length.toLocaleString()}건 중 {tableFilteredData.length.toLocaleString()}건 조회
                </p>
              </div>
              <button className="filter-btn active" onClick={downloadCSV} disabled={tableFilteredData.length === 0}>
                CSV 다운로드 📥
              </button>
            </div>

            {/* 테이블 필터 바 */}
            <div className="table-filters">
              <div className="filter-group">
                <label>채널</label>
                <select
                  className="custom-select"
                  value={tableChannelFilter}
                  onChange={(e) => setTableChannelFilter(e.target.value)}
                >
                  <option value="All">전체 채널</option>
                  {allChannels.map(ch => (
                    <option key={ch} value={ch}>{ch}</option>
                  ))}
                </select>
              </div>

              <div className="filter-group">
                <label>TOC 최소</label>
                <input
                  type="number"
                  className="custom-select"
                  placeholder="예: 0"
                  value={tableTocMin}
                  onChange={(e) => setTableTocMin(e.target.value)}
                  style={{ width: '100px' }}
                />
              </div>

              <div className="filter-group">
                <label>TOC 최대</label>
                <input
                  type="number"
                  className="custom-select"
                  placeholder="예: 100"
                  value={tableTocMax}
                  onChange={(e) => setTableTocMax(e.target.value)}
                  style={{ width: '100px' }}
                />
              </div>

              <div className="filter-group">
                <label>검색</label>
                <input
                  type="text"
                  className="custom-select"
                  placeholder="날짜, 채널, 비고..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ width: '180px' }}
                />
              </div>

              <div className="filter-group">
                <label>페이지당</label>
                <select
                  className="custom-select"
                  value={itemsPerPage}
                  onChange={(e) => setItemsPerPage(Number(e.target.value))}
                >
                  <option value={25}>25건</option>
                  <option value={50}>50건</option>
                  <option value={100}>100건</option>
                </select>
              </div>
            </div>

            {/* 데이터 테이블 */}
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>측정 일시</th>
                    <th>장비 ID</th>
                    <th>채널</th>
                    <th>채널 이름</th>
                    <th>TOC 농도</th>
                    <th>희석 배수</th>
                    <th>MSIG</th>
                    <th>비고</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedData.length === 0 ? (
                    <tr>
                      <td colSpan="8" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                        필터 조건에 부합하는 데이터가 없습니다.
                      </td>
                    </tr>
                  ) : (
                    paginatedData.map((row, index) => (
                      <tr key={index}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 600, whiteSpace: 'nowrap' }}>{row.Date_Time}</td>
                        <td style={{ color: 'var(--accent-cyan)', fontWeight: 600, fontFamily: 'monospace' }}>{row.Device_ID}</td>
                        <td>{row.Channel}</td>
                        <td style={{ fontWeight: 500 }}>{row.Channel_Name}</td>
                        <td style={{ fontWeight: 600 }}>{row.TOC_Conc} ppm</td>
                        <td>{row.DilutionFactor}x</td>
                        <td style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>{row.MSIG}</td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.Add_note}>
                          {row.Add_note}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* 페이징 */}
            {totalPages > 1 && (
              <div className="table-pagination">
                <button
                  className="filter-btn"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(1)}
                >
                  ◀◀
                </button>
                <button
                  className="filter-btn"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                >
                  ◀ 이전
                </button>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                  <strong>{currentPage}</strong> / {totalPages} 페이지
                </span>
                <button
                  className="filter-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                >
                  다음 ▶
                </button>
                <button
                  className="filter-btn"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(totalPages)}
                >
                  ▶▶
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

export default App;
