import { parseQmtLog } from './parser.mjs';
import { fetchDaily, fetchIntraday } from './market-data.mjs';
import { drawCandles, drawLine } from './chart.mjs';
import { sampleLog } from './sample-log.js';

const $ = (selector) => document.querySelector(selector);
const state = { report: null, day: null, stock: null, chartType: 'daily', cache: new Map() };
const styles = { large: '大盘', mid: '中盘', small: '小盘', growth: '成长' };
const pct = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
const money = value => value == null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value);

function marketLabel(exposure) {
  if (exposure >= .7) return '强势 / 可积极参与';
  if (exposure >= .4) return '结构性机会 / 控制节奏';
  if (exposure > 0) return '弱势观察 / 轻仓试错';
  return '风险规避 / 空仓';
}

function metric(label, value) { return `<div class="metric"><small>${label}</small><strong>${value}</strong></div>`; }

function renderMarket(day) {
  if (!day?.state) { $('#marketView').innerHTML = '当日没有 STATE 记录'; return; }
  const exposure = day.state.exposure || 0;
  const bars = Object.entries(day.state.styleExposures || {}).map(([name, value]) => `<div class="style-row"><span>${styles[name] || name}</span><div class="bar"><i style="width:${Math.min(100, value * 100)}%"></i></div><b>${pct(value)}</b></div>`).join('');
  $('#marketView').innerHTML = `<div class="exposure-ring" style="--value:${exposure * 100}"><strong>${pct(exposure)}</strong></div><div class="style-bars"><b>${marketLabel(exposure)}</b>${bars || '<p class="empty">无风格仓位</p>'}</div>`;
}

function renderAllocation(day) {
  const a = day?.allocation, p = day?.portfolio;
  $('#allocationView').innerHTML = [metric('计划仓位', pct(a?.plannedExposure)), metric('可执行仓位', pct(a?.targetExposure)), metric('仓位实现率', pct(a?.fillRate)), metric('未分配资金', money(a?.unallocatedCash)), metric('账户总资产', money(p?.balance)), metric('可用资金', money(p?.cash))].join('');
}

function renderTables(day) {
  $('#sectorRows').innerHTML = day.sectors.length ? day.sectors.map(x => `<tr><td>${styles[x.style] || x.style}</td><td>${x.code}</td><td class="score">${x.score.toFixed(1)}</td></tr>`).join('') : '<tr><td colspan="3" class="empty">当日无入选板块</td></tr>';
  $('#stockRows').innerHTML = day.targets.length ? day.targets.map(x => `<tr data-code="${x.code}" class="${x.code === state.stock?.code ? 'selected' : ''}"><td><b>${x.code}</b><br><small>${x.name || '—'}</small></td><td>${styles[x.style] || x.style}</td><td class="score">${x.score.toFixed(1)}</td><td>${money(day.desired[x.code])}</td></tr>`).join('') : '<tr><td colspan="4" class="empty">当日无入选个股</td></tr>';
  document.querySelectorAll('[data-code]').forEach(row => row.addEventListener('click', () => selectStock(day.targets.find(x => x.code === row.dataset.code))));
}

function diagnostic() {
  const meta = state.report.meta;
  $('#diagnosticText').textContent = [`回测引擎：${meta.engine || '未记录'}`, `首根K线：${meta.firstBar || '未记录'}`, ...meta.warnings].join('\n');
}

async function selectStock(stock) {
  if (!stock) { state.stock = null; $('#chartTitle').textContent = '当日没有可选个股'; return; }
  state.stock = stock; renderTables(state.day); $('#chartTitle').textContent = `${stock.code} ${stock.name || ''}`;
  const trades = [...state.day.orders.filter(x => x.code === stock.code), ...state.day.intraday.filter(x => x.code === stock.code).map(x => ({ side: x.action === 'add' ? 'buy' : 'sell', volume: x.volume, reason: `intraday_${x.action}` }))];
  $('#tradeChips').innerHTML = trades.length ? trades.map(x => `<span class="chip ${x.side}">${x.side === 'buy' ? '买入' : '卖出'} ${money(x.volume)}股 · ${x.reason}</span>`).join('') : '<span class="empty">所选日期没有该股委托记录</span>';
  await renderChart(trades);
}

async function renderChart(trades = []) {
  if (!state.stock) return;
  const key = `${state.chartType}:${state.stock.code}:${state.day.date}`;
  $('#chartLoading').classList.remove('hidden'); $('#chartLoading').textContent = '正在获取公开行情…';
  try {
    let rows = state.cache.get(key);
    if (!rows) {
      rows = state.chartType === 'daily' ? await fetchDaily(state.stock.code, state.day.date) : await fetchIntraday(state.stock.code);
      state.cache.set(key, rows);
    }
    if (state.chartType === 'daily') drawCandles($('#chart'), rows, state.day.date, trades); else drawLine($('#chart'), rows);
    $('#chartLoading').classList.add('hidden');
  } catch (error) {
    $('#chartLoading').textContent = `${error.message}。评分与交易日志仍可正常查看。`;
  }
}

function selectDay(date) {
  state.day = state.report.days.find(x => x.date === date) || state.report.days.at(-1);
  if (!state.day) return;
  $('#dateSelect').value = state.day.date; renderMarket(state.day); renderAllocation(state.day);
  state.stock = state.day.targets[0] || null; renderTables(state.day); selectStock(state.stock);
}

function parse() {
  state.report = parseQmtLog($('#logInput').value);
  const count = state.report.days.length;
  $('#sourceStatus').textContent = count ? `已解析 ${count} 个交易日` : '未识别到策略日志';
  $('#dateSelect').innerHTML = state.report.days.map(x => `<option value="${x.date}">${x.date.slice(0,4)}-${x.date.slice(4,6)}-${x.date.slice(6)}</option>`).join('');
  diagnostic(); if (count) { $('.import-panel').classList.remove('open'); selectDay(state.report.days.at(-1).date); } else $('.import-panel').classList.add('open');
}

$('#sampleButton').addEventListener('click', () => { $('#logInput').value = sampleLog; $('.import-panel').classList.add('open'); parse(); });
$('#parseButton').addEventListener('click', parse);
$('#logInput').addEventListener('focus', () => $('.import-panel').classList.add('open'));
$('#fileInput').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; $('#logInput').value = await file.text(); parse(); });
$('#dateSelect').addEventListener('change', event => selectDay(event.target.value));
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => { document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === tab)); state.chartType = tab.dataset.chart; selectStock(state.stock); }));
window.addEventListener('resize', () => state.stock && selectStock(state.stock));

$('#logInput').value = sampleLog; parse();
