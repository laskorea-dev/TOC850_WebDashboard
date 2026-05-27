import React, { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
  Cell,
  LineChart,
  Line
} from 'recharts';

// =========================================================================
// [실제 Supabase 무료 클라우드 B2B 연동 가이드]
// Supabase 프로젝트 Settings -> API 탭에서 복사한 주소와 키를 대입하세요.
// 변수가 비어있을 때는 로컬 시뮬레이션 CSV 모드로 안전하게 작동합니다.
// =========================================================================
// B2B 멀티테넌시 지원: Vercel 환경 변수(Environment Variables)에서 우선 조회하며, 없을 경우 현재 기본값으로 자동 폴백합니다.
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "https://abfjmqnurtjfbflquqsp.supabase.co/rest/v1/";
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFiZmptcW51cnRqZmJmbHF1cXNwIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTg3MjM4OCwiZXhwIjoyMDk1NDQ4Mzg4fQ.ejErBBFUNYlzBBCM0rLi_1mx49tuXQY_XArRuQ5dG0c";
const SUPABASE_TABLE = import.meta.env.VITE_SUPABASE_TABLE || "Samyang_Incheon";

// 채널명 깨짐 보정 및 한글 맵핑 테이블
const CHANNEL_NAME_MAP = {
  1: '방류수 (Effluent)',
  2: '유입수 (Influent)',
  3: '1차처리 (Primary)',
  4: '냉각수 (Cooling Water)'
};

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

// 데이터 표준화 및 한글 매핑 헬퍼 함수
const normalizeData = (items) => {
  if (!Array.isArray(items)) return [];
  return items.map(item => {
    const tocVal = parseFloat(item.TOC_Conc);
    const channelNum = parseInt(item.Channel);

    // 디비에서 가져온 채널 이름이 깨끗한 경우(방류수, 유입수, 고농도 등) 우선 사용하여 범례 이름을 완벽 동기화하고,
    // 비어있거나 특수 문자 깨짐(Լ)이 포함된 경우에만 CHANNEL_NAME_MAP으로 자동 폴백 처리합니다.
    let resolvedChannelName = item.Channel_Name;
    if (!resolvedChannelName || resolvedChannelName === '' || resolvedChannelName.includes('Լ')) {
      resolvedChannelName = CHANNEL_NAME_MAP[channelNum] || `채널 ${channelNum}`;
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

function App() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // 보안 접속 패스코드 상태 (눈가리기 식 로그인)
  const [passcode, setPasscode] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [loginError, setLoginError] = useState(false);

  // UI 필터 및 검색 상태
  const [selectedDevice, setSelectedDevice] = useState('All');
  const [selectedAttr, setSelectedAttr] = useState('TOC_Conc'); // TOC_Conc or MSIG (꺾은선 물리속성 토글)
  const [searchQuery, setSearchQuery] = useState('');
  const [timeRange, setTimeRange] = useState('All'); // 24h, 3d, 7d, All (기본값 All로 설정하여 데이터 풍부하게 표출)
  const [sortOrder, setSortOrder] = useState('desc'); // desc, asc
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // 데이터 로드 함수
  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      let fetchedData = [];

      // Supabase 연결 설정이 되어 있는 경우, 클라우드 DB에서 실시간 직접 fetch!
      if (SUPABASE_URL && SUPABASE_KEY) {
        const base_url = SUPABASE_URL.replace(/\/$/, "");
        const fetchUrl = base_url.includes("/rest/v1")
          ? `${base_url}/${SUPABASE_TABLE}?select=*&order=Date_Time.asc`
          : `${base_url}/rest/v1/${SUPABASE_TABLE}?select=*&order=Date_Time.asc`;

        const response = await fetch(fetchUrl, {
          headers: {
            "apikey": SUPABASE_KEY,
            "Authorization": `Bearer ${SUPABASE_KEY}`
          }
        });

        if (!response.ok) {
          throw new Error(`Supabase fetch failed: ${response.status} ${response.statusText}`);
        }

        const rawJson = await response.json();
        fetchedData = normalizeData(rawJson);
      } else {
        // 설정이 없을 시 로컬 퍼블릭 CSV 폴더에서 모의 동기화 데이터 fetch
        const response = await fetch('/mock_google_sheet.csv');
        if (!response.ok) {
          throw new Error(`Failed to load local mock data: ${response.status}`);
        }
        const csvText = await response.text();
        fetchedData = parseCSV(csvText);
      }

      setData(fetchedData);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5 * 60 * 1000); // 5분마다 자동 새로고침
    return () => clearInterval(interval);
  }, []);

  // CSV 파서
  const parseCSV = (text) => {
    const lines = text.split(/\r?\n/);
    if (lines.length < 2) return [];

    const headers = parseCSVLine(lines[0]);
    const rawItems = [];

    for (let i = 1; i < lines.length; i++) {
      if (!lines[i].trim()) continue;
      const values = parseCSVLine(lines[i]);

      if (values.length >= headers.length) {
        const item = {};
        headers.forEach((header, index) => {
          item[header.trim()] = values[index];
        });
        rawItems.push(item);
      }
    }
    return normalizeData(rawItems);
  };

  const parseCSVLine = (line) => {
    const result = [];
    let insideQuote = false;
    let entry = '';

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        insideQuote = !insideQuote;
      } else if (char === ',' && !insideQuote) {
        result.push(entry.trim().replace(/^"|"$/g, ''));
        entry = '';
      } else {
        entry += char;
      }
    }
    result.push(entry.trim().replace(/^"|"$/g, ''));
    return result;
  };

  // CSV 다운로드 기능
  const downloadCSV = () => {
    if (data.length === 0) return;

    const headers = ['Date_Time', 'Device_ID', 'Channel', 'Channel_Name', 'TOC_Conc', 'DilutionFactor', 'MSIG', 'Add_note'];
    const csvRows = [headers.join(',')];

    filteredData.forEach(row => {
      const values = [
        row.Date_Time,
        row.Device_ID,
        row.Channel,
        `"${row.Channel_Name}"`,
        row.TOC_Conc,
        row.DilutionFactor,
        row.MSIG,
        `"${row.Add_note.replace(/"/g, '""')}"`
      ];
      csvRows.push(values.join(','));
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `TOC_B2B_Report_${new Date().toISOString().slice(0, 10)}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 데이터 필터링 (X축 결합 전 원본 필터)
  const filteredData = data.filter(item => {
    // 1. 장비 필터
    if (selectedDevice !== 'All' && item.Device_ID !== selectedDevice) {
      return false;
    }

    // 2. 검색 텍스트 필터
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchDate = item.Date_Time.toLowerCase().includes(query);
      const matchNote = item.Add_note.toLowerCase().includes(query);
      const matchChName = item.Channel_Name.toLowerCase().includes(query);
      const matchDev = item.Device_ID.toLowerCase().includes(query);
      if (!matchDate && !matchNote && !matchChName && !matchDev) return false;
    }

    // 3. 시간 범위 필터
    if (timeRange !== 'All') {
      const itemDate = new Date(item.Date_Time.replace(/-/g, '/'));
      const now = new Date();

      const maxDate = data.length > 0 ? new Date(data[data.length - 1].Date_Time.replace(/-/g, '/')) : now;
      const diffTime = Math.abs(maxDate - itemDate);
      const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

      if (timeRange === '24h' && diffDays > 1) return false;
      if (timeRange === '3d' && diffDays > 3) return false;
      if (timeRange === '7d' && diffDays > 7) return false;
    }

    return true;
  }).sort((a, b) => {
    const dateA = new Date(a.Date_Time.replace(/-/g, '/'));
    const dateB = new Date(b.Date_Time.replace(/-/g, '/'));
    return sortOrder === 'desc' ? dateB - dateA : dateA - dateB;
  });

  // 요약 KPI 연산
  const getStats = () => {
    if (filteredData.length === 0) return { latest: 0, max: 0, avg: 0, count: 0, status: 'Offline' };

    const sortedByTime = [...filteredData].sort((a, b) => new Date(a.Date_Time.replace(/-/g, '/')) - new Date(b.Date_Time.replace(/-/g, '/')));
    const latestItem = sortedByTime[sortedByTime.length - 1];

    const latest = latestItem.TOC_Conc;
    const count = filteredData.length;

    const values = filteredData.map(item => item.TOC_Conc);
    const max = Math.max(...values);
    const avg = parseFloat((values.reduce((sum, val) => sum + val, 0) / count).toFixed(2));

    const latestTime = new Date(latestItem.Date_Time.replace(/-/g, '/'));
    const maxTime = data.length > 0 ? new Date(data[data.length - 1].Date_Time.replace(/-/g, '/')) : new Date();
    const timeDiffMinutes = Math.abs(maxTime - latestTime) / (1000 * 60);
    const status = timeDiffMinutes < 60 ? 'Active' : 'Standby';

    return { latest, max, avg, count, status, latestItem };
  };

  const stats = getStats();

  // 바 차트용 채널 통계 집계
  const getChannelStats = () => {
    const channelGroups = {};
    filteredData.forEach(item => {
      const chName = item.Channel_Name;
      if (!channelGroups[chName]) {
        channelGroups[chName] = { name: chName, sum: 0, max: 0, count: 0 };
      }
      channelGroups[chName].sum += item.TOC_Conc;
      channelGroups[chName].count += 1;
      if (item.TOC_Conc > channelGroups[chName].max) {
        channelGroups[chName].max = item.TOC_Conc;
      }
    });

    return Object.values(channelGroups).map(group => ({
      name: group.name,
      '평균 TOC': parseFloat((group.sum / group.count).toFixed(2)),
      '최대 TOC': parseFloat(group.max.toFixed(2))
    }));
  };

  const channelStats = getChannelStats();

  // =========================================================================
  // [핵심] 다중 채널 시계열 선형 오버랩을 위한 X축 Time-slotting 결합 엔진
  // 시간대별로 번갈아 들어오는 채널 데이터를 단일 버킷(30분/1시간 단위)으로 보간
  // =========================================================================
  const getMultiSeriesChartData = () => {
    if (filteredData.length === 0) return [];

    const timeSlots = {};

    // 시간 오름차순 정렬
    const sorted = [...filteredData].sort((a, b) => new Date(a.Date_Time.replace(/-/g, '/')) - new Date(b.Date_Time.replace(/-/g, '/')));

    sorted.forEach(item => {
      // YYYY-MM-DD HH:MM:SS -> 분 단위를 30분 단위 버킷으로 묶어 엇갈린 측정 시간 축을 결합!
      // 예: 13:33:57 -> 13:30 / 13:48:57 -> 13:30 또는 13:45로 타이트하게 바인딩
      const datePart = item.Date_Time.slice(0, 10);
      const timePart = item.Date_Time.slice(11, 16);
      const hours = parseInt(timePart.slice(0, 2));
      const minutes = parseInt(timePart.slice(3, 5));

      const bucketMinutes = minutes < 30 ? '00' : '30';
      const timeBucket = `${datePart} ${String(hours).padStart(2, '0')}:${bucketMinutes}`;

      if (!timeSlots[timeBucket]) {
        timeSlots[timeBucket] = {
          TimeBucket: timeBucket,
          ShortTime: timeBucket.slice(5),
        };
      }

      const attributeValue = selectedAttr === 'TOC_Conc' ? item.TOC_Conc : item.MSIG;
      timeSlots[timeBucket][item.Channel_Name] = attributeValue;
    });

    return Object.values(timeSlots).slice(-300);
  };

  const chartData = getMultiSeriesChartData();

  // 대시보드 내에 실제로 등장한 모든 채널명 고유 목록
  const getActiveChannels = () => {
    const channels = new Set();
    filteredData.forEach(item => channels.add(item.Channel_Name));
    return Array.from(channels);
  };

  const activeChannels = getActiveChannels();

  // 테이블 페이징
  const totalPages = Math.ceil(filteredData.length / itemsPerPage);
  const paginatedTableData = filteredData.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

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
                if (passcode === '850') {
                  setIsUnlocked(true);
                } else {
                  setLoginError(true);
                }
              }
            }}
          />
          {loginError && <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>올바르지 않은 코드입니다. 다시 시도해 주세요.</p>}
          <button
            className="sim-btn"
            style={{ width: '100%' }}
            onClick={() => {
              if (passcode === '850') {
                setIsUnlocked(true);
              } else {
                setLoginError(true);
              }
            }}
          >
            대시보드 접속 🔑
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* HEADER SECTION */}
      <header className="dashboard-header">
        <div className="header-title-section">
          <h1>LAS TOC-850 온라인 계측 모니터링 대시보드</h1>
          <p>LAS KOREA 제공</p>
        </div>
        <div className="header-controls">
          <button className="filter-btn active" onClick={loadData}>새로고침 🔄</button>
        </div>
      </header>

      {/* ERROR / LOADING HANDLERS */}
      {loading && data.length === 0 ? (
        <div className="glass-card empty-placeholder">
          <div className="status-dot" style={{ width: '40px', height: '40px' }}></div>
          <h2>데이터 스트림 연결 중...</h2>
          <p>Supabase PostgreSQL 클라우드 엔진으로부터 실시간 정보를 당겨오고 있습니다.</p>
        </div>
      ) : error && data.length === 0 ? (
        <div className="glass-card empty-placeholder" style={{ borderColor: 'var(--accent-rose)' }}>
          <h2 style={{ color: 'var(--accent-rose)' }}>클라우드 연결 오류</h2>
          <p>{error}</p>
          <button className="sim-btn" style={{ background: 'var(--accent-rose)' }} onClick={loadData}>연결 재시도 🔄</button>
        </div>
      ) : (
        <>
          {/* CHARTS SECTION */}
          <section style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '24px' }}>
            <div className="glass-card chart-card">
              <div className="chart-header">
                <div>
                  <h3 className="chart-title">TOC & Signal Multi-Series Trend</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>

                  </p>
                </div>

                <div className="header-controls" style={{ gap: '8px', flexWrap: 'wrap' }}>
                  <div className="filter-button-group">
                    <button
                      className={`filter-btn ${selectedAttr === 'TOC_Conc' ? 'active' : ''}`}
                      onClick={() => setSelectedAttr('TOC_Conc')}
                    >
                      TOC 농도 (ppm)
                    </button>
                    <button
                      className={`filter-btn ${selectedAttr === 'MSIG' ? 'active' : ''}`}
                      onClick={() => setSelectedAttr('MSIG')}
                    >
                      측정 신호 (MSIG)
                    </button>
                  </div>

                  <select
                    className="custom-select"
                    style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                    value={timeRange}
                    onChange={(e) => { setTimeRange(e.target.value); setCurrentPage(1); }}
                  >
                    <option value="24h">최근 24시간</option>
                    <option value="3d">최근 3일</option>
                    <option value="7d">최근 7일</option>
                    <option value="All">전체 기간</option>
                  </select>
                </div>
              </div>

              <div style={{ width: '100%', height: 400 }}>
                {chartData.length === 0 ? (
                  <div className="empty-placeholder" style={{ padding: '40px 0' }}>
                    <p>선택한 조건에 부합하는 시계열 데이터가 존재하지 않습니다.</p>
                  </div>
                ) : (
                  <ResponsiveContainer>
                    <LineChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border-color)" />
                      <XAxis dataKey="ShortTime" stroke="var(--text-muted)" fontSize={11} />
                      <YAxis stroke="var(--text-muted)" fontSize={11} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'var(--bg-tertiary)',
                          borderColor: 'var(--border-hover)',
                          borderRadius: '8px',
                          color: 'var(--text-main)'
                        }}
                      />
                      <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                      {activeChannels.map(chName => (
                        <Line
                          key={chName}
                          type="monotone"
                          dataKey={chName}
                          name={chName}
                          stroke={LINE_COLORS[chName] || LINE_COLORS['기타 채널']}
                          strokeWidth={2}
                          dot={{ r: 3, strokeWidth: 1 }}
                          activeDot={{ r: 5 }}
                          connectNulls={true}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </section>

          {/* HISTORICAL TABLE SECTION */}
          <section className="glass-card table-card">
            <div className="chart-header">
              <div>
                <h3 className="chart-title">측정 이력 상세 데이터</h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                  조회 일치 데이터 총 {filteredData.length}건
                </p>
              </div>
            </div>

            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>측정 일시</th>
                    <th>장비 ID (Device ID)</th>
                    <th>채널</th>
                    <th>채널 이름</th>
                    <th>TOC 농도</th>
                    <th>희석 배수</th>
                    <th>측정 신호 (MSIG)</th>
                    <th>기기 가동 비고 (Add Note)</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedTableData.length === 0 ? (
                    <tr>
                      <td colSpan="8" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                        필터 또는 검색 조건에 부합하는 계측 데이터가 존재하지 않습니다.
                      </td>
                    </tr>
                  ) : (
                    paginatedTableData.map((row, index) => (
                      <tr key={index}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{row.Date_Time}</td>
                        <td style={{ color: 'var(--accent-cyan)', fontWeight: 600, fontFamily: 'monospace' }}>{row.Device_ID}</td>
                        <td>{row.Channel}</td>
                        <td style={{ fontWeight: 500 }}>{row.Channel_Name}</td>
                        <td style={{ fontWeight: 600 }}>{row.TOC_Conc} ppm</td>
                        <td>{row.DilutionFactor}x</td>
                        <td style={{ color: 'var(--accent-purple)', fontWeight: 600 }}>{row.MSIG}</td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.Add_note}>
                          {row.Add_note}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* PAGING CONTROLS */}
            {totalPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', marginTop: '10px' }}>
                <button
                  className="filter-btn"
                  style={{ background: 'var(--bg-tertiary)' }}
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                >
                  ◀ 이전
                </button>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                  페이지 <strong>{currentPage}</strong> / {totalPages}
                </span>
                <button
                  className="filter-btn"
                  style={{ background: 'var(--bg-tertiary)' }}
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                >
                  다음 ▶
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
