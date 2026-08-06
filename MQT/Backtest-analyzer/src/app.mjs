import { parseQmtLog } from './parser.mjs?v=20260806-order-status1';
import { fetchDaily, fetchThirtyMinute } from './market-data.mjs';
import { drawCandles } from './chart.mjs';
import { sampleLog } from './sample-log.js';

const $ = (selector) => document.querySelector(selector);
const state = {
  report: null, day: null, stock: null, chartType: 'daily', cache: new Map(), chartRows: [], chartTrades: [],
  chartView: { bars: { daily: 80, '30m': 160 }, offset: { daily: 0, '30m': 0 } }
};
const styles = { large: '大盘', mid: '中盘', small: '小盘', growth: '成长' };
const indexes = { '000300.SH': '沪深300', '000905.SH': '中证500', '000852.SH': '中证1000', '399006.SZ': '创业板' };
const pct = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`;
const money = value => value == null ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value);
const ratio = value => value == null || !Number.isFinite(value) ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;

function marketLabel(exposure) {
  if (exposure >= .7) return '强势 / 可积极参与';
  if (exposure >= .4) return '结构性机会 / 控制节奏';
  if (exposure > 0) return '弱势观察 / 轻仓试错';
  return '风险规避 / 空仓';
}

function metric(label, value) { return `<div class="metric"><small>${label}</small><strong>${value}</strong></div>`; }

function renderOverview() {
  const meta = state.report.meta;
  const stats = state.report.statistics || { tradingDays: state.report.days.length };
  $('#backtestStats').innerHTML = [
    metric('开始时间', meta.startTime || '—'), metric('结束时间', meta.endTime || '—'),
    metric('交易日', stats.tradingDays || 0), metric('回测周期', meta.period || '—'),
    metric('初始资产', money(stats.initialAsset)), metric('期末资产', money(stats.finalAsset)),
    metric('累计收益', ratio(stats.totalReturn)), metric('年化收益', ratio(stats.annualizedReturn)),
    metric('最大回撤', ratio(stats.maxDrawdown)), metric('夏普比率', stats.sharpe == null ? '—' : stats.sharpe.toFixed(2)),
  ].join('');
}

function renderMarket(day) {
  if (!day?.state) { $('#marketView').innerHTML = '当日没有 STATE 记录'; return; }
  const exposure = day.state.exposure || 0;
  const scores = Object.entries(day.state.scores || {}).map(([code, raw]) => {
    const score = typeof raw === 'object' ? raw?.score : raw;
    return `${indexes[code] || code} ${Number(score).toFixed(0)}`;
  }).join(' · ');
  const bars = Object.entries(day.state.styleExposures || {}).map(([name, value]) => `<div class="style-row"><span>${indexes[name] || styles[name] || name}</span><div class="bar"><i style="width:${Math.min(100, value * 100)}%"></i></div><b>${pct(value)}</b></div>`).join('');
  $('#marketView').innerHTML = `<div class="exposure-ring" style="--value:${exposure * 100}"><strong>${pct(exposure)}</strong></div><div class="style-bars"><b>${marketLabel(exposure)}</b><div class="score">${scores}</div>${bars || '<p class="empty">无风格仓位</p>'}</div>`;
}

function renderAllocation(day) {
  const a = day?.allocation, p = day?.portfolio;
  $('#allocationView').innerHTML = [metric('计划仓位', pct(a?.plannedExposure)), metric('可执行仓位', pct(a?.targetExposure)), metric('仓位实现率', pct(a?.fillRate)), metric('未分配资金', money(a?.unallocatedCash)), metric('账户总资产', money(p?.balance)), metric('可用资金', money(p?.cash))].join('');
}

function renderTables(day) {
  $('#sectorRows').innerHTML = day.sectors.length ? day.sectors.map(x => `<tr><td>${styles[x.style] || x.style}</td><td>${x.code}</td><td class="score">${x.score.toFixed(1)}</td></tr>`).join('') : '<tr><td colspan="3" class="empty">当日无入选板块</td></tr>';
  $('#stockRows').innerHTML = day.targets.length ? day.targets.map(x => {
    const records = day.deals.length ? day.deals : day.orders.filter(order => order.status !== 'failed');
    const orders = records.filter(order => order.code === x.code);
    const bought = orders.filter(order => order.side === 'buy').reduce((sum, order) => sum + order.volume, 0);
    const sold = orders.filter(order => order.side === 'sell').reduce((sum, order) => sum + order.volume, 0);
    const executions = [bought ? `买 ${money(bought)}` : '', sold ? `卖 ${money(sold)}` : ''].filter(Boolean).join(' / ');
    return `<tr data-code="${x.code}" class="${x.code === state.stock?.code ? 'selected' : ''}"><td><b>${x.code}</b><br><small>${x.name || '—'}</small></td><td>${styles[x.style] || x.style}</td><td class="score">${x.score.toFixed(1)}</td><td>${money(day.desired[x.code])}<br><small>${executions || '当日无委托'}</small></td></tr>`;
  }).join('') : '<tr><td colspan="4" class="empty">当日无入选个股</td></tr>';
  document.querySelectorAll('[data-code]').forEach(row => row.addEventListener('click', () => selectStock(day.targets.find(x => x.code === row.dataset.code))));
}

function stockTrading(code) {
  return state.report?.stocks?.find(stock => stock.code === code) || null;
}

function populateStockSelect() {
  const stocks = state.report?.stocks || [];
  $('#chartStockSelect').innerHTML = stocks.length
    ? stocks.map(stock => `<option value="${stock.code}">${stock.code}${stock.name ? ` ${stock.name}` : ''} · ${stock.trades.length}笔</option>`).join('')
    : '<option value="">无买卖记录</option>';
}

function diagnostic() {
  const meta = state.report.meta;
  $('#diagnosticText').textContent = [`回测引擎：${meta.engine || '未记录'}`, `开始时间：${meta.startTime || '未记录'}`, `结束时间：${meta.endTime || '未记录'}`, `首根K线：${meta.firstBar || '未记录'}`, ...meta.warnings].join('\n');
}

async function selectStock(stock) {
  if (!stock) { state.stock = null; $('#chartTitle').textContent = '当日没有可选个股'; return; }
  const trading = stockTrading(stock.code);
  state.stock = trading ? { ...stock, ...trading, name: trading.name || stock.name || '' } : stock;
  renderTables(state.day); $('#chartTitle').textContent = `${state.stock.code} ${state.stock.name || ''}`;
  const stockOption = $('#chartStockSelect').querySelector(`option[value="${state.stock.code}"]`);
  if (stockOption) $('#chartStockSelect').value = state.stock.code;
  const trades = trading?.trades || [];
  const sourceLabel = trading?.tradeSource === 'deal' ? '成交' : '有效委托';
  $('#tradeChips').innerHTML = trades.length
    ? `<span class="chip buy">${sourceLabel}买入 ${trading.buyCount}笔 · ${money(trading.buyVolume)}股</span><span class="chip sell">${sourceLabel}卖出 ${trading.sellCount}笔 · ${money(trading.sellVolume)}股</span>${trading.failedCount ? `<span class="chip failed">明确失败 ${trading.failedCount}笔</span>` : ''}<span class="trade-range">${trades[0].date} — ${trades.at(-1).date}</span>`
    : `<span class="empty">该股没有有效委托${trading?.failedCount ? `，明确失败 ${trading.failedCount}笔` : ''}</span>`;
  await renderChart(trades);
}

async function renderChart(trades = []) {
  if (!state.stock) return;
  const endDate = trades.at(-1)?.date || state.day.date;
  const startDate = trades[0]?.date || state.day.date;
  const key = `${state.chartType}:${state.stock.code}:${startDate}:${endDate}`;
  $('#chartLoading').classList.remove('hidden'); $('#chartLoading').textContent = '正在获取腾讯财经行情…';
  try {
    let rows = state.cache.get(key);
    if (!rows) {
      rows = state.chartType === 'daily'
        ? await fetchDaily(state.stock.code, endDate, startDate)
        : await fetchThirtyMinute(state.stock.code, endDate);
      state.cache.set(key, rows);
    }
    const latestTrades = stockTrading(state.stock.code)?.trades || [];
    const latestEndDate = latestTrades.at(-1)?.date || state.day.date;
    const latestStartDate = latestTrades[0]?.date || state.day.date;
    if (key !== `${state.chartType}:${state.stock.code}:${latestStartDate}:${latestEndDate}`) return;
    state.chartRows = rows; state.chartTrades = trades;
    focusLatestCoveredTrade();
    redrawChart();
    $('#chartLoading').classList.add('hidden');
  } catch (error) {
    state.chartRows = []; redrawChart();
    $('#chartLoading').textContent = `${error.message}。评分与交易日志仍可正常查看。`;
  }
}

function chartViewport() {
  const total = state.chartRows.length;
  const bars = Math.min(state.chartView.bars[state.chartType], total);
  const maxOffset = Math.max(total - bars, 0);
  const offset = Math.min(state.chartView.offset[state.chartType], maxOffset);
  state.chartView.offset[state.chartType] = offset;
  return state.chartRows.slice(Math.max(0, total - bars - offset), total - offset);
}

function redrawChart() {
  if (!state.stock) return;
  if (!state.chartRows.length) {
    drawCandles($('#chart'), [], []);
    $('#chartRange').textContent = state.chartType === '30m'
      ? '腾讯财经暂未返回该股票的近期 30 分钟K数据。'
      : '该交易日暂无日K数据。';
    return;
  }
  const rows = chartViewport();
  drawCandles($('#chart'), rows, state.chartTrades, state.chartRows);
  const sourceStart = String(state.chartRows[0].time).replace(/\D/g, '').slice(0, 8);
  const sourceEnd = String(state.chartRows.at(-1).time).replace(/\D/g, '').slice(0, 8);
  const covered = state.chartTrades.filter(trade => {
    const date = String(trade.date || '').replace(/\D/g, '').slice(0, 8);
    return date >= sourceStart && date <= sourceEnd;
  }).length;
  const coverage = state.chartType === 'daily'
    ? '覆盖全部买卖日期'
    : covered
      ? `腾讯分钟行情覆盖 ${covered}/${state.chartTrades.length} 个买卖点`
      : `腾讯分钟行情范围外有 ${state.chartTrades.length} 个买卖点，无法在30分钟K上定位`;
  $('#chartRange').textContent = `${state.chartType === 'daily' ? '日K' : '30 分钟K'} · ${coverage} · 显示 ${rows.length} 根（${rows[0].time} — ${rows.at(-1).time}）。滚轮缩放，图内拖动查看区间，右侧边缘调整宽度。`;
}

function focusLatestCoveredTrade() {
  if (state.chartType !== '30m' || !state.chartRows.length || !state.chartTrades.length) return;
  const tradeDates = new Set(state.chartTrades.map(trade => String(trade.date || '').replace(/\D/g, '').slice(0, 8)));
  let targetIndex = -1;
  state.chartRows.forEach((row, index) => {
    const date = String(row.time || '').replace(/\D/g, '').slice(0, 8);
    if (tradeDates.has(date)) targetIndex = index;
  });
  if (targetIndex < 0) return;
  const bars = Math.min(state.chartView.bars['30m'], state.chartRows.length);
  state.chartView.offset['30m'] = Math.max(0, state.chartRows.length - targetIndex - Math.ceil(bars / 2));
}

function zoomChart(factor) {
  if (!state.chartRows.length) return;
  const current = state.chartView.bars[state.chartType];
  state.chartView.bars[state.chartType] = Math.max(12, Math.min(state.chartRows.length, Math.round(current * factor)));
  redrawChart();
}

function panChart(steps) {
  if (!state.chartRows.length) return;
  const bars = Math.min(state.chartView.bars[state.chartType], state.chartRows.length);
  const maxOffset = Math.max(state.chartRows.length - bars, 0);
  state.chartView.offset[state.chartType] = Math.max(0, Math.min(maxOffset, state.chartView.offset[state.chartType] + steps));
  redrawChart();
}

function resetChartView() {
  state.chartView.bars[state.chartType] = state.chartType === 'daily' ? 80 : 160;
  state.chartView.offset[state.chartType] = 0;
  redrawChart();
}

function selectDay(date) {
  state.day = state.report.days.find(x => x.date === date) || state.report.days.at(-1);
  if (!state.day) return;
  $('#dateSelect').value = state.day.date; renderMarket(state.day); renderAllocation(state.day);
  const currentStock = state.stock && stockTrading(state.stock.code) ? state.stock : null;
  state.stock = currentStock || state.day.targets[0] || state.report.stocks[0] || null;
  renderTables(state.day); selectStock(state.stock);
}

function parse() {
  state.report = parseQmtLog($('#logInput').value);
  const count = state.report.days.length;
  $('#sourceStatus').textContent = count ? `已解析 ${count} 个交易日 · ${state.report.meta.startTime || '未知'} 至 ${state.report.meta.endTime || '未知'}` : '未识别到策略日志';
  $('#dateSelect').innerHTML = state.report.days.map(x => `<option value="${x.date}">${x.date.slice(0,4)}-${x.date.slice(4,6)}-${x.date.slice(6)}</option>`).join('');
  populateStockSelect(); renderOverview(); diagnostic(); if (count) { $('.import-panel').classList.remove('open'); selectDay(state.report.days.at(-1).date); } else $('.import-panel').classList.add('open');
}

$('#sampleButton').addEventListener('click', () => { $('#logInput').value = sampleLog; $('.import-panel').classList.add('open'); parse(); });
$('#parseButton').addEventListener('click', parse);
$('#logInput').addEventListener('focus', () => $('.import-panel').classList.add('open'));
$('#fileInput').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; $('#logInput').value = await file.text(); parse(); });
$('#dateSelect').addEventListener('change', event => selectDay(event.target.value));
$('#chartStockSelect').addEventListener('change', event => {
  const stock = stockTrading(event.target.value);
  if (stock) selectStock(stock);
});
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(x => { const active = x === tab; x.classList.toggle('active', active); x.setAttribute('aria-pressed', String(active)); });
  state.chartType = tab.dataset.chart; selectStock(state.stock);
}));

const chartCard = $('#chartCard');
const resizeHandle = $('#chartResizeHandle');
const minChartWidth = 620;
const chartWidthKey = 'qmt-chart-width';

function chartWidthBounds() {
  return { min: Math.min(minChartWidth, chartCard.parentElement.clientWidth), max: chartCard.parentElement.clientWidth };
}

function setChartWidth(width, persist = false) {
  if (window.matchMedia('(max-width: 800px)').matches) {
    chartCard.style.removeProperty('width');
    redrawChart();
    return;
  }
  const { min, max } = chartWidthBounds();
  const next = Math.round(Math.max(min, Math.min(max, width)));
  chartCard.style.width = `${next}px`;
  resizeHandle.setAttribute('aria-valuemin', String(min));
  resizeHandle.setAttribute('aria-valuemax', String(max));
  resizeHandle.setAttribute('aria-valuenow', String(next));
  if (persist) localStorage.setItem(chartWidthKey, String(next));
  redrawChart();
}

const savedChartWidth = Number(localStorage.getItem(chartWidthKey));
if (Number.isFinite(savedChartWidth) && savedChartWidth > 0) setChartWidth(savedChartWidth);

resizeHandle.addEventListener('pointerdown', event => {
  event.preventDefault();
  const startX = event.clientX, startWidth = chartCard.getBoundingClientRect().width;
  resizeHandle.setPointerCapture(event.pointerId);
  const move = moveEvent => setChartWidth(startWidth + moveEvent.clientX - startX);
  const end = endEvent => {
    setChartWidth(startWidth + endEvent.clientX - startX, true);
    resizeHandle.removeEventListener('pointermove', move);
    resizeHandle.removeEventListener('pointerup', end);
    resizeHandle.removeEventListener('pointercancel', end);
  };
  resizeHandle.addEventListener('pointermove', move);
  resizeHandle.addEventListener('pointerup', end);
  resizeHandle.addEventListener('pointercancel', end);
});
resizeHandle.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
  event.preventDefault();
  const { min, max } = chartWidthBounds();
  const current = chartCard.getBoundingClientRect().width;
  setChartWidth(event.key === 'Home' ? min : event.key === 'End' ? max : current + (event.key === 'ArrowLeft' ? -40 : 40), true);
});
window.addEventListener('resize', () => setChartWidth(chartCard.getBoundingClientRect().width));

const chartCanvas = $('#chart');
chartCanvas.addEventListener('wheel', event => {
  event.preventDefault();
  zoomChart(event.deltaY < 0 ? .8 : 1.25);
}, { passive: false });

chartCanvas.addEventListener('pointerdown', event => {
  if (event.button !== 0 || !state.chartRows.length) return;
  const startX = event.clientX;
  const startOffset = state.chartView.offset[state.chartType];
  const visible = chartViewport().length;
  const step = Math.max((chartCanvas.clientWidth - 62) / Math.max(visible, 1), 1);
  chartCanvas.setPointerCapture(event.pointerId);
  const move = moveEvent => {
    const shiftedBars = Math.round((moveEvent.clientX - startX) / step);
    const bars = Math.min(state.chartView.bars[state.chartType], state.chartRows.length);
    const maxOffset = Math.max(state.chartRows.length - bars, 0);
    state.chartView.offset[state.chartType] = Math.max(0, Math.min(maxOffset, startOffset + shiftedBars));
    redrawChart();
  };
  const end = () => {
    chartCanvas.removeEventListener('pointermove', move);
    chartCanvas.removeEventListener('pointerup', end);
    chartCanvas.removeEventListener('pointercancel', end);
  };
  chartCanvas.addEventListener('pointermove', move);
  chartCanvas.addEventListener('pointerup', end);
  chartCanvas.addEventListener('pointercancel', end);
});

chartCanvas.addEventListener('keydown', event => {
  const key = event.key;
  if (!['+', '=', '-', '_', 'ArrowLeft', 'ArrowRight', 'Home', 'End', '0'].includes(key)) return;
  event.preventDefault();
  if (key === '+' || key === '=') zoomChart(.8);
  else if (key === '-' || key === '_') zoomChart(1.25);
  else if (key === 'ArrowLeft') panChart(Math.max(1, Math.round(state.chartView.bars[state.chartType] / 6)));
  else if (key === 'ArrowRight') panChart(-Math.max(1, Math.round(state.chartView.bars[state.chartType] / 6)));
  else if (key === 'Home') panChart(Number.MAX_SAFE_INTEGER);
  else if (key === 'End') panChart(-Number.MAX_SAFE_INTEGER);
  else resetChartView();
});

$('#logInput').value = sampleLog; parse();
