import React, { useState, useEffect, useMemo, useCallback } from 'react';
import Slider from 'rc-slider';
import 'rc-slider/assets/index.css';
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
// Supabase 연결 설정 — Vercel 환경변수에서 로드 (소스코드에 키 노출 금지)
// =========================================================================
const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || "";
const SUPABASE_KEY = import.meta.env.VITE_SUPABASE_KEY || "";
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

// 비고 란의 중복 채널명 정보 제거 (CH Name = xxx / 뒷내용 형태 삭제)
const cleanAddNote = (note) => {
  if (!note) return '';
  const pattern = /^CH\s*Name\s*=[^/]*\/\s*/i;
  return note.replace(pattern, '').trim();
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
      Add_note: cleanAddNote(item.Add_note || '')
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

// PostgREST용 날짜 범위 쿼리 파라미터 빌더
const getDateFilterParams = (range, start, end) => {
  const pad = (n) => String(n).padStart(2, '0');
  const formatDbDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

  if (range === '24h') {
    const d = new Date(Date.now() - 24 * 60 * 60 * 1000);
    return `&Date_Time=gte.${encodeURIComponent(formatDbDate(d))}`;
  }
  if (range === '7d') {
    const d = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    return `&Date_Time=gte.${encodeURIComponent(formatDbDate(d))}`;
  }
  if (range === '30d') {
    const d = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
    return `&Date_Time=gte.${encodeURIComponent(formatDbDate(d))}`;
  }
  if (range === 'custom') {
    let filter = '';
    if (start) {
      const dStart = new Date(start);
      const startStr = `${dStart.getFullYear()}-${pad(dStart.getMonth() + 1)}-${pad(dStart.getDate())} ${pad(dStart.getHours())}:${pad(dStart.getMinutes())}:00`;
      filter += `&Date_Time=gte.${encodeURIComponent(startStr)}`;
    }
    if (end) {
      const dEnd = new Date(end);
      const endStr = `${dEnd.getFullYear()}-${pad(dEnd.getMonth() + 1)}-${pad(dEnd.getDate())} ${pad(dEnd.getHours())}:${pad(dEnd.getMinutes())}:59`;
      filter += `&Date_Time=lte.${encodeURIComponent(endStr)}`;
    }
    return filter;
  }
  return ''; // 'all' 또는 'All'
};

function LegacyApp() {
  // URL 파라미터 ?site= 존재 여부 분석
  const hasSiteParam = useMemo(() => {
    if (typeof window === 'undefined') return false;
    const searchParams = new URLSearchParams(window.location.search);
    const siteVal = searchParams.get('site');
    return siteVal !== null && siteVal.trim() !== '';
  }, []);

  // URL 파라미터 ?site= 에서 사이트 아이디(테이블명) 파싱, 없을 경우 폴백
  const siteId = useMemo(() => {
    if (typeof window === 'undefined') return SUPABASE_TABLE;
    const searchParams = new URLSearchParams(window.location.search);
    return searchParams.get('site') || SUPABASE_TABLE;
  }, []);

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadProgress, setLoadProgress] = useState('');
  const [error, setError] = useState(null);

  // site_config 설정 데이터 상태
  const [siteConfig, setSiteConfig] = useState({
    site_id: siteId,
    passcode: '850', // 폴백용 기본 비밀번호
    site_name: 'LAS TOC-850 온라인 계측 모니터링 대시보드', // 폴백용 기본 사이트명
    is_active: true,
    toc_alert_high: null,
    loading: true
  });

  // 보안 접속
  const [passcode, setPasscode] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [loginError, setLoginError] = useState(false);

  // 트렌드 차트 필터
  const [selectedAttr, setSelectedAttr] = useState('TOC_Conc');
  const [timeRange, setTimeRange] = useState('24h');
  const [customStart, setCustomStart] = useState(() => {
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);
    const pad = (n) => String(n).padStart(2, '0');
    return `${oneWeekAgo.getFullYear()}-${pad(oneWeekAgo.getMonth() + 1)}-${pad(oneWeekAgo.getDate())}T00:00`;
  });
  const [customEnd, setCustomEnd] = useState(() => {
    const now = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T23:59`;
  });

  // 차트 채널 표시/숨김 토글
  const [hiddenChannels, setHiddenChannels] = useState(new Set());

  // Y축 수동 줌
  const [yMin, setYMin] = useState('');
  const [yMax, setYMax] = useState('');

  // 테이블 필터
  const [tableChannelFilter, setTableChannelFilter] = useState('All');
  const [tableTocMin, setTableTocMin] = useState('');
  const [tableTocMax, setTableTocMax] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [itemsPerPage, setItemsPerPage] = useState(() => {
    const saved = localStorage.getItem('dashboard_items_per_page');
    return saved ? Number(saved) : 50;
  });

  // 날짜 점프 상태
  const [jumpDate, setJumpDate] = useState('');

  // CSV 다운로드 모달 상태
  const [isCsvModalOpen, setIsCsvModalOpen] = useState(false);
  const [csvRangeType, setCsvRangeType] = useState('24h');
  const [csvCustomStart, setCsvCustomStart] = useState('');
  const [csvCustomEnd, setCsvCustomEnd] = useState('');

  // =========================================================================
  // site_config 로드 함수 추가
  // =========================================================================
  const loadSiteConfig = useCallback(async () => {
    if (!hasSiteParam) return;
    try {
      if (!SUPABASE_URL || !SUPABASE_KEY) {
        throw new Error('Supabase 연결 정보가 설정되지 않았습니다.');
      }
      const baseUrl = SUPABASE_URL.replace(/\/$/, '');
      const configEndpoint = baseUrl.includes('/rest/v1')
        ? `${baseUrl}/850_dashboard_site_config`
        : `${baseUrl}/rest/v1/850_dashboard_site_config`;

      const response = await fetch(`${configEndpoint}?site_id=eq.${siteId}`, {
        headers: {
          'apikey': SUPABASE_KEY,
          'Authorization': `Bearer ${SUPABASE_KEY}`
        }
      });

      if (response.ok) {
        const confList = await response.ok ? await response.json() : [];
        if (Array.isArray(confList) && confList.length > 0) {
          const conf = confList[0];
          let alertObj = null;
          if (conf.toc_alert_high) {
            try {
              alertObj = typeof conf.toc_alert_high === 'string'
                ? JSON.parse(conf.toc_alert_high)
                : conf.toc_alert_high;
            } catch (e) {
              console.error("임계값 JSON 파싱 에러:", e);
            }
          }
          setSiteConfig({
            site_id: conf.site_id,
            passcode: conf.passcode || '850',
            site_name: conf.site_name || 'LAS TOC-850 온라인 계측 모니터링 대시보드',
            is_active: conf.is_active !== false,
            toc_alert_high: alertObj,
            loading: false
          });
          return;
        }
      }
    } catch (err) {
      console.error("site_config 로드 실패, 기본설정 폴백 사용:", err);
    }

    // 로딩 완료 처리 (폴백 값 유지)
    setSiteConfig(prev => ({
      ...prev,
      loading: false
    }));
  }, [siteId]);

  // =========================================================================
  // Supabase 페이지네이션 Fetch — 선택한 날짜 구간만 서버사이드 쿼리
  // =========================================================================
  const loadData = useCallback(async () => {
    if (!hasSiteParam) return;
    setLoading(true);
    setError(null);
    setLoadProgress('연결 중...');
    try {
      if (!SUPABASE_URL || !SUPABASE_KEY) {
        throw new Error('Supabase 연결 정보가 설정되지 않았습니다.');
      }

      const baseUrl = SUPABASE_URL.replace(/\/$/, '');
      const endpoint = baseUrl.includes('/rest/v1')
        ? `${baseUrl}/${siteId}`
        : `${baseUrl}/rest/v1/${siteId}`;

      // 서버 사이드 날짜 쿼리 파라미터 빌드
      const filterParams = getDateFilterParams(timeRange, customStart, customEnd);

      let allData = [];
      let from = 0;
      let hasMore = true;

      while (hasMore) {
        const to = from + PAGE_SIZE - 1;
        setLoadProgress(`${allData.length.toLocaleString()}건 로딩 중...`);

        // PostgREST 날짜 필터(filterParams) 주입
        const response = await fetch(
          `${endpoint}?select=*&order=Date_Time.asc${filterParams}`,
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
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [siteId, timeRange, customStart, customEnd]);

  // 페이지 타이틀 동적 업데이트
  useEffect(() => {
    if (siteConfig && siteConfig.site_name) {
      document.title = siteConfig.site_name;
    }
  }, [siteConfig]);

  // 사이트 설정 정보 주기적 로드
  useEffect(() => {
    loadSiteConfig();
    const interval = setInterval(loadSiteConfig, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [loadSiteConfig]);

  // 조회 필터 변경 또는 시간 경과 시 데이터 로드
  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [loadData]);

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

  // Y축 자동 계산용 (절대 최소/최대)
  const { absMin, absMax } = useMemo(() => {
    if (visibleChannels.length === 0 || chartData.length === 0) return { absMin: 0, absMax: 100 };
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
    if (min === Infinity) return { absMin: 0, absMax: 100 };
    const padding = (max - min) * 0.05 || 1;
    return {
      absMin: Math.max(0, Math.floor(min - padding)),
      absMax: Math.ceil(max + padding)
    };
  }, [visibleChannels, chartData]);

  // Y축 도메인: 수동 입력값 우선, 없으면 표시 중인 채널 기준 오토스케일
  const yDomain = useMemo(() => {
    // 수동 입력값이 있으면 우선
    const manualMin = yMin !== '' ? parseFloat(yMin) : null;
    const manualMax = yMax !== '' ? parseFloat(yMax) : null;
    if (manualMin !== null && manualMax !== null) {
      return [manualMin, manualMax];
    }
    return [absMin, absMax];
  }, [absMin, absMax, yMin, yMax]);

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

  // 날짜로 점프 기능
  const handleJumpToDate = useCallback(() => {
    if (!jumpDate) return;
    
    // YYYY-MM-DD 포맷 등 입력된 날짜 문자열로 tableFilteredData(정렬된 상태) 탐색
    // 최근 데이터 먼저 정렬되어 있으므로, Date_Time이 jumpDate로 시작하는 첫 매칭 행 검색
    const targetIndex = tableFilteredData.findIndex(item => 
      item.Date_Time && item.Date_Time.startsWith(jumpDate)
    );

    if (targetIndex !== -1) {
      const targetPage = Math.floor(targetIndex / itemsPerPage) + 1;
      setCurrentPage(targetPage);
      alert(`${jumpDate} 데이터가 발견되어 ${targetPage}페이지로 이동합니다. (해당 페이지 ${targetIndex % itemsPerPage + 1}번째 행)`);
    } else {
      alert(`입력하신 날짜(${jumpDate})에 해당하는 데이터를 찾을 수 없습니다. (필터 상태 및 YYYY-MM-DD 형식을 확인해주세요)`);
    }
  }, [jumpDate, tableFilteredData, itemsPerPage]);

  // 채널별 TOC 알림 경계값 조회 유틸
  const getAlertThreshold = useCallback((channel) => {
    if (!siteConfig || !siteConfig.toc_alert_high) return null;
    const threshold = parseFloat(siteConfig.toc_alert_high[channel] || siteConfig.toc_alert_high[String(channel)]);
    return isNaN(threshold) ? null : threshold;
  }, [siteConfig]);

  // CSV 다운로드 전용 필터링 및 다운로드 구현
  const handleCSVDownload = useCallback(async () => {
    setError(null);
    setLoadProgress('다운로드 데이터 조회 중...');
    setLoading(true);

    try {
      if (!SUPABASE_URL || !SUPABASE_KEY) {
        throw new Error('Supabase 연결 정보가 설정되지 않았습니다.');
      }

      const baseUrl = SUPABASE_URL.replace(/\/$/, '');
      const endpoint = baseUrl.includes('/rest/v1')
        ? `${baseUrl}/${siteId}`
        : `${baseUrl}/rest/v1/${siteId}`;

      // CSV 다운로드용 날짜 필터 파라미터 빌드
      const filterParams = getDateFilterParams(csvRangeType, csvCustomStart, csvCustomEnd);

      let allData = [];
      let from = 0;
      let hasMore = true;

      while (hasMore) {
        const to = from + PAGE_SIZE - 1;
        setLoadProgress(`다운로드 데이터 ${allData.length.toLocaleString()}건 로딩 중...`);

        const response = await fetch(
          `${endpoint}?select=*&order=Date_Time.asc${filterParams}`,
          {
            headers: {
              'apikey': SUPABASE_KEY,
              'Authorization': `Bearer ${SUPABASE_KEY}`,
              'Range': `${from}-${to}`
            }
          }
        );

        if (!response.ok && response.status !== 206) {
          throw new Error(`CSV 데이터 로드 실패: ${response.status}`);
        }

        const chunk = await response.json();
        if (!Array.isArray(chunk) || chunk.length === 0) {
          hasMore = false;
        } else {
          allData = allData.concat(chunk);
          from += PAGE_SIZE;
          if (chunk.length < PAGE_SIZE) {
            hasMore = false;
          }
        }
      }

      if (allData.length === 0) {
        alert('선택하신 기간 내에 다운로드할 데이터가 존재하지 않습니다.');
        return;
      }

      const targetData = normalizeData(allData);
      // 최신 데이터를 먼저 보기 위해 내림차순 정렬 후 CSV 내보내기
      targetData.sort((a, b) => parseDate(b.Date_Time) - parseDate(a.Date_Time));

      const headers = ['Date_Time','Device_ID','Channel','Channel_Name','TOC_Conc','DilutionFactor','MSIG','SLOP','ICPT','FACT','OFST','Add_note'];
      const rows = [headers.join(',')];
      targetData.forEach(r => {
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
      a.download = `TOC_Data_${csvRangeType}_${new Date().toISOString().slice(0,10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setIsCsvModalOpen(false); // 모달 닫기
    } catch (err) {
      console.error(err);
      alert(`다운로드 실패: ${err.message}`);
    } finally {
      setLoading(false);
      setLoadProgress('');
    }
  }, [siteId, csvRangeType, csvCustomStart, csvCustomEnd]);

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
  // 보안 접속 화면 및 로딩/활성화 상태 체크
  // =========================================================================
  if (!hasSiteParam) {
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
        <div className="glass-card" style={{ maxWidth: '450px', width: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '20px', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
          <div style={{ fontSize: '3.2rem', color: 'var(--accent-cyan)' }}>🔒</div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}>대시보드 접속 제한</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: '1.6' }}>
            본 온라인 계측 모니터링 시스템은 개별 발급된 **보안 링크(URL)**를 통해서만 접근 가능합니다.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            올바른 전용 지점 파라미터(`?site=지점명`)를 포함해 접속하시거나, 계정 관리자에게 문의 바랍니다.
          </p>
        </div>
      </div>
    );
  }

  if (siteConfig.loading) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-primary)',
        color: 'var(--text-main)',
        fontFamily: 'var(--font-body)'
      }}>
        <div style={{ fontSize: '1.1rem', marginBottom: '15px', color: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}>설정 정보 분석 중...</div>
        <div className="loader" style={{
          border: '3px solid rgba(255,255,255,0.05)',
          borderTop: '3px solid var(--accent-cyan)',
          borderRadius: '50%',
          width: '32px',
          height: '32px',
          animation: 'spin 1s linear infinite'
        }}></div>
      </div>
    );
  }

  // 서비스 비활성화 상태인 경우
  if (!siteConfig.is_active) {
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
        <div className="glass-card" style={{ maxWidth: '450px', width: '100%', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '20px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
          <div style={{ fontSize: '3rem', color: 'var(--accent-rose)' }}>⚠️</div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, color: 'var(--accent-rose)' }}>서비스 비활성화</h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', lineHeight: '1.6' }}>
            본 모니터링 대시보드(<strong>{siteConfig.site_name}</strong>)는 관리자에 의해 일시적으로 서비스가 비활성화되었습니다.
          </p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
            기술 지원 및 재활성화 관련 문의는 본사 담당자에게 전달해 주세요.
          </p>
        </div>
      </div>
    );
  }

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
          <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700 }}>{siteConfig.site_name} 보안 접속</h2>
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
                if (passcode === siteConfig.passcode) setIsUnlocked(true);
                else setLoginError(true);
              }
            }}
          />
          {loginError && <p style={{ color: 'var(--accent-rose)', fontSize: '0.85rem' }}>올바르지 않은 코드입니다. 다시 시도해 주세요.</p>}
          <button
            className="sim-btn"
            style={{ width: '100%' }}
            onClick={() => {
              if (passcode === siteConfig.passcode) setIsUnlocked(true);
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
          <h1>{siteConfig.site_name}</h1>
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

            <div style={{ display: 'flex', width: '100%', height: 420 }}>
              {/* Y축 슬라이더 바 (rc-slider) */}
              <div style={{ padding: '20px 10px 30px 10px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '8px', fontWeight: 600 }}>Y 줌</span>
                <div style={{ flex: 1 }}>
                  <Slider
                    vertical
                    range
                    min={absMin}
                    max={absMax}
                    value={[
                      yMin !== '' ? parseFloat(yMin) : absMin,
                      yMax !== '' ? parseFloat(yMax) : absMax
                    ]}
                    onChange={(val) => {
                      setYMin(val[0]);
                      setYMax(val[1]);
                    }}
                    styles={{
                      track: { backgroundColor: 'var(--accent-cyan)' },
                      handle: { borderColor: 'var(--accent-cyan)', backgroundColor: 'var(--bg-primary)' }
                    }}
                  />
                </div>
                {(yMin !== '' || yMax !== '') && (
                  <button
                    style={{ marginTop: '12px', fontSize: '0.75rem', padding: '4px 8px', background: 'transparent', border: '1px solid var(--border-color)', color: 'var(--text-muted)', borderRadius: '4px', cursor: 'pointer' }}
                    onClick={() => { setYMin(''); setYMax(''); }}
                  >
                    초기화
                  </button>
                )}
              </div>
              <div style={{ flex: 1, height: '100%', minWidth: 0 }}>
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
                  장비: <span style={{ color: 'var(--accent-cyan)', fontWeight: 600, fontFamily: 'monospace' }}>{data.length > 0 ? data[0].Device_ID : '—'}</span>
                  {' · '}총 {data.length.toLocaleString()}건 중 {tableFilteredData.length.toLocaleString()}건 조회
                </p>
              </div>
              <button className="filter-btn active" onClick={() => setIsCsvModalOpen(true)} disabled={data.length === 0}>
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
                <label>페이지당 표시</label>
                <input
                  type="number"
                  className="custom-select"
                  value={itemsPerPage}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    if (val > 0) {
                      setItemsPerPage(val);
                      localStorage.setItem('dashboard_items_per_page', val);
                    }
                  }}
                  style={{ width: '80px' }}
                  min="1"
                />
              </div>

              {/* 날짜 점프 (Jump to Date) 필터 바에 연동 */}
              <div className="filter-group date-jump-filter-group">
                <label>날짜 이동 (점프)</label>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <input
                    type="date"
                    className="custom-select date-jump-input"
                    value={jumpDate}
                    onChange={(e) => setJumpDate(e.target.value)}
                    style={{ width: '140px', padding: '7px 12px' }}
                  />
                  <button className="sim-btn jump-btn" onClick={handleJumpToDate} style={{ height: '35px', padding: '0 12px !important', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    이동 🚀
                  </button>
                </div>
              </div>
            </div>

            {/* 데이터 테이블 */}
            <div className="table-wrapper">
              <table className="data-table compact">
                <thead>
                  <tr>
                    <th style={{ whiteSpace: 'nowrap' }}>측정 일시</th>
                    <th style={{ whiteSpace: 'nowrap' }}>채널</th>
                    <th style={{ whiteSpace: 'nowrap' }}>TOC (ppm)</th>
                    <th style={{ whiteSpace: 'nowrap' }}>희석</th>
                    <th style={{ whiteSpace: 'nowrap' }}>MSIG</th>
                    <th style={{ whiteSpace: 'nowrap' }}>비고</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedData.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
                        필터 조건에 부합하는 데이터가 없습니다.
                      </td>
                    </tr>
                  ) : (
                    paginatedData.map((row, index) => {
                      const threshold = getAlertThreshold(row.Channel);
                      const isAlert = threshold !== null && row.TOC_Conc > threshold;
                      return (
                        <tr key={index} className={isAlert ? 'row-alert' : ''}>
                          <td style={{ fontFamily: 'monospace', fontWeight: 600, whiteSpace: 'nowrap' }}>{row.Date_Time}</td>
                          <td style={{ fontWeight: 500, whiteSpace: 'nowrap' }}>{row.Channel_Name}</td>
                          <td style={{ fontWeight: 600, color: isAlert ? 'var(--accent-rose)' : 'inherit', whiteSpace: 'nowrap' }}>
                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                              {isAlert && <span className="alert-dot" title={`경고 기준치 (${threshold} ppm) 초과`} />}
                              <span>{row.TOC_Conc}</span>
                            </div>
                          </td>
                          <td style={{ whiteSpace: 'nowrap' }}>{row.DilutionFactor}x</td>
                          <td style={{ color: 'var(--accent-purple)', fontWeight: 600, whiteSpace: 'nowrap' }}>{row.MSIG}</td>
                          <td style={{ color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.Add_note}>
                            {row.Add_note}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>

            {/* 페이징 바 */}
            <div className="table-pagination-container" style={{ justifyContent: 'center' }}>
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
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-main)', fontWeight: 600 }}>
                    {currentPage} / {totalPages} 페이지
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
            </div>
          </section>

          {/* ============================================ */}
          {/* CSV 다운로드 기간 선택 모달                    */}
          {/* ============================================ */}
          {isCsvModalOpen && (
            <div className="modal-overlay" onClick={() => setIsCsvModalOpen(false)}>
              <div className="glass-card modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                  <h3>CSV 다운로드 기간 선택</h3>
                  <button className="modal-close-btn" onClick={() => setIsCsvModalOpen(false)}>✕</button>
                </div>
                
                <div className="modal-body">
                  <p style={{ fontSize: '0.88rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
                    원하시는 다운로드 범위를 지정해 주세요. 최신 데이터가 상단에 배치된 CSV 파일이 다운로드됩니다.
                  </p>

                  <div className="csv-options-grid">
                    <label className={`csv-option-card ${csvRangeType === '24h' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        name="csvRange"
                        value="24h"
                        checked={csvRangeType === '24h'}
                        onChange={(e) => setCsvRangeType(e.target.value)}
                      />
                      <div className="option-info">
                        <span className="option-title">최근 24시간</span>
                        <span className="option-desc">가장 최신 하루치 측정 데이터를 추출합니다.</span>
                      </div>
                    </label>

                    <label className={`csv-option-card ${csvRangeType === '7d' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        name="csvRange"
                        value="7d"
                        checked={csvRangeType === '7d'}
                        onChange={(e) => setCsvRangeType(e.target.value)}
                      />
                      <div className="option-info">
                        <span className="option-title">최근 7일</span>
                        <span className="option-desc">최근 일주일 동안의 통계 분석에 적합합니다.</span>
                      </div>
                    </label>

                    <label className={`csv-option-card ${csvRangeType === '30d' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        name="csvRange"
                        value="30d"
                        checked={csvRangeType === '30d'}
                        onChange={(e) => setCsvRangeType(e.target.value)}
                      />
                      <div className="option-info">
                        <span className="option-title">최근 30일</span>
                        <span className="option-desc">최근 30일간 장기 추세를 분석할 때 사용합니다.</span>
                      </div>
                    </label>

                    <label className={`csv-option-card ${csvRangeType === 'custom' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        name="csvRange"
                        value="custom"
                        checked={csvRangeType === 'custom'}
                        onChange={(e) => setCsvRangeType(e.target.value)}
                      />
                      <div className="option-info">
                        <span className="option-title">기간 지정</span>
                        <span className="option-desc">시작 일시와 종료 일시를 수동 설정합니다.</span>
                      </div>
                    </label>

                    <label className={`csv-option-card ${csvRangeType === 'all' ? 'active' : ''}`}>
                      <input
                        type="radio"
                        name="csvRange"
                        value="all"
                        checked={csvRangeType === 'all'}
                        onChange={(e) => setCsvRangeType(e.target.value)}
                      />
                      <div className="option-info">
                        <span className="option-title">전체 데이터</span>
                        <span className="option-desc">클라우드에 누적된 전체 ({data.length.toLocaleString()}건) 데이터를 다운로드합니다.</span>
                      </div>
                    </label>
                  </div>

                  {/* 커스텀 날짜 선택기 */}
                  {csvRangeType === 'custom' && (
                    <div className="custom-time-range csv-custom-time" style={{ marginTop: '16px' }}>
                      <label>
                        <span>시작 일시</span>
                        <input
                          type="datetime-local"
                          className="custom-select datetime-input"
                          value={csvCustomStart}
                          onChange={(e) => setCsvCustomStart(e.target.value)}
                        />
                      </label>
                      <span className="time-range-separator">~</span>
                      <label>
                        <span>종료 일시</span>
                        <input
                          type="datetime-local"
                          className="custom-select datetime-input"
                          value={csvCustomEnd}
                          onChange={(e) => setCsvCustomEnd(e.target.value)}
                        />
                      </label>
                    </div>
                  )}
                </div>

                <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
                  <button className="filter-btn" onClick={() => setIsCsvModalOpen(false)}>취소</button>
                  <button className="sim-btn" onClick={handleCSVDownload}>내보내기 실행 📥</button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default LegacyApp;
