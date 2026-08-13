export const SAMPLE_SCHEMA_VERSION = 3;
export const SAMPLE_STORAGE_KEY = 'qmt-standard-samples-v3';
const PREVIOUS_STORAGE_KEYS = ['qmt-standard-samples-v2'];

const clean = value => String(value ?? '').trim();
const finite = value => Number.isFinite(Number(value)) ? Number(value) : null;

export const scopeLabels = {
  market: '市场判断', sector: '板块判断', stock_selection: '个股选择', trade_point: '买卖点',
};

export const verdictLabels = {
  positive: '正样本', negative: '反样本', uncertain: '待研究',
};

export const actionLabels = {
  observe: '观察', no_trade: '不参与', open: '首仓', add: '加仓', addback: '加回',
  hold: '继续持有', trim: '减交易仓', reduce_core: '减主仓', exit: '清仓',
  risk_on: '提高仓位', risk_off: '降低仓位',
};

export const setupLabels = {
  first_ma13_pullback: '首次深回MA13', ma7_trend_hold: 'MA7趋势支撑',
  ma40_restart: 'MA40启动/再启动', bottom_cross: '底部7/13交叉',
  ma13_addback: 'MA13加回', volume_spike_fade: '冲高回落',
  failed_reclaim: '收复失败', ma13_breakdown: 'MA13破位',
  sector_rotation: '板块轮动', market_regime: '市场状态', custom: '其他形态',
};

export const reasonLabels = {
  market: '市场环境', sector: '板块阶段', relative_strength: '相对强度',
  lifecycle: '生命周期', ma_structure: '均线结构', space: '空间', time: '时间',
  volume: '量能', overhead_supply: '筹码/套牢区', intraday: '盘中确认',
  liquidity: '流动性', execution: '仓位/执行',
};

export const marketStateLabels = {
  strong: '强势', rotation: '结构轮动', weak: '弱势但有活跃板块', risk_window: '风险窗口', unknown: '待判断',
};

export const sectorStageLabels = {
  startup: '启动', advance: '主升', first_pullback: '首次回调', range: '震荡', decline: '衰退', unknown: '待判断',
};

export const lifecycleLabels = {
  bottom_start: '底部启动', first_ma7_pullback: '首次MA7回调', first_ma13_pullback: '首次MA13深回',
  second_pullback: '二次回调', high_range: '高位震荡', breakdown: '破位阶段', unknown: '待判断',
};

export const maStructureLabels = {
  smooth: '均线流畅', balanced_gap: '开口相对均衡', wide_713: 'MA7/13开口过大', wide_1340: 'MA13/40开口过大',
  ma7_flat: 'MA7走平', ma7_down: 'MA7下弯', ma13_flat: 'MA13走平', ma40_down: 'MA40向下', compressed: '均线粘合',
};

export const pullbackPathLabels = {
  direct_ma13: '高点直接回MA13', via_ma7_rebound: 'MA7反弹后再回落', platform_break: '平台破位后回落',
  slow_decline: '缓慢阴跌', no_pullback: '非回调形态', unknown: '待判断',
};

export const spaceStateLabels = {
  sufficient: '空间充分', neutral: '空间一般', insufficient: '空间不足', overheated: '位置过热', unknown: '待判断',
};

export const timingStateLabels = {
  sufficient: '调整充分', short: '调整偏短', too_long: '拖延过久', not_applicable: '不适用', unknown: '待判断',
};

export const volumePatternLabels = {
  shrink_pullback: '缩量回调', volume_support: '放量承接', weak_rebound: '无量反弹', spike_fade: '放量冲高回落',
  volume_divergence: '量价背离', normal: '量能中性',
};

export const overheadSupplyLabels = {
  none: '无明显压力', light: '轻度成交平台', dense: '密集套牢区', unknown: '待判断',
};

export const intradayConfirmLabels = {
  two_bar_reclaim: '连续两根30分钟站回', single_reclaim: '单根站回', unconfirmed: '尚未收复',
  close_failed: '盘中收复但尾盘失守', not_checked: '未核对30分钟', not_applicable: '不适用',
};

export const invalidationRuleLabels = {
  break_ma7: '收盘跌破MA7', break_ma13: '收盘跌破MA13', next_day_unconfirmed: '次日一小时未确认',
  sector_break: '板块趋势破位', market_risk: '市场进入风险窗口', volume_failure: '承接量能消失', custom: '其他条件',
};

function idValue() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `sample-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function normalizedBar(bar = {}) {
  return {
    time: clean(bar.time), open: finite(bar.open), high: finite(bar.high),
    low: finite(bar.low), close: finite(bar.close), volume: finite(bar.volume),
    amount: finite(bar.amount),
  };
}

function normalizedCandidate(candidate = {}) {
  return {
    score: finite(candidate.score), strength: finite(candidate.strength),
    strengthFit: finite(candidate.strengthFit), entry: finite(candidate.entry),
    status: clean(candidate.status), setup: clean(candidate.setup),
  };
}

function uniqueList(value) {
  return [...new Set((Array.isArray(value) ? value : []).map(clean).filter(Boolean))];
}

function normalizedTechnical(technical = {}) {
  return Object.fromEntries([
    'ma7', 'ma13', 'ma40', 'ma7Slope3Pct', 'ma13Slope3Pct', 'ma40Slope3Pct',
    'gap713Pct', 'gap1340Pct', 'gapBalanceRatio', 'closeMa7BiasPct', 'closeMa13BiasPct',
    'closeMa40BiasPct', 'drawdown20dPct', 'daysFrom20dHigh', 'volume1To20Ratio',
    'volume5To20Ratio', 'nearMa7Days5',
  ].map(key => [key, finite(technical[key])]).concat([
    ['reclaimedMa13', typeof technical.reclaimedMa13 === 'boolean' ? technical.reclaimedMa13 : null],
    ['aboveMa13', typeof technical.aboveMa13 === 'boolean' ? technical.aboveMa13 : null],
    ['basis', clean(technical.basis) || 'daily'],
  ]));
}

function average(values) {
  const usable = values.filter(value => Number.isFinite(Number(value))).map(Number);
  return usable.length ? usable.reduce((sum, value) => sum + value, 0) / usable.length : null;
}

function sma(rows, index, period, field = 'close') {
  if (index < period - 1) return null;
  return average(rows.slice(index - period + 1, index + 1).map(row => row[field]));
}

function percent(value, base) {
  return Number.isFinite(value) && Number.isFinite(base) && base !== 0 ? (value / base - 1) * 100 : null;
}

export function deriveTechnicalFeatures(rows = [], target = null) {
  if (!Array.isArray(rows) || !rows.length || !target) return normalizedTechnical();
  const targetDigits = clean(target.time).replace(/\D/g, '');
  let index = rows.findIndex(row => clean(row.time).replace(/\D/g, '') === targetDigits);
  if (index < 0) index = rows.findIndex(row => clean(row.time).replace(/\D/g, '').slice(0, 8) === targetDigits.slice(0, 8));
  if (index < 0) return normalizedTechnical();
  const close = Number(rows[index].close), low = Number(rows[index].low);
  const ma7 = sma(rows, index, 7), ma13 = sma(rows, index, 13), ma40 = sma(rows, index, 40);
  const previous7 = sma(rows, index - 3, 7), previous13 = sma(rows, index - 3, 13), previous40 = sma(rows, index - 3, 40);
  const highWindowStart = Math.max(0, index - 19);
  const highWindow = rows.slice(highWindowStart, index + 1);
  const recentHigh = Math.max(...highWindow.map(row => Number(row.high)).filter(Number.isFinite));
  const localHighIndex = highWindow.findIndex(row => Number(row.high) === recentHigh);
  const previous20Volumes = rows.slice(Math.max(0, index - 20), index).map(row => row.volume);
  const previous20Average = average(previous20Volumes);
  const recent5Average = average(rows.slice(Math.max(0, index - 4), index + 1).map(row => row.volume));
  const recent5 = rows.slice(Math.max(0, index - 4), index + 1);
  const nearMa7Days5 = recent5.reduce((count, row, offset) => {
    const rowIndex = index - recent5.length + 1 + offset, rowMa7 = sma(rows, rowIndex, 7);
    return count + (rowMa7 && Math.abs(percent(Number(row.close), rowMa7)) <= 1.5 ? 1 : 0);
  }, 0);
  const gap713Pct = percent(ma7, ma13), gap1340Pct = percent(ma13, ma40);
  return normalizedTechnical({
    ma7, ma13, ma40, ma7Slope3Pct: percent(ma7, previous7), ma13Slope3Pct: percent(ma13, previous13),
    ma40Slope3Pct: percent(ma40, previous40), gap713Pct, gap1340Pct,
    gapBalanceRatio: gap713Pct != null && gap1340Pct != null && Math.abs(gap1340Pct) > 0.0001 ? Math.abs(gap713Pct / gap1340Pct) : null,
    closeMa7BiasPct: percent(close, ma7), closeMa13BiasPct: percent(close, ma13), closeMa40BiasPct: percent(close, ma40),
    drawdown20dPct: percent(close, recentHigh), daysFrom20dHigh: localHighIndex < 0 ? null : highWindow.length - 1 - localHighIndex,
    volume1To20Ratio: previous20Average ? Number(rows[index].volume) / previous20Average : null,
    volume5To20Ratio: previous20Average && recent5Average ? recent5Average / previous20Average : null,
    nearMa7Days5, reclaimedMa13: ma13 != null ? low < ma13 && close >= ma13 : null,
    aboveMa13: ma13 != null ? close >= ma13 : null, basis: 'daily',
  });
}

export function normalizeSample(input = {}, options = {}) {
  const now = options.now || new Date().toISOString();
  const context = input.context || {};
  const label = input.label || {};
  const sample = {
    id: clean(input.id) || options.id || idValue(),
    schemaVersion: SAMPLE_SCHEMA_VERSION,
    createdAt: clean(input.createdAt) || now,
    updatedAt: now,
    source: {
      webVersion: clean(input.source?.webVersion), strategy: clean(input.source?.strategy),
      backtestStart: clean(input.source?.backtestStart), backtestEnd: clean(input.source?.backtestEnd),
    },
    context: {
      decisionDate: clean(context.decisionDate).replace(/\D/g, '').slice(0, 8),
      decisionTime: clean(context.decisionTime).replace(/\D/g, '').slice(0, 6),
      timeframe: clean(context.timeframe) || '1d',
      indexCode: clean(context.indexCode), indexName: clean(context.indexName),
      indexScore: finite(context.indexScore), regime: clean(context.regime),
      exposure: finite(context.exposure), sectorCode: clean(context.sectorCode),
      sectorScore: finite(context.sectorScore), stockCode: clean(context.stockCode).toUpperCase(),
      stockName: clean(context.stockName), candidate: normalizedCandidate(context.candidate),
      bar: normalizedBar(context.bar), technical: normalizedTechnical(context.technical),
    },
    label: {
      scope: clean(label.scope), verdict: clean(label.verdict), action: clean(label.action),
      setup: clean(label.setup), confidence: clean(label.confidence) || 'medium',
      positionScale: finite(label.positionScale), reasons: uniqueList(label.reasons),
      marketState: marketStateLabels[clean(label.marketState)] ? clean(label.marketState) : 'unknown',
      sectorStage: sectorStageLabels[clean(label.sectorStage)] ? clean(label.sectorStage) : 'unknown',
      lifecycle: lifecycleLabels[clean(label.lifecycle)] ? clean(label.lifecycle) : 'unknown',
      maStructures: uniqueList(label.maStructures).filter(value => maStructureLabels[value]),
      pullbackPath: pullbackPathLabels[clean(label.pullbackPath)] ? clean(label.pullbackPath) : 'unknown',
      spaceState: spaceStateLabels[clean(label.spaceState)] ? clean(label.spaceState) : 'unknown',
      timingState: timingStateLabels[clean(label.timingState)] ? clean(label.timingState) : 'unknown',
      volumePatterns: uniqueList(label.volumePatterns).filter(value => volumePatternLabels[value]),
      overheadSupply: overheadSupplyLabels[clean(label.overheadSupply)] ? clean(label.overheadSupply) : 'unknown',
      intradayConfirm: intradayConfirmLabels[clean(label.intradayConfirm)] ? clean(label.intradayConfirm) : 'not_checked',
      invalidationRules: uniqueList(label.invalidationRules).filter(value => invalidationRuleLabels[value]),
      summary: clean(label.summary), invalidation: clean(label.invalidation), notes: clean(label.notes),
    },
  };
  if (!scopeLabels[sample.label.scope]) throw new Error('请选择判断层级');
  if (!verdictLabels[sample.label.verdict]) throw new Error('请选择样本结论');
  if (!actionLabels[sample.label.action]) throw new Error('请选择预期动作');
  if (!sample.context.decisionDate) throw new Error('缺少决策日期或K线标点');
  if (!sample.label.summary) throw new Error('请填写判断原因');
  return sample;
}

export function structuredSampleErrors(sample = {}) {
  const label = sample.label || {}, errors = [];
  const atLeastSector = ['sector', 'stock_selection', 'trade_point'].includes(label.scope);
  const atLeastStock = ['stock_selection', 'trade_point'].includes(label.scope);
  if (!label.marketState || label.marketState === 'unknown') errors.push('请选择市场环境');
  if (atLeastSector && (!label.sectorStage || label.sectorStage === 'unknown')) errors.push('请选择板块阶段');
  if (atLeastStock && (!label.lifecycle || label.lifecycle === 'unknown')) errors.push('请选择个股生命周期');
  if (atLeastStock && !label.maStructures?.length) errors.push('至少选择一个均线结构');
  if (atLeastStock && (!label.pullbackPath || label.pullbackPath === 'unknown')) errors.push('请选择回调路径');
  if (atLeastStock && (!label.spaceState || label.spaceState === 'unknown')) errors.push('请选择空间条件');
  if (atLeastStock && (!label.timingState || label.timingState === 'unknown')) errors.push('请选择时间条件');
  if (atLeastStock && !label.volumePatterns?.length) errors.push('至少选择一个量能结构');
  if (atLeastStock && (!label.overheadSupply || label.overheadSupply === 'unknown')) errors.push('请选择筹码压力');
  if (label.scope === 'trade_point' && label.intradayConfirm === 'not_checked') errors.push('请选择盘中确认状态');
  if (['open', 'add', 'addback', 'hold', 'trim', 'reduce_core', 'exit'].includes(label.action)
    && !label.invalidationRules?.length) errors.push('至少选择一个失效或退出条件');
  return errors;
}

export function sampleExport(samples, source = {}, exportedAt = new Date().toISOString()) {
  return { schemaVersion: SAMPLE_SCHEMA_VERSION, exportedAt, source, samples: samples.map(sample => {
    const missingFields = structuredSampleErrors(sample);
    return { ...sample, quality: { analysisReady: missingFields.length === 0, missingFields } };
  }) };
}

export function readSamples(storage = globalThis.localStorage) {
  try {
    const raw = storage?.getItem(SAMPLE_STORAGE_KEY)
      || PREVIOUS_STORAGE_KEYS.map(key => storage?.getItem(key)).find(Boolean) || '[]';
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const samples = parsed.flatMap(record => {
      try { return [normalizeSample(record, { now: record.updatedAt || record.createdAt || new Date().toISOString() })]; }
      catch { return []; }
    });
    if (!storage?.getItem(SAMPLE_STORAGE_KEY) && samples.length) writeSamples(samples, storage);
    return samples;
  } catch {
    return [];
  }
}

export function writeSamples(samples, storage = globalThis.localStorage) {
  storage?.setItem(SAMPLE_STORAGE_KEY, JSON.stringify(samples));
  return samples;
}

function legacyAction(label) {
  const text = clean(label).toLowerCase();
  if (text.includes('add')) return 'addback';
  if (text.includes('trim')) return 'trim';
  if (text.includes('exit')) return 'exit';
  if (text.includes('entry')) return text.startsWith('negative') ? 'no_trade' : 'open';
  return 'observe';
}

function importLegacy(record, index, now) {
  const verdict = clean(record.label).startsWith('negative') ? 'negative'
    : clean(record.label).startsWith('positive') ? 'positive' : 'uncertain';
  return normalizeSample({
    id: `legacy-${clean(record.code)}-${clean(record.date || record.range)}-${index}`,
    createdAt: now,
    context: {
      decisionDate: record.date || clean(record.range).slice(0, 10), timeframe: '1d',
      stockCode: record.code,
    },
    label: {
      scope: clean(record.label).includes('entry') ? 'stock_selection' : 'trade_point',
      verdict, action: legacyAction(record.label), setup: record.setup || 'custom',
      confidence: record.confidence || 'medium', summary: record.note || record.purpose || '历史人工标签',
    },
  }, { now });
}

export function importSamples(payload, now = new Date().toISOString()) {
  const parsed = typeof payload === 'string' ? JSON.parse(payload) : payload;
  const records = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.samples) ? parsed.samples : null;
  if (records) return records.map(record => normalizeSample(record, { now }));
  if (Array.isArray(parsed?.labels)) return parsed.labels.flatMap((record, index) => {
    const decisionDate = clean(record.date || record.range).replace(/\D/g, '').slice(0, 8);
    return decisionDate.length === 8 ? [importLegacy(record, index, now)] : [];
  });
  throw new Error('文件中没有可识别的 samples 或 labels');
}

function csvCell(value) {
  const text = String(value ?? '');
  return /[",\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

export function samplesToCsv(samples) {
  const headers = [
    'id', 'analysis_ready', 'missing_fields', 'decision_date', 'decision_time', 'timeframe', 'scope', 'verdict', 'action',
    'setup', 'confidence', 'position_scale', 'index_code', 'index_score', 'regime',
    'exposure', 'sector_code', 'sector_score', 'stock_code', 'stock_name', 'bar_time',
    'bar_open', 'bar_high', 'bar_low', 'bar_close', 'bar_volume', 'candidate_score',
    'strength_score', 'entry_score', 'candidate_status', 'market_state', 'sector_stage',
    'lifecycle', 'ma_structures', 'pullback_path', 'space_state', 'timing_state',
    'volume_patterns', 'overhead_supply', 'intraday_confirm', 'invalidation_rules',
    'ma7', 'ma13', 'ma40', 'ma7_slope_3d_pct', 'ma13_slope_3d_pct', 'ma40_slope_3d_pct',
    'gap_7_13_pct', 'gap_13_40_pct', 'gap_balance_ratio', 'close_ma7_bias_pct',
    'close_ma13_bias_pct', 'close_ma40_bias_pct', 'drawdown_20d_pct', 'days_from_20d_high',
    'volume_1_to_20_ratio', 'volume_5_to_20_ratio', 'near_ma7_days_5', 'reclaimed_ma13',
    'above_ma13', 'reason_dimensions', 'summary',
    'invalidation', 'notes', 'created_at', 'updated_at',
  ];
  const rows = samples.map(sample => {
    const context = sample.context || {}, label = sample.label || {}, bar = context.bar || {}, technical = context.technical || {};
    const missingFields = structuredSampleErrors(sample);
    return [
      sample.id, missingFields.length === 0, missingFields.join('|'), context.decisionDate, context.decisionTime, context.timeframe, label.scope,
      label.verdict, label.action, label.setup, label.confidence, label.positionScale,
      context.indexCode, context.indexScore, context.regime, context.exposure,
      context.sectorCode, context.sectorScore, context.stockCode, context.stockName,
      bar.time, bar.open, bar.high, bar.low, bar.close, bar.volume,
      context.candidate?.score, context.candidate?.strength, context.candidate?.entry,
      context.candidate?.status, label.marketState, label.sectorStage, label.lifecycle,
      (label.maStructures || []).join('|'), label.pullbackPath, label.spaceState, label.timingState,
      (label.volumePatterns || []).join('|'), label.overheadSupply, label.intradayConfirm,
      (label.invalidationRules || []).join('|'), technical.ma7, technical.ma13, technical.ma40,
      technical.ma7Slope3Pct, technical.ma13Slope3Pct, technical.ma40Slope3Pct,
      technical.gap713Pct, technical.gap1340Pct, technical.gapBalanceRatio,
      technical.closeMa7BiasPct, technical.closeMa13BiasPct, technical.closeMa40BiasPct,
      technical.drawdown20dPct, technical.daysFrom20dHigh, technical.volume1To20Ratio,
      technical.volume5To20Ratio, technical.nearMa7Days5, technical.reclaimedMa13,
      technical.aboveMa13, (label.reasons || []).join('|'), label.summary,
      label.invalidation, label.notes, sample.createdAt, sample.updatedAt,
    ].map(csvCell).join(',');
  });
  return [headers.join(','), ...rows].join('\n');
}
