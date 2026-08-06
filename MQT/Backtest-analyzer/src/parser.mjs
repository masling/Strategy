function balancedObject(text, marker) {
  const start = text.indexOf('{', text.indexOf(marker));
  if (start < 0) return null;
  let depth = 0;
  for (let i = start; i < text.length; i += 1) {
    if (text[i] === '{') depth += 1;
    if (text[i] === '}') depth -= 1;
    if (depth === 0) return text.slice(start, i + 1);
  }
  return null;
}

function pythonValue(text, fallback = {}) {
  if (!text) return fallback;
  try {
    return JSON.parse(text
      .replace(/'/g, '"')
      .replace(/\bNone\b/g, 'null')
      .replace(/\bTrue\b/g, 'true')
      .replace(/\bFalse\b/g, 'false'));
  } catch {
    return fallback;
  }
}

function tuples(text) {
  const results = [];
  const tuplePattern = /\(\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*(?:'([^']*)'\s*,\s*)?(-?\d+(?:\.\d+)?)\s*\)/g;
  let match;
  while ((match = tuplePattern.exec(text))) {
    results.push({ style: match[1], code: match[2], name: match[3] || '', score: Number(match[4]) });
  }
  return results;
}

function numberAfter(line, label) {
  const match = line.match(new RegExp(`${label}\\s+(-?\\d+(?:\\.\\d+)?)`));
  return match ? Number(match[1]) : null;
}

function emptyDay(date) {
  return { date, state: null, sectors: [], targets: [], portfolio: null, desired: {}, allocation: null, orders: [], intraday: [] };
}

function dateTime(value) {
  const text = String(value || '').trim();
  const digits = text.replace(/\D/g, '');
  if (digits.length < 8 || /^-?1$/.test(text)) return null;
  const date = `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6, 8)}`;
  return digits.length >= 14 ? `${date} ${digits.slice(8, 10)}:${digits.slice(10, 12)}:${digits.slice(12, 14)}` : date;
}

function engineMeta(line) {
  const body = line.slice(7);
  const start = body.match(/\bstart\s+(.+?)\s+end\s+/i);
  const end = body.match(/\bend\s+(.+)$/i);
  return {
    raw: body,
    period: body.match(/\bperiod\s+(\S+)/i)?.[1] || null,
    startTime: dateTime(start?.[1]),
    endTime: dateTime(end?.[1]),
  };
}

function performance(days) {
  const assets = days.map(day => day.portfolio?.balance).filter(value => Number.isFinite(value) && value > 0);
  if (!assets.length) return { tradingDays: days.length, initialAsset: null, finalAsset: null, totalReturn: null, annualizedReturn: null, maxDrawdown: null, sharpe: null };
  const loggedCapital = days.map(day => day.portfolio?.capital).find(value => Number.isFinite(value) && value > 0);
  const initialAsset = loggedCapital || assets[0], finalAsset = assets.at(-1);
  const curve = loggedCapital ? [loggedCapital, ...assets] : assets;
  const returns = curve.slice(1).map((value, index) => value / curve[index] - 1);
  let peak = curve[0], maxDrawdown = 0;
  curve.forEach(value => { peak = Math.max(peak, value); maxDrawdown = Math.min(maxDrawdown, value / peak - 1); });
  const totalReturn = finalAsset / initialAsset - 1;
  const annualizedReturn = returns.length ? Math.pow(finalAsset / initialAsset, 252 / returns.length) - 1 : null;
  const average = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : null;
  const variance = returns.length > 1 ? returns.reduce((sum, value) => sum + Math.pow(value - average, 2), 0) / (returns.length - 1) : null;
  const sharpe = variance > 0 ? average / Math.sqrt(variance) * Math.sqrt(252) : null;
  return { tradingDays: days.length, initialAsset, finalAsset, totalReturn, annualizedReturn, maxDrawdown, sharpe };
}

export function parseQmtLog(raw) {
  const days = new Map();
  const meta = { engine: null, period: null, startTime: null, endTime: null, firstBar: null, warnings: [] };
  let currentDate = '';
  let pendingPortfolio = null;
  const dayFor = (date = currentDate) => {
    if (!date) return null;
    currentDate = date;
    if (!days.has(date)) days.set(date, emptyDay(date));
    const day = days.get(date);
    if (pendingPortfolio && !day.portfolio) {
      day.portfolio = pendingPortfolio;
      pendingPortfolio = null;
    }
    return day;
  };

  for (const rawLine of String(raw || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    if (line.startsWith('ENGINE ')) Object.assign(meta, { engine: line.slice(7), ...engineMeta(line) });
    else if (line.startsWith('FIRST_BAR ')) meta.firstBar = line.slice(10);
    else if (line.startsWith('BACKTEST_RANGE ')) {
      const range = line.match(/^BACKTEST_RANGE\s+start\s+(.+?)\s+end\s+(.+)$/);
      if (range) { meta.startTime = dateTime(range[1]); meta.endTime = dateTime(range[2]); }
    }
    else if (/^(WARN|WARNING|ERROR)\b/.test(line)) meta.warnings.push(line);
    else if (line.startsWith('STATE ')) {
      const match = line.match(/^STATE\s+(\d{8})\s+exposure\s+(-?\d+(?:\.\d+)?)/);
      if (!match) continue;
      const day = dayFor(match[1]);
      day.state = {
        exposure: Number(match[2]),
        styleExposures: pythonValue(balancedObject(line, 'style_exposures')),
        scores: pythonValue(balancedObject(line, 'scores')),
      };
    } else if (line.startsWith('SECTORS ')) {
      const day = dayFor(); if (day) day.sectors = tuples(line);
    } else if (line.startsWith('TARGETS ')) {
      const day = dayFor(); if (day) day.targets = tuples(line);
    } else if (line.startsWith('PORTFOLIO ')) {
      pendingPortfolio = {
        source: line.match(/source\s+(\S+)/)?.[1] || '',
        capital: numberAfter(line, 'capital'),
        balance: numberAfter(line, 'balance'), cash: numberAfter(line, 'cash'),
        marketValue: numberAfter(line, 'market_value'), positions: numberAfter(line, 'positions'),
      };
    } else if (line.startsWith('DESIRED ')) {
      const match = line.match(/^DESIRED\s+(\d{8})/); const day = match && dayFor(match[1]);
      if (day) day.desired = pythonValue(balancedObject(line, 'DESIRED'));
    } else if (line.startsWith('ALLOCATION ')) {
      const match = line.match(/^ALLOCATION\s+(\d{8})/); const day = match && dayFor(match[1]);
      if (day) day.allocation = {
        plannedExposure: numberAfter(line, 'planned_exposure'), targetExposure: numberAfter(line, 'target_exposure'),
        fillRate: numberAfter(line, 'fill_rate'), unallocatedCash: numberAfter(line, 'unallocated_cash'),
      };
    } else if (line.startsWith('ORDER ')) {
      const match = line.match(/^ORDER\s+(\d{8})\s+(buy|sell)\s+(\S+)\s+(\d+)\s*(.*)$/i);
      if (match) dayFor(match[1]).orders.push({ side: match[2], code: match[3], volume: Number(match[4]), reason: match[5] });
    } else if (line.startsWith('INTRADAY ')) {
      const match = line.match(/^INTRADAY\s+(\d{8})\s+(\S+)\s+(reduce|add)\s+(\d+)/);
      if (match) dayFor(match[1]).intraday.push({ code: match[2], action: match[3], volume: Number(match[4]) });
    }
  }
  if (pendingPortfolio && currentDate) days.get(currentDate).portfolio = pendingPortfolio;
  const sortedDays = [...days.values()].sort((a, b) => a.date.localeCompare(b.date));
  if (!meta.startTime) meta.startTime = dateTime(meta.firstBar) || dateTime(sortedDays[0]?.date);
  if (!meta.endTime) meta.endTime = dateTime(sortedDays.at(-1)?.date);
  return { meta, statistics: performance(sortedDays), days: sortedDays };
}
