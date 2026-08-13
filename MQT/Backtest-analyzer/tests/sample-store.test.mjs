import test from 'node:test';
import assert from 'node:assert/strict';
import { importSamples, normalizeSample, samplesToCsv } from '../src/sample-store.mjs';

const base = {
  context: {
    decisionDate: '2025-08-01', decisionTime: '10:30', timeframe: '30m',
    indexCode: '000852.SH', sectorCode: 'SW1电子', stockCode: '301592.sz',
    bar: { time: '2025-08-01 10:30', open: 10, high: 11, low: 9.8, close: 10.8, volume: 1000 },
  },
  label: {
    scope: 'trade_point', verdict: 'positive', action: 'open',
    setup: 'first_ma13_pullback', confidence: 'high', reasons: ['space', 'time', 'space'],
    summary: '首次深回MA13后持续收复', invalidation: '尾盘重新跌破MA13',
  },
};

test('normalizes a chart annotation into the standard sample schema', () => {
  const sample = normalizeSample(base, { id: 'sample-1', now: '2026-08-13T00:00:00.000Z' });
  assert.equal(sample.schemaVersion, 2);
  assert.equal(sample.context.decisionDate, '20250801');
  assert.equal(sample.context.decisionTime, '1030');
  assert.equal(sample.context.stockCode, '301592.SZ');
  assert.equal(sample.context.bar.close, 10.8);
  assert.deepEqual(sample.label.reasons, ['space', 'time']);
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
  assert.match(csv, /301592\.SZ/);
  assert.match(csv, /"空间足够, 量能健康\n等待确认"/);
});
