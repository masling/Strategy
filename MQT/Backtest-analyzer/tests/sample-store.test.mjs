import test from 'node:test';
import assert from 'node:assert/strict';
import {
  deriveTechnicalFeatures, importSamples, normalizeSample, readSamples,
  SAMPLE_STORAGE_KEY, samplesToCsv, structuredSampleErrors,
} from '../src/sample-store.mjs';

const base = {
  context: {
    decisionDate: '2025-08-01', decisionTime: '10:30', timeframe: '30m',
    indexCode: '000852.SH', sectorCode: 'SW1电子', stockCode: '301592.sz',
    bar: { time: '2025-08-01 10:30', open: 10, high: 11, low: 9.8, close: 10.8, volume: 1000 },
  },
  label: {
    scope: 'trade_point', verdict: 'positive', action: 'open',
    setup: 'first_ma13_pullback', confidence: 'high', reasons: ['space', 'time', 'space'],
    marketState: 'rotation', sectorStage: 'first_pullback', lifecycle: 'first_ma13_pullback',
    maStructures: ['smooth', 'balanced_gap'], pullbackPath: 'direct_ma13', spaceState: 'sufficient',
    timingState: 'sufficient', volumePatterns: ['shrink_pullback'], overheadSupply: 'none',
    intradayConfirm: 'two_bar_reclaim', invalidationRules: ['break_ma13'],
    summary: '首次深回MA13后持续收复', invalidation: '尾盘重新跌破MA13',
  },
};

test('normalizes a chart annotation into the standard sample schema', () => {
  const sample = normalizeSample(base, { id: 'sample-1', now: '2026-08-13T00:00:00.000Z' });
  assert.equal(sample.schemaVersion, 3);
  assert.equal(sample.context.decisionDate, '20250801');
  assert.equal(sample.context.decisionTime, '1030');
  assert.equal(sample.context.stockCode, '301592.SZ');
  assert.equal(sample.context.bar.close, 10.8);
  assert.deepEqual(sample.label.reasons, ['space', 'time']);
  assert.deepEqual(sample.label.maStructures, ['smooth', 'balanced_gap']);
});

test('validates the structured fields required by each decision level', () => {
  const complete = normalizeSample(base, { id: 'sample-1', now: '2026-08-13T00:00:00.000Z' });
  assert.deepEqual(structuredSampleErrors(complete), []);
  const incomplete = normalizeSample({ ...base, label: { ...base.label, lifecycle: 'unknown', volumePatterns: [] } });
  assert.deepEqual(structuredSampleErrors(incomplete), ['请选择个股生命周期', '至少选择一个量能结构']);
});

test('derives comparable daily MA, slope, pullback and volume features', () => {
  const rows = Array.from({ length: 50 }, (_, index) => {
    const date = new Date(Date.UTC(2025, 0, index + 1)).toISOString().slice(0, 10);
    const close = 10 + index * 0.2;
    return { time: date, open: close - 0.1, high: close + 0.5, low: close - 0.3, close, volume: 1000 + index * 10 };
  });
  rows[49] = { ...rows[49], low: 17.5, close: 19.8, volume: 1800 };
  const features = deriveTechnicalFeatures(rows, rows[49]);
  assert.ok(features.ma7 > features.ma13);
  assert.ok(features.ma13 > features.ma40);
  assert.ok(features.gap713Pct > 0);
  assert.equal(features.reclaimedMa13, true);
  assert.ok(features.volume1To20Ratio > 1);
});

test('migrates V2 browser samples to V3 storage without losing records', () => {
  const values = new Map([['qmt-standard-samples-v2', JSON.stringify([normalizeSample(base)])]]);
  const storage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
  const samples = readSamples(storage);
  assert.equal(samples.length, 1);
  assert.ok(values.has(SAMPLE_STORAGE_KEY));
  assert.equal(samples[0].schemaVersion, 3);
});

test('requires decision semantics instead of saving an empty point', () => {
  assert.throws(() => normalizeSample({ context: { decisionDate: '20250801' }, label: {} }), /判断层级/);
  assert.throws(() => normalizeSample({ ...base, label: { ...base.label, summary: '' } }), /判断原因/);
});

test('imports the existing manual label format', () => {
  const samples = importSamples({ labels: [{
    code: '002643.SZ', date: '2025-08-01', label: 'negative_entry',
    setup: 'failed_reclaim', confidence: 'high', note: '未持续收复MA13',
  }] }, '2026-08-13T00:00:00.000Z');
  assert.equal(samples.length, 1);
  assert.equal(samples[0].label.verdict, 'negative');
  assert.equal(samples[0].label.action, 'no_trade');
  assert.equal(samples[0].context.stockCode, '002643.SZ');
});

test('skips unresolved legacy labels without inventing a decision date', () => {
  const samples = importSamples({ labels: [
    { code: '300236.SZ', label: 'negative_entry', note: '日期待确认' },
    { code: '301592.SZ', range: '2025-08-01 — 2025-08-04', label: 'positive_entry', note: '首次深回' },
  ] }, '2026-08-13T00:00:00.000Z');
  assert.equal(samples.length, 1);
  assert.equal(samples[0].context.decisionDate, '20250801');
});

test('exports research-friendly CSV with quoted free text', () => {
  const sample = normalizeSample({
    ...base, label: { ...base.label, summary: '空间足够, 量能健康\n等待确认' },
  }, { id: 'sample-1', now: '2026-08-13T00:00:00.000Z' });
  const csv = samplesToCsv([sample]);
  assert.match(csv, /decision_date/);
  assert.match(csv, /analysis_ready/);
  assert.match(csv, /sample-1,true,/);
  assert.match(csv, /ma7_slope_3d_pct/);
  assert.match(csv, /market_state/);
  assert.match(csv, /301592\.SZ/);
  assert.match(csv, /"空间足够, 量能健康\n等待确认"/);
});

test('keeps the structured CSV header and row column counts aligned', () => {
  const sample = normalizeSample(base, { id: 'sample-1', now: '2026-08-13T00:00:00.000Z' });
  const [header, row] = samplesToCsv([sample]).split('\n');
  assert.equal(row.split(',').length, header.split(',').length);
});
