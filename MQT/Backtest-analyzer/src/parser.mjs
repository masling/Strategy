function balancedObject(text, marker) {
  const markerStart = text.indexOf(marker);
  if (markerStart < 0) return null;
  const start = text.indexOf('{', markerStart);
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

function tupleAtom(raw) {
  const value = String(raw || '').trim();
  if ((value.startsWith("'") && value.endsWith("'")) || (value.startsWith('"') && value.endsWith('"'))) {
    return value.slice(1, -1).replace(/\\(['"\\])/g, '$1');
  }
  if (/^-?\d+(?:\.\d+)?$/.test(value)) return Number(value);
  if (/^(?:None|null)$/i.test(value)) return null;
  if (/^(?:True|False)$/i.test(value)) return value.toLowerCase() === 'true';
  return value;
}

function tupleRows(text) {
  const rows = [];
  let quote = '', escaped = false, depth = 0, token = '', row = null;
  for (const char of String(text || '')) {
    if (escaped) { if (depth) token += char; escaped = false; continue; }
    if (char === '\\' && quote) { if (depth) token += char; escaped = true; continue; }
    if (quote) {
      if (depth) token += char;
      if (char === quote) quote = '';
      continue;
    }
    if (char === "'" || char === '"') { quote = char; if (depth) token += char; continue; }
    if (char === '(') {
      depth += 1;
      if (depth === 1) { row = []; token = ''; }
      else token += char;
      continue;
    }
    if (char === ')' && depth) {
      depth -= 1;
      if (depth === 0) {
        row.push(tupleAtom(token));
        rows.push(row);
        row = null; token = '';
      } else token += char;
      continue;
    }
    if (char === ',' && depth === 1) { row.push(tupleAtom(token)); token = ''; continue; }
    if (depth) token += char;
  }
  return rows;
}

function sectorRows(text) {
  return tupleRows(text).map(row => ({
    style: String(row[0] || ''), code: String(row[1] || ''), name: String(row[1] || ''), score: Number(row[2]),
  })).filter(item => item.style && item.code && Number.isFinite(item.score));
}

function sectorKRows(text) {
  return tupleRows(text).map(row => ({
    time: String(row[0] || ''), open: Number(row[1]), high: Number(row[2]), low: Number(row[3]),
    close: Number(row[4]), volume: 0, amount: Number(row[5] || 0),
  })).filter(row => row.time && [row.open, row.high, row.low, row.close].every(Number.isFinite));
}

function candidateRows(text, kind = 'watchlist') {
  return tupleRows(text).map(row => {
    const style = String(row[0] || ''), code = String(row[1] || ''), name = String(row[2] || '');
    const hasSector = typeof row[3] === 'string' && !/^[-+]?\d/.test(row[3]);
    const sector = hasSector ? String(row[3]) : '';
    const values = row.slice(hasSector ? 4 : 3);
    if (kind === 'spectator') {
      return {
        style, code, name, sector, score: null, strength: Number(values[0]), strengthFit: Number(values[1]),
        entry: Number(values[2]), status: String(values[3] || 'WAIT'), setup: '', source: kind,
      };
    }
    const modern = values.length >= 5;
    return {
      style, code, name, sector, score: Number(values[0]), strength: values.length >= 3 ? Number(values[1]) : null,
      strengthFit: modern ? Number(values[2]) : null, entry: modern ? Number(values[3]) : values.length >= 3 ? Number(values[2]) : null,
      status: String(values[modern ? 4 : 3] || (kind === 'targets' ? 'READY' : 'WAIT')),
      setup: kind === 'targets' ? String(values[modern ? 4 : 3] || '') : '', source: kind,
    };
  }).filter(item => item.style && item.code);
}

function entryReadyChange(text) {
  const addedText = text.match(/\badded\s+(\[.*?\])\s+removed\s+/)?.[1] || '';
  const removedText = text.match(/\bremoved\s+(\[.*\])\s*$/)?.[1] || '';
  const added = tupleRows(addedText).map(row => ({
    code: String(row[0] || ''), setup: String(row[1] || ''), score: Number(row[2]), strength: Number(row[3]),
    strengthFit: row.length >= 6 ? Number(row[4]) : null, entry: Number(row.length >= 6 ? row[5] : row[4]), status: 'READY',
  })).filter(item => item.code);
  const removed = [...removedText.matchAll(/['"]([^'"]+)['"]/g)].map(match => match[1]);
  return { added, removed };
}

function numberAfter(line, label) {
  const match = line.match(new RegExp(`${label}\\s+(-?\\d+(?:\\.\\d+)?)`));
  return match ? Number(match[1]) : null;
}

function emptyDay(date) {
  return {
    date, state: null, sectors: [], sectorsLogged: false, sectorK: [], sectorKLogged: false,
    watchlist: [], watchlistLogged: false,
    spectators: [], spectatorsLogged: false, targets: [], targetsLogged: false, entryReady: { added: [], removed: [] },
    sectorFocus: null, transitions: [], portfolio: null, desired: {}, desiredLogged: false,
    allocation: null, orders: [], deals: [], intraday: [],
  };
}

function logMessage(rawLine) {
  return String(rawLine || '').trim().replace(/^【[^】]+】\s*/, '');
}

function orderKey(date, time, code, side) {
  return `${date}|${time}|${code}|${side}`;
}

function rejectedOrder(line) {
  let match = line.match(/当前股票(\S+)没有持仓,不能卖出,跳过,日期时间:(\d{8})\s+(\d{2}):(\d{2}):(\d{2})/);
  if (match) return { code: match[1], date: match[2], time: `${match[3]}${match[4]}${match[5]}`, side: 'sell', reason: '无持仓，卖出被QMT跳过' };
  match = line.match(/获取不到行情默认停牌,跳过,代码:(\S+),日期时间:(\d{8})\s+(\d{2}):(\d{2}):(\d{2})/);
  if (match) return { code: match[1], date: match[2], time: `${match[3]}${match[4]}${match[5]}`, side: '*', reason: '行情不可用，委托被QMT跳过' };
  return null;
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

function calendarDay(value) {
  const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!match) return null;
  return Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

function annualizationExponent(meta, tradingDays) {
  const start = calendarDay(meta?.startTime);
  const end = calendarDay(meta?.endTime);
  const elapsedDays = start != null && end != null ? (end - start) / 86400000 : 0;
  if (elapsedDays > 0) return 365 / elapsedDays;
  return tradingDays > 0 ? 252 / tradingDays : null;
}

function performance(days, meta) {
  const assets = days.map(day => day.portfolio?.balance).filter(value => Number.isFinite(value) && value > 0);
  if (!assets.length) return { tradingDays: days.length, initialAsset: null, finalAsset: null, totalReturn: null, annualizedReturn: null, maxDrawdown: null, sharpe: null };
  const loggedCapital = days.map(day => day.portfolio?.capital).find(value => Number.isFinite(value) && value > 0);
  const initialAsset = loggedCapital || assets[0], finalAsset = assets.at(-1);
  const curve = loggedCapital ? [loggedCapital, ...assets] : assets;
  const returns = curve.slice(1).map((value, index) => value / curve[index] - 1);
  let peak = curve[0], maxDrawdown = 0;
  curve.forEach(value => { peak = Math.max(peak, value); maxDrawdown = Math.min(maxDrawdown, value / peak - 1); });
  const totalReturn = finalAsset / initialAsset - 1;
  const exponent = annualizationExponent(meta, days.length);
  const annualizedReturn = exponent == null ? null : Math.pow(finalAsset / initialAsset, exponent) - 1;
  const average = returns.length ? returns.reduce((sum, value) => sum + value, 0) / returns.length : null;
  const variance = returns.length > 1 ? returns.reduce((sum, value) => sum + Math.pow(value - average, 2), 0) / (returns.length - 1) : null;
  const sharpe = variance > 0 ? average / Math.sqrt(variance) * Math.sqrt(252) : null;
  return { tradingDays: days.length, initialAsset, finalAsset, totalReturn, annualizedReturn, maxDrawdown, sharpe };
}

function stockTrading(days) {
  const stocks = new Map();
  const stockFor = code => {
    if (!stocks.has(code)) stocks.set(code, { code, name: '', styles: [], orders: [], deals: [] });
    return stocks.get(code);
  };
  days.forEach(day => {
    [...day.watchlist, ...day.spectators, ...day.targets].forEach(target => {
      const stock = stockFor(target.code);
      if (target.name) stock.name = target.name;
      if (target.style && !stock.styles.includes(target.style)) stock.styles.push(target.style);
      if (target.sector) stock.sector = target.sector;
    });
    day.orders.forEach(order => {
      stockFor(order.code).orders.push({ ...order, date: day.date });
    });
    day.deals.forEach(deal => {
      stockFor(deal.code).deals.push({ ...deal, date: day.date });
    });
  });
  return [...stocks.values()]
    .filter(stock => stock.orders.length || stock.deals.length)
    .map(stock => {
      const submitted = stock.orders.filter(order => order.status === 'submitted');
      const trades = stock.deals.length ? stock.deals : submitted;
      const failedOrders = stock.orders.filter(order => order.status === 'failed' || order.status === 'cancelled');
      return {
        ...stock, trades, activity: stock.deals.length ? [...stock.deals, ...failedOrders] : stock.orders,
        tradeSource: stock.deals.length ? 'deal' : 'order',
        failedCount: stock.orders.filter(order => order.status === 'failed' || order.status === 'cancelled').length,
        buyCount: trades.filter(order => order.side === 'buy').length,
        sellCount: trades.filter(order => order.side === 'sell').length,
        buyVolume: trades.filter(order => order.side === 'buy').reduce((sum, order) => sum + order.volume, 0),
        sellVolume: trades.filter(order => order.side === 'sell').reduce((sum, order) => sum + order.volume, 0),
      };
    })
    .sort((a, b) => b.trades.length - a.trades.length || a.code.localeCompare(b.code));
}

export function parseQmtLog(raw) {
  const days = new Map();
  const meta = { engine: null, period: null, startTime: null, endTime: null, firstBar: null, warnings: [] };
  let currentDate = '';
  let pendingPortfolio = null;
  const rejected = new Map();
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
    const line = logMessage(rawLine);
    if (!line) continue;
    const rejection = rejectedOrder(line);
    if (rejection) {
      rejected.set(orderKey(rejection.date, rejection.time, rejection.code, rejection.side), rejection.reason);
      meta.warnings.push(line);
      continue;
    }
    if (line.startsWith('ENGINE ')) Object.assign(meta, { engine: line.slice(7), ...engineMeta(line) });
    else if (line.startsWith('FIRST_BAR ')) meta.firstBar = line.slice(10);
    else if (line.startsWith('BACKTEST_RANGE ')) {
      const range = line.match(/^BACKTEST_RANGE\s+start\s+(.+?)\s+end\s+(.+)$/);
      if (range) { meta.startTime = dateTime(range[1]); meta.endTime = dateTime(range[2]); }
    }
    else if (/^(WARN|WARNING|ERROR)\b/.test(line)) meta.warnings.push(line);
    else if (line.startsWith('REGIME ')) {
      const match = line.match(/^REGIME\s+(\d{8})\s+(\S+)\s+(\S+)\s+to\s+(\S+)\s+score\s+(-?\d+(?:\.\d+)?)/);
      if (match) dayFor(match[1]).transitions.push({ code: match[2], from: match[3], to: match[4], score: Number(match[5]) });
    } else if (line.startsWith('STATE ')) {
      const match = line.match(/^STATE\s+(\d{8})\s+exposure\s+(-?\d+(?:\.\d+)?)/);
      if (!match) continue;
      const day = dayFor(match[1]);
      day.state = {
        exposure: Number(match[2]),
        styleExposures: pythonValue(balancedObject(line, 'style_exposures')),
        scores: pythonValue(balancedObject(line, 'scores')),
        regimes: pythonValue(balancedObject(line, 'regimes')),
        riskCaps: pythonValue(balancedObject(line, 'risk_caps')),
        reserve: numberAfter(line, 'reserve'), watchlist: numberAfter(line, 'watchlist'),
        spectators: numberAfter(line, 'spectators'), entryReady: numberAfter(line, 'entry_ready'),
      };
    } else if (line.startsWith('SECTORS ')) {
      const day = dayFor(); if (day) { day.sectors = sectorRows(line); day.sectorsLogged = true; }
    } else if (line.startsWith('SECTOR_K ')) {
      const match = line.match(/^SECTOR_K\s+(\d{8})\s+(\S+)\s+(\S+)\s+/); const day = match && dayFor(match[1]);
      if (day) {
        day.sectorK.push({ style: match[2], code: match[3], rows: sectorKRows(line.slice(match[0].length)) });
        day.sectorKLogged = true;
      }
    } else if (line.startsWith('WATCHLIST ')) {
      const day = dayFor(); if (day) { day.watchlist = candidateRows(line, 'watchlist'); day.watchlistLogged = true; }
    } else if (line.startsWith('SPECTATORS ')) {
      const day = dayFor(); if (day) { day.spectators = candidateRows(line, 'spectator'); day.spectatorsLogged = true; }
    } else if (line.startsWith('TARGETS ')) {
      const day = dayFor(); if (day) { day.targets = candidateRows(line, 'targets'); day.targetsLogged = true; }
    } else if (line.startsWith('ENTRY_READY ')) {
      const match = line.match(/^ENTRY_READY\s+(\d{8})/); const day = match && dayFor(match[1]);
      if (day) day.entryReady = entryReadyChange(line);
    } else if (line.startsWith('SECTOR_FOCUS ')) {
      const match = line.match(/^SECTOR_FOCUS\s+(\d{8})\s+(\S+)\s+style\s+(\S+)\s+leader\s+(-?\d+(?:\.\d+)?)\s+runner\s+(-?\d+(?:\.\d+)?)\s+base_exposure\s+(-?\d+(?:\.\d+)?)/);
      if (match) dayFor(match[1]).sectorFocus = {
        sector: match[2], style: match[3], leaderScore: Number(match[4]), runnerScore: Number(match[5]), exposure: Number(match[6]),
      };
    } else if (line.startsWith('PORTFOLIO ')) {
      pendingPortfolio = {
        source: line.match(/source\s+(\S+)/)?.[1] || '',
        capital: numberAfter(line, 'capital'),
        balance: numberAfter(line, 'balance'), cash: numberAfter(line, 'cash'),
        marketValue: numberAfter(line, 'market_value'), positions: numberAfter(line, 'positions'),
      };
    } else if (line.startsWith('DESIRED ')) {
      const match = line.match(/^DESIRED\s+(\d{8})/); const day = match && dayFor(match[1]);
      if (day) { day.desired = pythonValue(balancedObject(line, 'DESIRED')); day.desiredLogged = true; }
    } else if (line.startsWith('ALLOCATION ')) {
      const match = line.match(/^ALLOCATION\s+(\d{8})/); const day = match && dayFor(match[1]);
      if (day) day.allocation = {
        plannedExposure: numberAfter(line, 'planned_exposure'), targetExposure: numberAfter(line, 'target_exposure'),
        fillRate: numberAfter(line, 'fill_rate'), unallocatedCash: numberAfter(line, 'unallocated_cash'),
      };
    } else if (line.startsWith('ORDER_QUEUED ')) {
      const match = line.match(/^ORDER_QUEUED\s+(\d{8})\s+(\d{6})\s+(buy|sell)\s+(\S+)\s+(\d+)\s+reference_price\s+(-?\d+(?:\.\d+)?)\s*(.*)$/i);
      if (match) dayFor(match[1]).orders.push({
        time: match[2], signalTime: match[2], side: match[3].toLowerCase(), code: match[4], volume: Number(match[5]),
        price: Number(match[6]), reason: match[7], status: 'queued', failureReason: '',
      });
    } else if (/^ORDER(?:_SUBMITTED)?\s/.test(line)) {
      const match = line.match(/^ORDER(?:_SUBMITTED)?\s+(\d{8})(?:\s+(\d{6}))?\s+(buy|sell)\s+(\S+)\s+(\d+)(?:\s+price\s+(-?\d+(?:\.\d+)?))?\s*(.*)$/i);
      if (match) {
        const time = match[2] || '', side = match[3].toLowerCase(), code = match[4];
        const failureReason = rejected.get(orderKey(match[1], time, code, side)) || rejected.get(orderKey(match[1], time, code, '*')) || '';
        const signalTime = match[7].match(/\bsignal_time\s+(\d{6})/)?.[1] || '';
        const submitted = {
          time, side, code, volume: Number(match[5]),
          price: match[6] == null ? null : Number(match[6]), reason: match[7].replace(/\s+signal_time\s+\d{6}.*$/, '').trim(),
          status: failureReason ? 'failed' : 'submitted', failureReason,
        };
        if (signalTime) submitted.signalTime = signalTime;
        const day = dayFor(match[1]);
        const queued = day.orders.find(order => order.status === 'queued' && order.signalTime === (signalTime || time) && order.code === code && order.side === side && order.volume === submitted.volume);
        if (queued) Object.assign(queued, submitted);
        else day.orders.push(submitted);
      }
    } else if (line.startsWith('ORDER_CANCELLED ')) {
      const match = line.match(/^ORDER_CANCELLED\s+(\d{8})\s+(\d{6})\s+(buy|sell)\s+(\S+)\s+(\d+)\s+(.+)$/i);
      if (match) {
        const side = match[3].toLowerCase(), signalTime = match[6].match(/\bsignal_time\s+(\d{6})/)?.[1] || match[2], day = dayFor(match[1]);
        const reason = match[6].replace(/\s+signal_time\s+\d{6}\s*$/, '');
        const queued = day.orders.find(order => order.status === 'queued' && order.signalTime === signalTime && order.code === match[4] && order.side === side && order.volume === Number(match[5]));
        const cancelled = {
          time: match[2], signalTime, side, code: match[4], volume: Number(match[5]), price: queued?.price ?? null,
          reason, status: 'cancelled', failureReason: reason,
        };
        if (queued) Object.assign(queued, cancelled);
        else day.orders.push(cancelled);
      }
    } else if (line.startsWith('DEAL ')) {
      const match = line.match(/^DEAL\s+(\d{8})(?:\s+(\d{6}))?\s+(buy|sell)\s+(\S+)\s+(\d+)(?:\s+price\s+(-?\d+(?:\.\d+)?))?/i);
      if (match) dayFor(match[1]).deals.push({
        time: match[2] || '', side: match[3].toLowerCase(), code: match[4],
        volume: Number(match[5]), price: match[6] == null ? null : Number(match[6]),
        reason: '成交', status: 'filled',
      });
    } else if (line.startsWith('INTRADAY ')) {
      const match = line.match(/^INTRADAY\s+(\d{8})\s+(\S+)\s+(reduce|add)\s+(\d+)/);
      if (match) dayFor(match[1]).intraday.push({ code: match[2], action: match[3], volume: Number(match[4]) });
    }
  }
  if (pendingPortfolio && currentDate) days.get(currentDate).portfolio = pendingPortfolio;
  const sortedDays = [...days.values()].sort((a, b) => a.date.localeCompare(b.date));
  let carriedDesired = {}, carriedSectors = [], carriedSectorK = [], carriedWatchlist = [], carriedSpectators = [];
  sortedDays.forEach(day => {
    if (day.desiredLogged) carriedDesired = { ...day.desired };
    else day.desired = { ...carriedDesired };
    const active = (day.state?.exposure || 0) > 0;
    if (day.sectorsLogged) carriedSectors = day.sectors.map(item => ({ ...item }));
    else day.sectors = active ? carriedSectors.map(item => ({ ...item, carried: true })) : [];
    if (day.sectorKLogged) carriedSectorK = day.sectorK.map(item => ({ ...item, rows: item.rows.map(row => ({ ...row })) }));
    else day.sectorK = active ? carriedSectorK.map(item => ({ ...item, carried: true, rows: item.rows.map(row => ({ ...row })) })) : [];
    if (day.watchlistLogged) carriedWatchlist = day.watchlist.map(item => ({ ...item }));
    else if ((day.state?.watchlist || 0) > 0) day.watchlist = carriedWatchlist.map(item => ({ ...item, carried: true }));
    else day.watchlist = [];
    const removed = new Set(day.entryReady.removed);
    day.watchlist = day.watchlist.map(item => removed.has(item.code) ? { ...item, status: 'WAIT' } : item);
    day.entryReady.added.forEach(added => {
      const index = day.watchlist.findIndex(item => item.code === added.code);
      if (index >= 0) day.watchlist[index] = { ...day.watchlist[index], ...added };
      else day.watchlist.push({ style: '', name: '', sector: '', source: 'entry_ready', ...added });
    });
    carriedWatchlist = day.watchlist.map(item => ({ ...item }));
    if (day.spectatorsLogged) carriedSpectators = day.spectators.map(item => ({ ...item }));
    else if ((day.state?.spectators || 0) > 0) day.spectators = carriedSpectators.map(item => ({ ...item, carried: true }));
    else day.spectators = [];
    carriedSpectators = day.spectators.map(item => ({ ...item }));
    if (!day.targetsLogged) day.targets = day.watchlist.filter(item => item.status === 'READY').map(item => ({ ...item, setup: item.setup || '', source: 'derived' }));
  });
  sortedDays.forEach(day => {
    day.orders.forEach(order => {
      const failureReason = rejected.get(orderKey(day.date, order.time, order.code, order.side)) || rejected.get(orderKey(day.date, order.time, order.code, '*')) || '';
      if (failureReason) Object.assign(order, { status: 'failed', failureReason });
    });
  });
  if (!meta.startTime) meta.startTime = dateTime(meta.firstBar) || dateTime(sortedDays[0]?.date);
  if (!meta.endTime) meta.endTime = dateTime(sortedDays.at(-1)?.date);
  return { meta, statistics: performance(sortedDays, meta), days: sortedDays, stocks: stockTrading(sortedDays) };
}
