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

export function parseQmtLog(raw) {
  const days = new Map();
  const meta = { engine: null, firstBar: null, warnings: [] };
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
    if (line.startsWith('ENGINE ')) meta.engine = line.slice(7);
    else if (line.startsWith('FIRST_BAR ')) meta.firstBar = line.slice(10);
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
  return { meta, days: [...days.values()].sort((a, b) => a.date.localeCompare(b.date)) };
}
