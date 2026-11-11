import test from 'node:test';
import assert from 'node:assert/strict';
import { buildChannelColorMap, LINE_COLORS } from '../src/channelColors.js';

const GREY = LINE_COLORS['기타 채널'];

test('울산1공장 DW·CW·AW 는 서로 다른 색', () => {
  const m = buildChannelColorMap(['DW', 'CW', 'AW'], { DW: '1', CW: '2', AW: '3' });
  assert.equal(new Set(Object.values(m)).size, 3);
  assert.ok(!Object.values(m).includes(GREY));
});

test('인천 유입수·고농도·방류수 는 기존 고정색 그대로', () => {
  const m = buildChannelColorMap(['유입수', '고농도', '방류수'], { 유입수: '1', 고농도: '2', 방류수: '3' });
  assert.deepEqual(m, { 유입수: '#00f2fe', 고농도: '#a55eea', 방류수: '#ff9f43' });
});

test('고정색 없는 단일 채널 사이트는 예전처럼 회색', () => {
  assert.deepEqual(buildChannelColorMap(['원수'], { 원수: '1' }), { 원수: GREY });
  assert.deepEqual(buildChannelColorMap(['중계펌프'], { 중계펌프: '1' }), { 중계펌프: GREY });
});

test('고정색 채널과 섞이면 이미 쓴 색은 피한다', () => {
  const m = buildChannelColorMap(['유입수', 'A', 'B'], { 유입수: '1', A: '2', B: '3' });
  assert.equal(m['유입수'], '#00f2fe');
  assert.equal(new Set(Object.values(m)).size, 3);
});

test('채널 순서가 바뀌어도 같은 채널은 같은 색', () => {
  const ids = { DW: '1', CW: '2', AW: '3' };
  assert.deepEqual(buildChannelColorMap(['AW', 'DW', 'CW'], ids), buildChannelColorMap(['DW', 'CW', 'AW'], ids));
});
