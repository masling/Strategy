import { parseQmtLog } from './parser.mjs?v=20260811-v210';
import { fetchDaily, fetchThirtyMinute } from './market-data.mjs';
import { candleAtClientPoint, drawCandles, drawScoreSeries } from './chart.mjs';
import { sampleLog } from './sample-log.js';
import {
  actionLabels, importSamples, normalizeSample, readSamples, reasonLabels,
  sampleExport, samplesToCsv, scopeLabels, setupLabels, verdictLabels, writeSamples,
} from './sample-store.mjs?v=20260813-v220';

const $ = selector => document.querySelector(selector);
const state = {
  report: null, day: null, indexCode: '', sectorCode: '', stock: null, chartType: 'daily',
  cache: new Map(), chartRows: [], chartTrades: [], chartRequest: 0, indexRequest: 0,
  sectorChartType: 'kline', candidateStock: null, candidateRequest: 0,
  chartView: { bars: { daily: 80, '30m': 160 }, offset: { daily: 0, '30m': 0 } },
  samples: readSamples(), sampleDraft: null, sampleEditingId: '', sampleCapture: false,
  sampleReturnWorkspace: 'sample', candidateChartRows: [], candidateChartSourceRows: [],
};
const styles = { large: '大盘', mid: '中盘', small: '小盘', growth: '成长' };
const indexes = { '000300.SH': '沪深300', '000905.SH': '中证500', '000852.SH': '中证1000', '399006.SZ': '创业板' };
const regimes = { STRONG: '强势', WATCH: '观察', WARNING: '警戒', EXIT: '退出', OFF: '关闭' };
const statuses = { READY: '可入场', WAIT: '等待', OVEREXTENDED: '过热', HELD: '持有' };
const setups = { trend: '趋势回踩', ma40_starter: 'MA40启动', base_reclaim: '底部收复' };
const pct = value => value == null || !Number.isFinite(Number(value)) ? '—' : `${(Number(value) * 100).toFixed(1)}%`;
const money = value => value == null || !Number.isFinite(Number(value)) ? '—' : new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value);
const ratio = value => value == null || !Number.isFinite(value) ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(2)}%`;
const scoreText = value => value != null && Number.isFinite(Number(value)) ? Number(value).toFixed(1) : '—';
const html = value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
const displayDate = value => { const digits = String(value || '').replace(/\D/g, ''); return digits.length >= 8 ? `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}` : '—'; };
const displayTime = value => { const digits = String(value || '').replace(/\D/g, ''); return digits.length >= 4 ? `${digits.slice(0, 2)}:${digits.slice(2, 4)}${digits.length >= 6 ? `:${digits.slice(4, 6)}` : ''}` : '—'; };

function rowDateTime(row = {}) {
  const digits = String(row.time || '').replace(/\D/g, '');
  return { date: digits.slice(0, 8), time: digits.length >= 12 ? `${digits.slice(8, 12)}00` : '' };
}

function selectedSector() {
  return state.day?.sectors?.find(item => item.code === state.sectorCode && (!state.indexCode || item.style === state.indexCode)) || null;
}

function selectedIndex() {
  return indexEntries(state.day).find(item => item.code === state.indexCode) || null;
}

function sampleSource() {
  return {
    webVersion: '2.2.0', strategy: state.report?.meta?.strategy || state.report?.meta?.engine || '',
    backtestStart: state.report?.meta?.startTime || '', backtestEnd: state.report?.meta?.endTime || '',
  };
}

function contextSnapshot({ stock = null, bar = null, timeframe = '1d' } = {}) {
  const point = rowDateTime(bar || {});
  const decisionDate = point.date || String(state.day?.date || '').replace(/\D/g, '').slice(0, 8);
  const snapshotDay = state.report?.days?.find(day => String(day.date).replace(/\D/g, '').slice(0, 8) === decisionDate) || state.day;
  const stockCode = stock?.code || state.candidateStock?.code || '';
  const datedCandidate = stockCode ? dailyCandidates(snapshotDay).find(item => item.code === stockCode) : null;
  const candidate = datedCandidate || stock || state.candidateStock || null;
  const indexCode = datedCandidate?.style || state.indexCode;
  const index = Object.entries(snapshotDay?.state?.scores || {}).map(([code, raw]) => ({
    code, score: scoreValue(raw), regime: snapshotDay.state.regimes?.[code] || '',
  })).find(item => item.code === indexCode) || null;
  const sectorCode = datedCandidate?.sector || (snapshotDay?.date === state.day?.date ? state.sectorCode : '');
  const sector = snapshotDay?.sectors?.find(item => item.code === sectorCode && (!indexCode || item.style === indexCode)) || null;
  return {
    decisionDate, decisionTime: point.time, timeframe, indexCode,
    indexName: indexes[indexCode] || '', indexScore: index?.score,
    regime: index?.regime || '', exposure: snapshotDay?.state?.exposure,
    sectorCode, sectorScore: sector?.score,
    stockCode: candidate?.code || '', stockName: candidate?.name || '',
    candidate: {
      score: candidate?.score, strength: candidate?.strength, strengthFit: candidate?.strengthFit,
      entry: candidate?.entry, status: candidate?.status, setup: candidate?.setup,
    },
    bar: bar || {},
  };
}

function defaultLabel(scope) {
  return {
    scope, verdict: 'uncertain', action: scope === 'market' || scope === 'sector' ? 'observe' : 'no_trade',
    setup: scope === 'market' ? 'market_regime' : scope === 'sector' ? 'sector_rotation' : 'first_ma13_pullback',
    confidence: 'medium', positionScale: null, reasons: [], summary: '', invalidation: '', notes: '',
  };
}

function beginSample(scope, context, overrides = {}) {
  state.sampleEditingId = '';
  state.sampleDraft = { source: sampleSource(), context, label: { ...defaultLabel(scope), ...overrides } };
  setWorkspace('sample');
  renderSampleForm();
}

function sampleMarkers(code) {
  return state.samples.filter(sample => sample.context?.stockCode === code).map(sample => ({
    date: sample.context.decisionDate, time: sample.context.decisionTime,
    verdict: sample.label.verdict, label: sample.label.action,
  }));
}

function contextToken(label, value) {
  return value == null || value === '' ? '' : `<span class="context-token">${html(label)} ${html(value)}</span>`;
}

function renderSampleForm() {
  const draft = state.sampleDraft;
  if (!draft) {
    $('#sampleContext').className = 'sample-context empty';
    $('#sampleContext').textContent = '从日期复盘、候选股或个股K线发起采集。';
    return;
  }
  const context = draft.context || {}, label = draft.label || {};
  $('#sampleContext').className = 'sample-context';
  $('#sampleContext').innerHTML = `<strong>${html(context.stockCode ? `${context.stockCode} ${context.stockName || ''}` : context.sectorCode || context.indexName || '市场整体')} · ${displayDate(context.decisionDate)}${context.decisionTime ? ` ${displayTime(context.decisionTime)}` : ''}</strong><div class="sample-context-grid">${[
    contextToken('周期', context.timeframe === '30m' ? '30分钟' : '日K'),
    contextToken('指数', context.indexName || context.indexCode), contextToken('指数分', scoreText(context.indexScore)),
    contextToken('状态', regimes[context.regime] || context.regime), contextToken('总仓位', pct(context.exposure)),
    contextToken('板块', context.sectorCode?.replace(/^SW1_?/, '')), contextToken('板块分', scoreText(context.sectorScore)),
    contextToken('入场分', scoreText(context.candidate?.entry)), contextToken('候选状态', context.candidate?.status),
    contextToken('标点收盘', context.bar?.close == null ? '' : Number(context.bar.close).toFixed(2)),
  ].join('')}</div>`;
  $('#sampleScope').value = label.scope || 'stock_selection';
  $('#sampleVerdict').value = label.verdict || 'uncertain';
  $('#sampleAction').value = label.action || 'observe';
  $('#sampleSetup').value = setupLabels[label.setup] ? label.setup : 'custom';
  $('#sampleConfidence').value = label.confidence || 'medium';
  $('#samplePositionScale').value = label.positionScale == null ? '' : String(label.positionScale);
  $('#sampleSummary').value = label.summary || '';
  $('#sampleInvalidation').value = label.invalidation || '';
  $('#sampleNotes').value = label.notes || '';
  document.querySelectorAll('#sampleReasons input').forEach(input => { input.checked = (label.reasons || []).includes(input.value); });
  $('#sampleFormMessage').textContent = state.sampleEditingId ? '正在编辑已有样本' : '';
  $('#sampleFormMessage').className = '';
}

function formLabel() {
  return {
    scope: $('#sampleScope').value, verdict: $('#sampleVerdict').value,
    action: $('#sampleAction').value, setup: $('#sampleSetup').value,
    confidence: $('#sampleConfidence').value,
    positionScale: $('#samplePositionScale').value === '' ? null : Number($('#samplePositionScale').value),
    reasons: [...document.querySelectorAll('#sampleReasons input:checked')].map(input => input.value),
    summary: $('#sampleSummary').value, invalidation: $('#sampleInvalidation').value,
    notes: $('#sampleNotes').value,
  };
}

function renderSampleLibrary() {
  const ordered = [...state.samples].sort((a, b) => `${b.context?.decisionDate || ''}${b.context?.decisionTime || ''}`.localeCompare(`${a.context?.decisionDate || ''}${a.context?.decisionTime || ''}`));
  $('#sampleRows').innerHTML = ordered.length ? ordered.map(sample => {
    const context = sample.context || {}, label = sample.label || {};
    const subject = context.stockCode ? `${context.stockCode} ${context.stockName || ''}` : context.sectorCode?.replace(/^SW1_?/, '') || context.indexName || '市场整体';
    return `<tr><td>${displayDate(context.decisionDate)}<br><small>${context.decisionTime ? displayTime(context.decisionTime) : context.timeframe === '30m' ? '30分钟' : '日K'}</small></td><td>${html(subject)}<br><small>${html(context.indexName || context.indexCode || '')}${context.sectorCode ? ` · ${html(context.sectorCode.replace(/^SW1_?/, ''))}` : ''}</small></td><td>${html(scopeLabels[label.scope] || label.scope)}</td><td><span class="sample-verdict ${html(label.verdict)}">${html(verdictLabels[label.verdict] || label.verdict)}</span><br><small>${html(label.confidence || '')}</small></td><td>${html(actionLabels[label.action] || label.action)}<br><small>${html(setupLabels[label.setup] || label.setup || '—')}</small></td><td>${html(label.summary || '—')}<br><small>${html((label.reasons || []).map(reason => reasonLabels[reason] || reason).join(' · '))}</small></td><td><div class="sample-row-actions"><button type="button" data-sample-edit="${html(sample.id)}">编辑</button><button type="button" data-sample-delete="${html(sample.id)}">删除</button></div></td></tr>`;
  }).join('') : '<tr><td colspan="7" class="empty">尚未采集样本。请从日期复盘、候选股或个股K线开始。</td></tr>';
  const positives = state.samples.filter(sample => sample.label?.verdict === 'positive').length;
  const negatives = state.samples.filter(sample => sample.label?.verdict === 'negative').length;
  $('#sampleLibrarySummary').innerHTML = state.samples.length ? `<strong>共 ${state.samples.length} 条</strong><br>正样本 ${positives} · 反样本 ${negatives} · 待研究 ${state.samples.length - positives - negatives}` : '尚未采集样本';
  document.querySelectorAll('[data-sample-edit]').forEach(button => button.addEventListener('click', () => {
    const sample = state.samples.find(item => item.id === button.dataset.sampleEdit);
    if (!sample) return;
    state.sampleEditingId = sample.id;
    state.sampleDraft = JSON.parse(JSON.stringify(sample));
    renderSampleForm();
    $('#sampleForm').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
  document.querySelectorAll('[data-sample-delete]').forEach(button => button.addEventListener('click', () => {
    if (!window.confirm('确认删除这条样本？删除后只能从已导出的 JSON 恢复。')) return;
    state.samples = state.samples.filter(item => item.id !== button.dataset.sampleDelete);
    writeSamples(state.samples); renderSampleLibrary(); redrawChart(); renderCandidateChart();
  }));
}

function downloadText(filename, content, type) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([content], { type }));
  link.download = filename; link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 0);
}

function scoreValue(raw) {
  const value = raw && typeof raw === 'object' ? raw.score : raw;
  return Number.isFinite(Number(value)) ? Number(value) : null;
}

function marketLabel(exposure) {
  if (exposure >= .7) return '强势 / 可积极参与';
  if (exposure >= .4) return '结构性机会 / 控制节奏';
  if (exposure > 0) return '弱势观察 / 轻仓试错';
  return '风险规避 / 空仓';
}

function metric(label, value) { return `<div class="metric"><small>${html(label)}</small><strong>${html(value)}</strong></div>`; }

function renderOverview() {
  const meta = state.report.meta, stats = state.report.statistics || { tradingDays: state.report.days.length };
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
  const bars = Object.entries(day.state.styleExposures || {}).map(([name, value]) => `<div class="style-row"><span>${html(indexes[name] || styles[name] || name)}</span><div class="bar"><i style="width:${Math.min(100, Number(value) * 100)}%"></i></div><b>${pct(Number(value))}</b></div>`).join('');
  $('#marketView').innerHTML = `<div class="exposure-ring" style="--value:${exposure * 100}"><strong>${pct(exposure)}</strong></div><div class="style-bars"><b>${marketLabel(exposure)}</b>${bars || '<p class="empty">无风格仓位</p>'}</div>`;
}

function renderAllocation(day) {
  const a = day?.allocation, p = day?.portfolio;
  $('#allocationView').innerHTML = [metric('计划仓位', pct(a?.plannedExposure)), metric('可执行仓位', pct(a?.targetExposure)), metric('仓位实现率', pct(a?.fillRate)), metric('未分配资金', money(a?.unallocatedCash)), metric('账户总资产', money(p?.balance)), metric('可用资金', money(p?.cash))].join('');
}

function indexEntries(day) {
  return Object.entries(day?.state?.scores || {}).map(([code, raw]) => ({
    code, score: scoreValue(raw), regime: day.state.regimes?.[code] || '', exposure: Number(day.state.styleExposures?.[code] || 0), riskCap: day.state.riskCaps?.[code],
  })).sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
}

function regimeClass(value) {
  if (value === 'STRONG') return 'strong';
  if (value === 'WATCH') return 'watch';
  return 'off';
}

function renderIndexCards() {
  const entries = indexEntries(state.day);
  if (!entries.some(item => item.code === state.indexCode)) state.indexCode = entries[0]?.code || '';
  $('#indexCards').innerHTML = entries.length ? entries.map(item => `<button class="selection-item ${item.code === state.indexCode ? 'active' : ''}" data-index-code="${html(item.code)}"><span>${html(indexes[item.code] || item.code)}</span><small class="selection-meta"><i class="tag ${regimeClass(item.regime)}">${html(regimes[item.regime] || item.regime || '未记录')}</i><i class="tag">仓位 ${pct(item.exposure)}</i>${item.riskCap == null ? '' : `<i class="tag">上限 ${pct(Number(item.riskCap))}</i>`}</small><strong>${scoreText(item.score)}</strong></button>`).join('') : '<p class="empty">当日无指数评分</p>';
  const counts = state.day.state || {};
  $('#marketSummary').innerHTML = `<strong>总仓位 ${pct(counts.exposure || 0)}</strong><br>储备 ${counts.reserve ?? '—'} · 观察 ${counts.watchlist ?? '—'} · 可入场 ${counts.entryReady ?? '—'}`;
  document.querySelectorAll('[data-index-code]').forEach(button => button.addEventListener('click', () => {
    state.indexCode = button.dataset.indexCode; state.sectorCode = ''; renderIndexCards(); renderSectorStage(); renderCandidates(); renderIndexChart();
  }));
  renderIndexChart();
}

function indexScoreHistory(code) {
  return state.report.days.flatMap(day => {
    const value = scoreValue(day.state?.scores?.[code]);
    return value == null ? [] : [{ time: displayDate(day.date), value }];
  });
}

async function renderIndexChart() {
  const code = state.indexCode, date = state.day?.date;
  $('#indexChartTitle').textContent = code ? `${indexes[code] || code} · ${displayDate(date)}` : '选择指数';
  if (!code || !date) { drawCandles($('#indexChart'), [], []); return; }
  const request = ++state.indexRequest, key = `index:${code}:${date}`;
  $('#indexChartLoading').classList.remove('hidden'); $('#indexChartLoading').textContent = '正在获取指数日K…';
  try {
    let rows = state.cache.get(key);
    if (!rows) { rows = await fetchDaily(code, date, date); state.cache.set(key, rows); }
    if (request !== state.indexRequest) return;
    const end = String(date).replace(/\D/g, '');
    rows = rows.filter(row => String(row.time).replace(/\D/g, '').slice(0, 8) <= end);
    if (rows.length) {
      drawCandles($('#indexChart'), rows.slice(-90), [], rows);
      $('#indexChartNote').textContent = `日K · ${rows.at(-90)?.time || rows[0].time} — ${rows.at(-1).time}，截止当前复盘日，不展示未来行情。`;
    } else {
      drawScoreSeries($('#indexChart'), indexScoreHistory(code), date);
      $('#indexChartNote').textContent = '腾讯指数K线未返回数据，已自动切换为日志中的指数评分趋势。';
    }
    $('#indexChartLoading').classList.add('hidden');
  } catch (error) {
    if (request !== state.indexRequest) return;
    drawScoreSeries($('#indexChart'), indexScoreHistory(code), date);
    $('#indexChartNote').textContent = `${error.message}，已自动切换为指数评分趋势。`;
    $('#indexChartLoading').classList.add('hidden');
  }
}

function renderSectorStage() {
  const sectors = (state.day?.sectors || []).filter(item => !state.indexCode || item.style === state.indexCode);
  if (!sectors.some(item => item.code === state.sectorCode)) {
    const focused = state.day?.sectorFocus?.style === state.indexCode ? state.day.sectorFocus.sector : '';
    state.sectorCode = sectors.some(item => item.code === focused) ? focused : sectors[0]?.code || '';
  }
  $('#sectorCards').innerHTML = sectors.length ? sectors.map(item => `<button class="selection-item ${item.code === state.sectorCode ? 'active' : ''}" data-sector-code="${html(item.code)}"><span>${html(item.code.replace(/^SW1_?/, ''))}</span><small>${html(indexes[item.style] || item.style)}${item.carried ? ' · 延用上次选择' : ''}</small><strong>${scoreText(item.score)}</strong></button>`).join('') : '<p class="empty">该指数当日无入选板块</p>';
  const focus = state.day?.sectorFocus;
  $('#sectorFocus').innerHTML = focus ? `<span class="focus-badge">主线 ${html(focus.sector.replace(/^SW1_?/, ''))} · 基准仓位 ${pct(focus.exposure)}</span>` : '当日无唯一主线记录';
  document.querySelectorAll('[data-sector-code]').forEach(button => button.addEventListener('click', () => {
    state.sectorCode = button.dataset.sectorCode; renderSectorStage(); renderCandidates();
  }));
  renderSectorChart();
}

function renderSectorChart() {
  const code = state.sectorCode, style = state.indexCode;
  const scoreRows = !code ? [] : state.report.days.flatMap(day => {
    const item = day.sectors.find(sector => sector.style === style && sector.code === code);
    return item ? [{ time: displayDate(day.date), value: item.score }] : [];
  });
  if (!code) {
    $('#sectorChartTitle').textContent = '选择板块';
    drawCandles($('#sectorChart'), [], []);
    $('#sectorChartNote').textContent = '当日没有可显示的板块。';
    return;
  }
  if (state.sectorChartType === 'score') {
    $('#sectorChartTitle').textContent = `${code.replace(/^SW1_?/, '')} · 评分历史`;
    drawScoreSeries($('#sectorChart'), scoreRows, state.day?.date);
    $('#sectorChartNote').textContent = scoreRows.length ? `板块评分由策略日志还原，共 ${scoreRows.length} 个交易日；非调仓日延用上次选择结果。` : '日志中没有该板块的评分历史。';
    return;
  }
  const snapshot = state.day?.sectorK?.find(item => item.style === style && item.code === code);
  const end = String(state.day?.date || '').replace(/\D/g, '');
  const rows = (snapshot?.rows || []).filter(row => String(row.time).replace(/\D/g, '').slice(0, 8) <= end);
  if (rows.length) {
    $('#sectorChartTitle').textContent = `${code.replace(/^SW1_?/, '')} · 板块代理日K`;
    drawCandles($('#sectorChart'), rows.slice(-90), [], rows);
    $('#sectorChartNote').textContent = `策略申万成员等权代理K线 · ${rows[0].time} — ${rows.at(-1).time} · MA7 / MA13 / MA40，与板块评分使用同一份QMT行情。`;
  } else {
    $('#sectorChartTitle').textContent = `${code.replace(/^SW1_?/, '')} · 评分历史`;
    drawScoreSeries($('#sectorChart'), scoreRows, state.day?.date);
    $('#sectorChartNote').textContent = '当前日志没有 SECTOR_K，已回退显示评分趋势。同步 V2.4.1 策略并重新回测后可显示板块K线。';
  }
}

function dailyCandidates(day) {
  const items = new Map();
  [...(day.watchlist || []), ...(day.spectators || [])].forEach(item => items.set(item.code, { ...item }));
  (day.targets || []).forEach(item => items.set(item.code, { ...(items.get(item.code) || {}), ...item, status: 'READY' }));
  return [...items.values()];
}

function statusPill(value) {
  const key = String(value || 'WAIT').toUpperCase();
  return `<span class="status-pill ${key.toLowerCase()}">${html(statuses[key] || key)}</span>`;
}

function renderCandidates() {
  let items = dailyCandidates(state.day).filter(item => !state.indexCode || !item.style || item.style === state.indexCode);
  const hasSectorLink = items.some(item => item.sector);
  if (hasSectorLink && state.sectorCode) items = items.filter(item => item.sector === state.sectorCode);
  items.sort((a, b) => (Number(b.entry) || -1) - (Number(a.entry) || -1));
  if (!items.some(item => item.code === state.candidateStock?.code)) state.candidateStock = items[0] || null;
  const records = state.day.deals.length ? state.day.deals : state.day.orders.filter(order => order.status !== 'failed');
  $('#candidateRows').innerHTML = items.length ? items.map(item => {
    const actions = records.filter(record => record.code === item.code);
    const bought = actions.filter(record => record.side === 'buy').reduce((sum, record) => sum + record.volume, 0);
    const sold = actions.filter(record => record.side === 'sell').reduce((sum, record) => sum + record.volume, 0);
    const actionText = [bought ? `买 ${money(bought)}` : '', sold ? `卖 ${money(sold)}` : ''].filter(Boolean).join(' / ') || '当日无操作';
    return `<tr data-stock-code="${html(item.code)}" class="${item.code === state.candidateStock?.code ? 'selected' : ''}"><td><button class="candidate-link">${html(item.code)}</button><br><small>${html(item.name || '—')}</small></td><td>${html(item.sector ? item.sector.replace(/^SW1_?/, '') : indexes[item.style] || item.style || '—')}</td><td class="score">${scoreText(item.score)}</td><td>${scoreText(item.strength)}</td><td>${scoreText(item.strengthFit)}</td><td class="score">${scoreText(item.entry)}</td><td>${statusPill(item.status)}${item.setup ? `<br><small>${html(setups[item.setup] || item.setup)}</small>` : ''}</td><td>${money(state.day.desired[item.code])}<br><small>${actionText}</small></td></tr>`;
  }).join('') : '<tr><td colspan="8" class="empty">当日无对应个股记录</td></tr>';
  $('#candidateTitle').textContent = `${indexes[state.indexCode] || state.indexCode || '未选指数'}${state.sectorCode ? ` · ${state.sectorCode.replace(/^SW1_?/, '')}` : ''}`;
  $('#candidateLegend').innerHTML = '<span class="tag ready">可入场</span><span class="tag watch">等待</span><span class="tag overextended">过热</span>';
  $('#candidateNote').textContent = hasSectorLink ? '个股已按日志中的板块归属精确过滤。' : '当前日志未记录个股的板块归属，因此展示该指数下的全部观察股，不做错误的板块映射。';
  document.querySelectorAll('[data-stock-code]').forEach(row => row.addEventListener('click', () => {
    state.candidateStock = items.find(item => item.code === row.dataset.stockCode) || null;
    renderCandidates();
  }));
  $('#openStockDetail').disabled = !state.candidateStock;
  $('#sampleCandidate').disabled = !state.candidateStock;
  renderCandidateChart();
}

async function renderCandidateChart() {
  const candidate = state.candidateStock, date = state.day?.date;
  if (!candidate || !date) {
    state.candidateChartRows = []; state.candidateChartSourceRows = [];
    $('#candidateChartTitle').textContent = '选择候选股';
    $('#candidateChartNote').textContent = '当日没有可显示的候选股。';
    $('#candidateChartLoading').classList.add('hidden');
    drawCandles($('#candidateChart'), [], []);
    return;
  }
  const code = candidate.code, request = ++state.candidateRequest;
  $('#candidateChartTitle').textContent = `${code} ${candidate.name || ''}`;
  $('#candidateChartLoading').classList.remove('hidden');
  $('#candidateChartLoading').textContent = '正在获取候选股日K…';
  try {
    const key = `daily:${code}:${date}:${date}`;
    let rows = state.cache.get(key);
    if (!rows) { rows = await fetchDaily(code, date, date); state.cache.set(key, rows); }
    if (request !== state.candidateRequest || state.candidateStock?.code !== code || state.day?.date !== date) return;
    const end = String(date).replace(/\D/g, '');
    rows = rows.filter(row => String(row.time).replace(/\D/g, '').slice(0, 8) <= end);
    state.candidateChartSourceRows = rows;
    state.candidateChartRows = rows.slice(-90);
    const trades = stockTrading(code)?.trades || [];
    drawCandles($('#candidateChart'), state.candidateChartRows, trades, rows, sampleMarkers(code));
    $('#candidateChartNote').textContent = rows.length
      ? `日K · ${rows[0].time} — ${rows.at(-1).time} · MA7 / MA13 / MA40 · 入场评分 ${scoreText(candidate.entry)}，截止当前复盘日。`
      : '腾讯财经未返回该股在当前复盘日之前的日K。';
    $('#candidateChartLoading').classList.add('hidden');
  } catch (error) {
    if (request !== state.candidateRequest) return;
    state.candidateChartRows = []; state.candidateChartSourceRows = [];
    drawCandles($('#candidateChart'), [], []);
    $('#candidateChartNote').textContent = `${error.message}，候选股评分仍可正常查看。`;
    $('#candidateChartLoading').classList.add('hidden');
  }
}

function stockTrading(code) { return state.report?.stocks?.find(stock => stock.code === code) || null; }

function candidateFor(code) {
  for (let index = (state.report?.days?.length || 0) - 1; index >= 0; index -= 1) {
    const candidate = dailyCandidates(state.report.days[index]).find(item => item.code === code);
    if (candidate) return candidate;
  }
  return null;
}

function filteredStocks(query = $('#stockFilterInput')?.value || '') {
  const keyword = String(query).trim().toUpperCase();
  return (state.report?.stocks || []).filter(stock => !keyword || `${stock.code || ''} ${stock.name || ''}`.toUpperCase().includes(keyword));
}

function populateStockSelect() {
  const select = $('#chartStockSelect'), stocks = filteredStocks();
  select.innerHTML = stocks.length ? stocks.map(stock => `<option value="${html(stock.code)}">${html(stock.code)}${stock.name ? ` ${html(stock.name)}` : ''} · ${stock.trades.length}笔</option>`).join('') : '<option value="" disabled>无匹配股票</option>';
  select.disabled = !stocks.length;
  if (state.stock && stocks.some(stock => stock.code === state.stock.code)) select.value = state.stock.code;
  return stocks;
}

function renderTradeLedger(trading) {
  const activity = [...(trading?.activity || [])].sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`));
  $('#tradeRows').innerHTML = activity.length ? activity.map(record => {
    const filled = record.status === 'filled', cancelled = record.status === 'cancelled', failed = record.status === 'failed' || cancelled;
    const status = filled ? '已成交' : cancelled ? '已撤单' : failed ? '明确失败' : record.status === 'queued' ? '排队待提交' : '已委托（成交未知）';
    return `<tr><td>${displayDate(record.date)}</td><td>${displayTime(record.time)}</td><td><span class="status-pill side-${record.side}">${record.side === 'buy' ? '买入' : '卖出'}</span></td><td>${money(record.volume)}</td><td>${record.price == null ? '—' : Number(record.price).toFixed(2)}</td><td><span class="status-pill status-${filled ? 'filled' : failed ? 'failed' : 'submitted'}">${status}</span></td><td>${html(record.failureReason || record.reason || '—')}</td></tr>`;
  }).join('') : '<tr><td colspan="7" class="empty">该股没有买卖记录</td></tr>';
  $('#ledgerSummary').innerHTML = trading ? `<strong>买 ${trading.buyCount}笔 / ${money(trading.buyVolume)}股 · 卖 ${trading.sellCount}笔 / ${money(trading.sellVolume)}股</strong><br>${trading.tradeSource === 'deal' ? '以 DEAL 实际成交为准' : '无 DEAL 日志，仅能确认委托'}${trading.failedCount ? ` · 失败 ${trading.failedCount}笔` : ''}` : '该股无操盘记录';
}

async function selectStock(stock) {
  if (!stock) { state.stock = null; $('#chartTitle').textContent = '没有可选个股'; renderTradeLedger(null); return; }
  const trading = stockTrading(stock.code), candidate = candidateFor(stock.code);
  state.stock = { ...(candidate || {}), ...stock, ...(trading || {}), name: trading?.name || stock.name || candidate?.name || '' };
  $('#chartTitle').textContent = `${state.stock.code} ${state.stock.name || ''}`;
  if ([...$('#chartStockSelect').options].some(option => option.value === state.stock.code)) $('#chartStockSelect').value = state.stock.code;
  const trades = trading?.trades || [], sourceLabel = trading?.tradeSource === 'deal' ? '成交' : '有效委托';
  $('#tradeChips').innerHTML = trades.length ? `<span class="chip buy">${sourceLabel}买入 ${trading.buyCount}笔 · ${money(trading.buyVolume)}股</span><span class="chip sell">${sourceLabel}卖出 ${trading.sellCount}笔 · ${money(trading.sellVolume)}股</span>${trading.failedCount ? `<span class="chip failed">明确失败 ${trading.failedCount}笔</span>` : ''}<span class="trade-range">${displayDate(trades[0].date)} — ${displayDate(trades.at(-1).date)}</span>` : `<span class="empty">该股没有有效买卖记录${trading?.failedCount ? `，明确失败 ${trading.failedCount}笔` : ''}</span>`;
  renderTradeLedger(trading); await renderChart(trades);
}

async function renderChart(trades = []) {
  if (!state.stock) return;
  const endDate = trades.at(-1)?.date || state.day?.date, startDate = trades[0]?.date || state.day?.date;
  const code = state.stock.code, type = state.chartType, request = ++state.chartRequest;
  const key = `${type}:${code}:${startDate}:${endDate}`;
  $('#chartLoading').classList.remove('hidden'); $('#chartLoading').textContent = '正在获取腾讯财经行情…';
  try {
    let rows = state.cache.get(key);
    if (!rows) { rows = type === 'daily' ? await fetchDaily(code, endDate, startDate) : await fetchThirtyMinute(code, endDate); state.cache.set(key, rows); }
    if (request !== state.chartRequest || state.stock?.code !== code || state.chartType !== type) return;
    state.chartRows = rows; state.chartTrades = trades; focusLatestCoveredTrade(); redrawChart(); $('#chartLoading').classList.add('hidden');
  } catch (error) {
    if (request !== state.chartRequest) return;
    state.chartRows = []; redrawChart(); $('#chartLoading').textContent = `${error.message}。买卖明细仍可正常查看。`;
  }
}

function chartViewport() {
  const total = state.chartRows.length, bars = Math.min(state.chartView.bars[state.chartType], total), maxOffset = Math.max(total - bars, 0);
  const offset = Math.min(state.chartView.offset[state.chartType], maxOffset); state.chartView.offset[state.chartType] = offset;
  return state.chartRows.slice(Math.max(0, total - bars - offset), total - offset);
}

function redrawChart() {
  if (!state.stock) return;
  if (!state.chartRows.length) { drawCandles($('#chart'), [], []); $('#chartRange').textContent = state.chartType === '30m' ? '腾讯财经暂未返回该股票的近期30分钟K数据。' : '该交易日暂无日K数据。'; return; }
  const rows = chartViewport(); drawCandles($('#chart'), rows, state.chartTrades, state.chartRows, sampleMarkers(state.stock.code));
  const sourceStart = String(state.chartRows[0].time).replace(/\D/g, '').slice(0, 8), sourceEnd = String(state.chartRows.at(-1).time).replace(/\D/g, '').slice(0, 8);
  const covered = state.chartTrades.filter(trade => { const date = String(trade.date || '').replace(/\D/g, '').slice(0, 8); return date >= sourceStart && date <= sourceEnd; }).length;
  const coverage = state.chartType === 'daily' ? '覆盖全部买卖日期' : covered ? `分钟行情覆盖 ${covered}/${state.chartTrades.length} 个买卖点` : `有 ${state.chartTrades.length} 个买卖点在分钟行情范围外`;
  $('#chartRange').textContent = `${state.chartType === 'daily' ? '日K' : '30 分钟K'} · ${coverage} · 显示 ${rows.length} 根（${rows[0].time} — ${rows.at(-1).time}）。滚轮缩放，图内拖动查看区间。`;
}

function focusLatestCoveredTrade() {
  if (state.chartType !== '30m' || !state.chartRows.length || !state.chartTrades.length) return;
  const dates = new Set(state.chartTrades.map(trade => String(trade.date || '').replace(/\D/g, '').slice(0, 8)));
  let target = -1; state.chartRows.forEach((row, index) => { if (dates.has(String(row.time || '').replace(/\D/g, '').slice(0, 8))) target = index; });
  if (target < 0) return;
  const bars = Math.min(state.chartView.bars['30m'], state.chartRows.length); state.chartView.offset['30m'] = Math.max(0, state.chartRows.length - target - Math.ceil(bars / 2));
}

function zoomChart(factor) { if (!state.chartRows.length) return; state.chartView.bars[state.chartType] = Math.max(12, Math.min(state.chartRows.length, Math.round(state.chartView.bars[state.chartType] * factor))); redrawChart(); }
function panChart(steps) { if (!state.chartRows.length) return; const bars = Math.min(state.chartView.bars[state.chartType], state.chartRows.length), max = Math.max(state.chartRows.length - bars, 0); state.chartView.offset[state.chartType] = Math.max(0, Math.min(max, state.chartView.offset[state.chartType] + steps)); redrawChart(); }
function resetChartView() { state.chartView.bars[state.chartType] = state.chartType === 'daily' ? 80 : 160; state.chartView.offset[state.chartType] = 0; redrawChart(); }

function selectDay(date) {
  state.day = state.report.days.find(day => day.date === date) || state.report.days[0];
  if (!state.day) return;
  const index = state.report.days.findIndex(day => day.date === state.day.date);
  $('#dateSelect').value = state.day.date;
  $('#previousDay').disabled = index <= 0; $('#nextDay').disabled = index >= state.report.days.length - 1;
  $('#dateProgress').textContent = `第 ${index + 1} / ${state.report.days.length} 天`;
  renderMarket(state.day); renderAllocation(state.day); renderIndexCards(); renderSectorStage(); renderCandidates();
}

function stepDay(offset) {
  if (!state.day || !state.report?.days?.length) return;
  const index = state.report.days.findIndex(day => day.date === state.day.date);
  const next = Math.max(0, Math.min(state.report.days.length - 1, index + offset));
  if (next !== index) selectDay(state.report.days[next].date);
}

function diagnostic() {
  const meta = state.report.meta;
  const legacyLinks = state.report.days.some(day => day.watchlist.some(item => !item.sector));
  $('#diagnosticText').textContent = [`Web版本：V2.2.0 (2026-08-13)`, `回测引擎：${meta.engine || '未记录'}`, `开始时间：${meta.startTime || '未记录'}`, `结束时间：${meta.endTime || '未记录'}`, `首根K线：${meta.firstBar || '未记录'}`, `本地研究样本：${state.samples.length} 条`, legacyLinks ? '提示：当前日志没有个股板块归属字段，Web按指数显示观察池。' : '', ...meta.warnings].filter(Boolean).join('\n');
}

function parse() {
  state.report = parseQmtLog($('#logInput').value); state.cache.clear(); state.indexCode = ''; state.sectorCode = ''; state.stock = null; state.candidateStock = null; $('#stockFilterInput').value = '';
  const count = state.report.days.length;
  $('#sourceStatus').textContent = count ? `已解析 ${count} 个交易日 · ${state.report.meta.startTime || '未知'} 至 ${state.report.meta.endTime || '未知'}` : '未识别到策略日志';
  $('#dateSelect').innerHTML = state.report.days.map(day => `<option value="${html(day.date)}">${displayDate(day.date)}</option>`).join('');
  populateStockSelect(); renderOverview(); diagnostic();
  if (count) {
    $('.import-panel').classList.remove('open'); $('#pasteButton').setAttribute('aria-expanded', 'false'); selectDay(state.report.days[0].date);
    const firstStock = state.report.stocks[0]; if (firstStock) selectStock(firstStock);
  } else $('.import-panel').classList.add('open');
}

function setWorkspace(name) {
  document.querySelectorAll('.workspace').forEach(section => section.classList.toggle('active', section.id === `${name}Workspace`));
  document.querySelectorAll('.workspace-tab').forEach(tab => { const active = tab.dataset.workspace === name; tab.classList.toggle('active', active); tab.setAttribute('aria-pressed', String(active)); });
  if (name === 'stock') requestAnimationFrame(redrawChart);
  if (name === 'sample') { renderSampleForm(); renderSampleLibrary(); }
}

$('#sampleButton').addEventListener('click', () => { $('#logInput').value = sampleLog; $('.import-panel').classList.add('open'); parse(); });
$('#pasteButton').addEventListener('click', () => {
  $('.import-panel').classList.add('open'); $('#pasteButton').setAttribute('aria-expanded', 'true');
  $('#logInput').focus(); $('#logInput').select();
});
$('#parseButton').addEventListener('click', parse);
$('#logInput').addEventListener('focus', () => { $('.import-panel').classList.add('open'); $('#pasteButton').setAttribute('aria-expanded', 'true'); });
$('#logInput').addEventListener('keydown', event => { if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') parse(); });
$('#fileInput').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; $('#logInput').value = await file.text(); parse(); });
$('#dateSelect').addEventListener('change', event => selectDay(event.target.value));
$('#previousDay').addEventListener('click', () => stepDay(-1));
$('#nextDay').addEventListener('click', () => stepDay(1));
$('#stockFilterInput').addEventListener('input', () => {
  const stocks = populateStockSelect();
  if (stocks.length === 1 && stocks[0].code !== state.stock?.code) selectStock(stocks[0]);
});
$('#chartStockSelect').addEventListener('change', event => { const stock = stockTrading(event.target.value); if (stock) selectStock(stock); });
document.querySelectorAll('.workspace-tab').forEach(tab => tab.addEventListener('click', () => setWorkspace(tab.dataset.workspace)));
document.querySelectorAll('.sector-tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.sector-tab').forEach(item => { const active = item === tab; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  state.sectorChartType = tab.dataset.sectorChart; renderSectorChart();
}));
$('#openStockDetail').addEventListener('click', () => {
  if (!state.candidateStock) return;
  setWorkspace('stock'); selectStock(state.candidateStock);
});
$('#sampleReview').addEventListener('click', () => {
  const scope = state.sectorCode ? 'sector' : 'market';
  beginSample(scope, contextSnapshot(), {
    action: 'observe', setup: scope === 'market' ? 'market_regime' : 'sector_rotation',
    reasons: scope === 'market' ? ['market'] : ['market', 'sector'],
  });
});
$('#sampleCandidate').addEventListener('click', () => {
  if (!state.candidateStock) return;
  const date = String(state.day?.date || '').replace(/\D/g, '').slice(0, 8);
  const bar = state.candidateChartSourceRows.find(row => String(row.time || '').replace(/\D/g, '').slice(0, 8) === date) || null;
  beginSample('stock_selection', contextSnapshot({ stock: state.candidateStock, bar, timeframe: '1d' }), {
    action: 'no_trade', reasons: ['market', 'sector', 'lifecycle', 'ma_structure'],
  });
});
document.querySelectorAll('.tab').forEach(tab => tab.addEventListener('click', () => {
  document.querySelectorAll('.tab').forEach(item => { const active = item === tab; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  state.chartType = tab.dataset.chart; selectStock(state.stock);
}));

function setSampleCapture(active) {
  state.sampleCapture = active;
  $('#sampleChartPoint').classList.toggle('sample-capture-active', active);
  $('.stock-chart').classList.toggle('capture', active);
  $('#sampleChartPoint').textContent = active ? '取消标点' : '在K线上标点采样';
}

$('#sampleChartPoint').addEventListener('click', () => {
  if (!state.stock) return;
  state.sampleReturnWorkspace = 'sample';
  setSampleCapture(!state.sampleCapture);
});

$('#samplePickPoint').addEventListener('click', async () => {
  if (state.sampleDraft) state.sampleDraft.label = formLabel();
  const code = state.sampleDraft?.context?.stockCode || state.stock?.code;
  if (!code) {
    $('#sampleFormMessage').textContent = '当前样本没有股票，市场/板块判断不需要K线标点。';
    $('#sampleFormMessage').className = 'error';
    return;
  }
  const candidate = candidateFor(code) || { code, name: state.sampleDraft?.context?.stockName || '' };
  state.sampleReturnWorkspace = 'sample';
  setWorkspace('stock');
  await selectStock(candidate);
  setSampleCapture(true);
});

$('#sampleForm').addEventListener('submit', event => {
  event.preventDefault();
  const message = $('#sampleFormMessage');
  try {
    const existing = state.samples.find(item => item.id === state.sampleEditingId);
    const sample = normalizeSample({
      ...(existing || {}), ...(state.sampleDraft || {}), id: state.sampleEditingId || state.sampleDraft?.id,
      label: formLabel(), source: sampleSource(),
    });
    state.samples = existing ? state.samples.map(item => item.id === existing.id ? sample : item) : [...state.samples, sample];
    writeSamples(state.samples); state.sampleEditingId = sample.id; state.sampleDraft = JSON.parse(JSON.stringify(sample));
    message.textContent = '样本已保存到本机浏览器'; message.className = 'success';
    renderSampleLibrary(); redrawChart(); renderCandidateChart();
  } catch (error) {
    message.textContent = error.message; message.className = 'error';
  }
});

$('#sampleReset').addEventListener('click', () => {
  state.sampleEditingId = ''; state.sampleDraft = null; $('#sampleForm').reset();
  renderSampleForm(); $('#sampleFormMessage').textContent = '';
});

$('#sampleExportJson').addEventListener('click', () => {
  const payload = sampleExport(state.samples, sampleSource());
  downloadText(`qmt-standard-samples-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(payload, null, 2), 'application/json;charset=utf-8');
});
$('#sampleExportCsv').addEventListener('click', () => {
  downloadText(`qmt-standard-samples-${new Date().toISOString().slice(0, 10)}.csv`, `\ufeff${samplesToCsv(state.samples)}`, 'text/csv;charset=utf-8');
});
$('#sampleImport').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  const message = $('#sampleFormMessage');
  try {
    const imported = importSamples(await file.text());
    const byId = new Map(state.samples.map(sample => [sample.id, sample]));
    imported.forEach(sample => byId.set(sample.id, sample));
    state.samples = [...byId.values()]; writeSamples(state.samples); renderSampleLibrary();
    message.textContent = `已导入 ${imported.length} 条样本`; message.className = 'success';
  } catch (error) {
    message.textContent = `导入失败：${error.message}`; message.className = 'error';
  } finally { event.target.value = ''; }
});

const chartCard = $('#chartCard'), resizeHandle = $('#chartResizeHandle'), minChartWidth = 620, chartWidthKey = 'qmt-chart-width-v2';
function chartWidthBounds() { return { min: Math.min(minChartWidth, chartCard.parentElement.clientWidth), max: chartCard.parentElement.clientWidth }; }
function setChartWidth(width, persist = false) {
  if (window.matchMedia('(max-width: 900px)').matches) { chartCard.style.removeProperty('width'); redrawChart(); return; }
  const { min, max } = chartWidthBounds(), next = Math.round(Math.max(min, Math.min(max, width))); chartCard.style.width = `${next}px`;
  resizeHandle.setAttribute('aria-valuemin', String(min)); resizeHandle.setAttribute('aria-valuemax', String(max)); resizeHandle.setAttribute('aria-valuenow', String(next));
  if (persist) localStorage.setItem(chartWidthKey, String(next)); redrawChart();
}
const savedChartWidth = Number(localStorage.getItem(chartWidthKey)); if (Number.isFinite(savedChartWidth) && savedChartWidth > 0) setChartWidth(savedChartWidth);
resizeHandle.addEventListener('pointerdown', event => {
  event.preventDefault(); const startX = event.clientX, startWidth = chartCard.getBoundingClientRect().width; resizeHandle.setPointerCapture(event.pointerId);
  const move = moveEvent => setChartWidth(startWidth + moveEvent.clientX - startX);
  const end = endEvent => { setChartWidth(startWidth + endEvent.clientX - startX, true); resizeHandle.removeEventListener('pointermove', move); resizeHandle.removeEventListener('pointerup', end); resizeHandle.removeEventListener('pointercancel', end); };
  resizeHandle.addEventListener('pointermove', move); resizeHandle.addEventListener('pointerup', end); resizeHandle.addEventListener('pointercancel', end);
});
resizeHandle.addEventListener('keydown', event => {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return; event.preventDefault(); const { min, max } = chartWidthBounds(), current = chartCard.getBoundingClientRect().width;
  setChartWidth(event.key === 'Home' ? min : event.key === 'End' ? max : current + (event.key === 'ArrowLeft' ? -40 : 40), true);
});
window.addEventListener('resize', () => setChartWidth(chartCard.getBoundingClientRect().width));

const chartCanvas = $('#chart');
chartCanvas.addEventListener('wheel', event => { event.preventDefault(); zoomChart(event.deltaY < 0 ? .8 : 1.25); }, { passive: false });
chartCanvas.addEventListener('pointerdown', event => {
  if (state.sampleCapture) return;
  if (event.button !== 0 || !state.chartRows.length) return;
  const startX = event.clientX, startOffset = state.chartView.offset[state.chartType], visible = chartViewport().length, step = Math.max((chartCanvas.clientWidth - 62) / Math.max(visible, 1), 1);
  chartCanvas.setPointerCapture(event.pointerId);
  const move = moveEvent => { const shifted = Math.round((moveEvent.clientX - startX) / step), bars = Math.min(state.chartView.bars[state.chartType], state.chartRows.length), max = Math.max(state.chartRows.length - bars, 0); state.chartView.offset[state.chartType] = Math.max(0, Math.min(max, startOffset + shifted)); redrawChart(); };
  const end = () => { chartCanvas.removeEventListener('pointermove', move); chartCanvas.removeEventListener('pointerup', end); chartCanvas.removeEventListener('pointercancel', end); };
  chartCanvas.addEventListener('pointermove', move); chartCanvas.addEventListener('pointerup', end); chartCanvas.addEventListener('pointercancel', end);
});
chartCanvas.addEventListener('click', event => {
  if (!state.sampleCapture || !state.stock) return;
  const rows = chartViewport(), hit = candleAtClientPoint(chartCanvas, rows, event.clientX, event.clientY);
  if (!hit) return;
  const existingLabel = state.sampleDraft?.label || defaultLabel('trade_point');
  state.sampleDraft = {
    ...(state.sampleDraft || {}), source: sampleSource(),
    context: contextSnapshot({ stock: state.stock, bar: hit.row, timeframe: state.chartType }),
    label: { ...existingLabel, scope: existingLabel.scope || 'trade_point' },
  };
  setSampleCapture(false); setWorkspace(state.sampleReturnWorkspace || 'sample'); renderSampleForm();
  $('#sampleFormMessage').textContent = `已选择 ${hit.row.time} 的K线`;
  $('#sampleFormMessage').className = 'success';
});
chartCanvas.addEventListener('keydown', event => {
  if (!['+', '=', '-', '_', 'ArrowLeft', 'ArrowRight', 'Home', 'End', '0'].includes(event.key)) return; event.preventDefault();
  if (event.key === '+' || event.key === '=') zoomChart(.8); else if (event.key === '-' || event.key === '_') zoomChart(1.25); else if (event.key === 'ArrowLeft') panChart(Math.max(1, Math.round(state.chartView.bars[state.chartType] / 6))); else if (event.key === 'ArrowRight') panChart(-Math.max(1, Math.round(state.chartView.bars[state.chartType] / 6))); else if (event.key === 'Home') panChart(Number.MAX_SAFE_INTEGER); else if (event.key === 'End') panChart(-Number.MAX_SAFE_INTEGER); else resetChartView();
});

$('#sampleReasons').innerHTML = Object.entries(reasonLabels).map(([value, label]) => `<label class="reason-option"><input type="checkbox" value="${html(value)}">${html(label)}</label>`).join('');
renderSampleLibrary();
$('#logInput').value = sampleLog; parse();
