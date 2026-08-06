import test from 'node:test';
import assert from 'node:assert/strict';
import { parseQmtLog } from '../src/parser.mjs';

const log = `ENGINE period 5m start 20250701 end 20250805
FIRST_BAR 2025-07-01 09:35:00
DESIRED 20250801 {'002755.SZ': 2000}
ALLOCATION 20250801 planned_exposure 0.8 target_exposure 0.62 fill_rate 0.775 unallocated_cash 180000
ORDER 20250801 buy 002755.SZ 2000 rebalance
PORTFOLIO source virtual_account balance 996162.36 cash 872879.36 positions 6
STATE 20250801 exposure 0.8 style_exposures {'large': 0.4, 'growth': 0.4} scores {'000300.SH': {'score': 82}, '399006.SZ': {'score': 88}}
SECTORS [('growth', 'SW1_汽车', 86.5), ('large', 'SW1_银行', 80)]
TARGETS [('growth', '002755.SZ', '奥赛康', 91.2)]
INTRADAY 20250801 002755.SZ reduce 600`;

test('parses linked daily analysis records', () => {
  const result = parseQmtLog(log);
  assert.equal(result.days.length, 1);
  assert.equal(result.days[0].state.exposure, 0.8);
  assert.equal(result.days[0].sectors[0].score, 86.5);
  assert.equal(result.days[0].targets[0].name, '奥赛康');
  assert.equal(result.days[0].orders[0].volume, 2000);
  assert.equal(result.days[0].allocation.fillRate, 0.775);
});

test('preserves engine metadata and warnings', () => {
  const result = parseQmtLog(`${log}\nWARNING invalid context.capital`);
  assert.match(result.meta.engine, /period 5m/);
  assert.equal(result.meta.firstBar, '2025-07-01 09:35:00');
  assert.equal(result.meta.warnings.length, 1);
});

test('returns an empty report for unrelated text', () => {
  assert.deepEqual(parseQmtLog('hello').days, []);
});

test('attaches a portfolio snapshot to the following dated cycle', () => {
  const result = parseQmtLog(`STATE 20250801 exposure 0.5 style_exposures {} scores {}
PORTFOLIO source virtual_account balance 990000 cash 800000 positions 2
DESIRED 20250804 {'600036.SH': 1000}
STATE 20250804 exposure 0.6 style_exposures {} scores {}`);
  assert.equal(result.days[0].portfolio, null);
  assert.equal(result.days[1].portfolio.balance, 990000);
});

test('derives backtest range and performance statistics from daily snapshots', () => {
  const result = parseQmtLog(`ENGINE period 5m start -1 end -1
PORTFOLIO source virtual_account balance 100 cash 100 positions 0
STATE 20250102 exposure 0 style_exposures {} scores {}
PORTFOLIO source virtual_account balance 120 cash 120 positions 0
STATE 20250103 exposure 0 style_exposures {} scores {}
PORTFOLIO source virtual_account balance 90 cash 90 positions 0
STATE 20250106 exposure 0 style_exposures {} scores {}`);
  assert.equal(result.meta.period, '5m');
  assert.equal(result.meta.startTime, '2025-01-02');
  assert.equal(result.meta.endTime, '2025-01-06');
  assert.equal(result.statistics.tradingDays, 3);
  assert.equal(result.statistics.initialAsset, 100);
  assert.equal(result.statistics.finalAsset, 90);
  assert.ok(Math.abs(result.statistics.totalReturn + 0.1) < 1e-12);
  assert.ok(Math.abs(result.statistics.maxDrawdown + 0.25) < 1e-12);
});

test('uses actual backtest range emitted by the strategy', () => {
  const result = parseQmtLog(`ENGINE period 5m start -1 end -1
BACKTEST_RANGE start 2025-01-02 09:35:00 end 2025-01-06 15:00:00
STATE 20250102 exposure 0 style_exposures {} scores {}`);
  assert.equal(result.meta.startTime, '2025-01-02 09:35:00');
  assert.equal(result.meta.endTime, '2025-01-06 15:00:00');
});

test('annualizes return using the actual backtest date range instead of sparse asset snapshots', () => {
  const result = parseQmtLog(`BACKTEST_RANGE start 2025-08-01 09:35:00 end 2026-08-03 15:00:00
PORTFOLIO source result_records capital 1000000 balance 1000000 cash 1000000 positions 0
STATE 20250801 exposure 0 style_exposures {} scores {}
STATE 20260105 exposure 0 style_exposures {} scores {}
PORTFOLIO source result_records capital 1000000 balance 1232447 cash 1232447 positions 0
STATE 20260803 exposure 0 style_exposures {} scores {}`);
  const expected = Math.pow(1.232447, 365 / 367) - 1;
  assert.equal(result.statistics.tradingDays, 3);
  assert.ok(Math.abs(result.statistics.totalReturn - 0.232447) < 1e-12);
  assert.ok(Math.abs(result.statistics.annualizedReturn - expected) < 1e-12);
  assert.ok(result.statistics.annualizedReturn < 0.24);
});

test('groups every buy and sell order by stock across trading days', () => {
  const result = parseQmtLog(`STATE 20250801 exposure 0.8 style_exposures {} scores {}
TARGETS [('growth', '002755.SZ', '奥赛康', 91.2)]
ORDER 20250801 buy 002755.SZ 2000 rebalance
ORDER 20250804 sell 002755.SZ 600 intraday_top
STATE 20250804 exposure 0.7 style_exposures {} scores {}
ORDER 20250805 sell 002755.SZ 1400 sector_rotation`);
  assert.equal(result.stocks.length, 1);
  assert.equal(result.stocks[0].name, '奥赛康');
  assert.equal(result.stocks[0].buyCount, 1);
  assert.equal(result.stocks[0].sellCount, 2);
  assert.equal(result.stocks[0].buyVolume, 2000);
  assert.equal(result.stocks[0].sellVolume, 2000);
  assert.deepEqual(result.stocks[0].orders.map(order => order.date), ['20250801', '20250804', '20250805']);
});

test('keeps traded stocks even when they never appear in targets', () => {
  const result = parseQmtLog(`ORDER 20250801 buy 600000.SH 1000 rebalance`);
  assert.equal(result.stocks[0].code, '600000.SH');
  assert.equal(result.stocks[0].name, '');
});

test('parses order time and submitted price while keeping old logs compatible', () => {
  const result = parseQmtLog(`ORDER 20250801 100500 buy 002755.SZ 2000 price 28.13 rebalance
ORDER 20250804 sell 002755.SZ 600 intraday_top`);
  assert.deepEqual(result.stocks[0].orders[0], {
    date: '20250801', time: '100500', side: 'buy', code: '002755.SZ',
    volume: 2000, price: 28.13, reason: 'rebalance',
  });
  assert.equal(result.stocks[0].orders[1].time, '');
  assert.equal(result.stocks[0].orders[1].price, null);
});
