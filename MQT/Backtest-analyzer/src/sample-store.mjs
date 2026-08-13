export const SAMPLE_SCHEMA_VERSION = 2;
export const SAMPLE_STORAGE_KEY = 'qmt-standard-samples-v2';

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
      bar: normalizedBar(context.bar),
    },
    label: {
      scope: clean(label.scope), verdict: clean(label.verdict), action: clean(label.action),
      setup: clean(label.setup), confidence: clean(label.confidence) || 'medium',
      positionScale: finite(label.positionScale), reasons: [...new Set(
        (Array.isArray(label.reasons) ? label.reasons : []).map(clean).filter(Boolean)
      )],
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

export function sampleExport(samples, source = {}, exportedAt = new Date().toISOString()) {
  return { schemaVersion: SAMPLE_SCHEMA_VERSION, exportedAt, source, samples };
}

export function readSamples(storage = globalThis.localStorage) {
  try {
    const parsed = JSON.parse(storage?.getItem(SAMPLE_STORAGE_KEY) || '[]');
    return Array.isArray(parsed) ? parsed : [];
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
    'id', 'decision_date', 'decision_time', 'timeframe', 'scope', 'verdict', 'action',
    'setup', 'confidence', 'position_scale', 'index_code', 'index_score', 'regime',
    'exposure', 'sector_code', 'sector_score', 'stock_code', 'stock_name', 'bar_time',
    'bar_open', 'bar_high', 'bar_low', 'bar_close', 'bar_volume', 'candidate_score',
    'strength_score', 'entry_score', 'candidate_status', 'reason_dimensions', 'summary',
    'invalidation', 'notes', 'created_at', 'updated_at',
  ];
  const rows = samples.map(sample => {
    const context = sample.context || {}, label = sample.label || {}, bar = context.bar || {};
    return [
      sample.id, context.decisionDate, context.decisionTime, context.timeframe, label.scope,
      label.verdict, label.action, label.setup, label.confidence, label.positionScale,
      context.indexCode, context.indexScore, context.regime, context.exposure,
      context.sectorCode, context.sectorScore, context.stockCode, context.stockName,
      bar.time, bar.open, bar.high, bar.low, bar.close, bar.volume,
      context.candidate?.score, context.candidate?.strength, context.candidate?.entry,
      context.candidate?.status, (label.reasons || []).join('|'), label.summary,
      label.invalidation, label.notes, sample.createdAt, sample.updatedAt,
    ].map(csvCell).join(',');
  });
  return [headers.join(','), ...rows].join('\n');
}
