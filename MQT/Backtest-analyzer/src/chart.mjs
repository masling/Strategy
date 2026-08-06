const COLORS = { up: '#ef5350', down: '#19a974', grid: '#263248', text: '#8d9bb3', average: '#f6c85f', ma7: '#f6c85f', ma13: '#6fb7ff', ma40: '#cf8cff' };

function setup(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 700, height = canvas.clientHeight || 360;
  canvas.width = width * ratio; canvas.height = height * ratio;
  const ctx = canvas.getContext('2d'); ctx.scale(ratio, ratio);
  return { ctx, width, height };
}

function empty(ctx, width, height, text) {
  ctx.fillStyle = COLORS.text; ctx.font = '14px system-ui'; ctx.textAlign = 'center';
  ctx.fillText(text, width / 2, height / 2);
}

function movingAverages(rows, periods) {
  const sums = Object.fromEntries(periods.map(period => [period, 0]));
  return rows.map((row, index) => {
    const values = {};
    periods.forEach(period => {
      sums[period] += row.close;
      if (index >= period) sums[period] -= rows[index - period].close;
      values[period] = index >= period - 1 ? sums[period] / period : null;
    });
    return values;
  });
}

function tradeDate(value) {
  return String(value || '').replace(/\D/g, '').slice(0, 8);
}

function rowForTrade(rows, order) {
  const date = tradeDate(order.date);
  const sameDay = rows.map((row, index) => ({ row, index, digits: String(row.time || '').replace(/\D/g, '') }))
    .filter(item => item.digits.slice(0, 8) === date);
  if (!sameDay.length) return null;
  if (!order.time || sameDay[0].digits.length < 12) return sameDay[0].index;
  const orderClock = String(order.time).padStart(6, '0').slice(0, 4);
  return (sameDay.find(item => item.digits.slice(8, 12) >= orderClock) || sameDay.at(-1)).index;
}

function clockLabel(order) {
  const clock = String(order.time || '');
  return clock.length === 6 ? `${clock.slice(0, 2)}:${clock.slice(2, 4)}` : '';
}

export function drawCandles(canvas, rows, orders = [], sourceRows = rows) {
  const { ctx, width, height } = setup(canvas); ctx.clearRect(0, 0, width, height);
  if (!rows.length) return empty(ctx, width, height, '暂无K线数据');
  const pad = { l: 46, r: 16, t: 20, b: 34 }, chartH = height - pad.t - pad.b;
  const periods = [7, 13, 40];
  const sourceAverages = movingAverages(sourceRows, periods);
  const averageByTime = new Map(sourceRows.map((row, index) => [row.time, sourceAverages[index]]));
  const visibleAverages = rows.map(row => averageByTime.get(row.time));
  const averageValues = visibleAverages.flatMap(values => periods.map(period => values?.[period]).filter(Number.isFinite));
  const min = Math.min(...rows.map(r => r.low), ...averageValues), max = Math.max(...rows.map(r => r.high), ...averageValues);
  const y = value => pad.t + (max - value) / Math.max(max - min, 0.01) * chartH;
  const step = (width - pad.l - pad.r) / rows.length;
  ctx.strokeStyle = COLORS.grid; ctx.fillStyle = COLORS.text; ctx.font = '11px system-ui';
  for (let i = 0; i <= 4; i += 1) {
    const py = pad.t + chartH * i / 4; ctx.beginPath(); ctx.moveTo(pad.l, py); ctx.lineTo(width - pad.r, py); ctx.stroke();
    ctx.fillText((max - (max - min) * i / 4).toFixed(2), 3, py + 4);
  }
  const tradesByIndex = new Map();
  orders.forEach(order => {
    const index = rowForTrade(rows, order);
    if (index == null) return;
    const trades = tradesByIndex.get(index) || [];
    trades.push(order);
    tradesByIndex.set(index, trades);
  });
  rows.forEach((r, i) => {
    const x = pad.l + step * (i + .5), color = r.close >= r.open ? COLORS.up : COLORS.down;
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(x, y(r.high)); ctx.lineTo(x, y(r.low)); ctx.stroke();
    const top = y(Math.max(r.open, r.close)), bottom = y(Math.min(r.open, r.close));
    ctx.fillRect(x - Math.max(1, step * .28), top, Math.max(2, step * .56), Math.max(1, bottom - top));
    const trades = tradesByIndex.get(i) || [];
    const buy = trades.find(order => order.side === 'buy');
    const sell = trades.find(order => order.side === 'sell');
    ctx.font = 'bold 10px system-ui'; ctx.textAlign = 'center';
    if (buy) {
      const markerY = Math.min(height - pad.b - 4, y(r.low) + 13);
      ctx.fillStyle = '#ffcf5c'; ctx.beginPath();
      ctx.moveTo(x, markerY); ctx.lineTo(x - 5, markerY + 8); ctx.lineTo(x + 5, markerY + 8); ctx.fill();
      ctx.fillText(`B${clockLabel(buy) ? ` ${clockLabel(buy)}` : ''}`, x, markerY + 19);
    }
    if (sell) {
      const markerY = Math.max(pad.t + 4, y(r.high) - 13);
      ctx.fillStyle = '#65d6bc'; ctx.beginPath();
      ctx.moveTo(x, markerY); ctx.lineTo(x - 5, markerY - 8); ctx.lineTo(x + 5, markerY - 8); ctx.fill();
      ctx.fillText(`S${clockLabel(sell) ? ` ${clockLabel(sell)}` : ''}`, x, markerY - 11);
    }
  });
  const drawAverage = (period, color) => {
    ctx.strokeStyle = color; ctx.lineWidth = 1.4; ctx.beginPath();
    let started = false;
    visibleAverages.forEach((values, index) => {
      const value = values?.[period];
      if (!Number.isFinite(value)) return;
      const x = pad.l + step * (index + .5);
      if (started) ctx.lineTo(x, y(value)); else { ctx.moveTo(x, y(value)); started = true; }
    });
    if (started) ctx.stroke();
  };
  drawAverage(7, COLORS.ma7); drawAverage(13, COLORS.ma13); drawAverage(40, COLORS.ma40);
  ctx.font = '11px system-ui'; ctx.textAlign = 'left';
  [[7, COLORS.ma7], [13, COLORS.ma13], [40, COLORS.ma40]].forEach(([period, color], index) => {
    ctx.fillStyle = color; ctx.fillText(`MA${period}`, pad.l + index * 46, 13);
  });
  ctx.fillStyle = COLORS.text; ctx.fillText(rows[0].time, pad.l, height - 8); ctx.textAlign = 'right'; ctx.fillText(rows.at(-1).time, width - pad.r, height - 8);
}

export function drawLine(canvas, rows) {
  const { ctx, width, height } = setup(canvas); ctx.clearRect(0, 0, width, height);
  if (!rows.length) return empty(ctx, width, height, '暂无分时数据（仅提供最近交易日）');
  const values = rows.flatMap(r => [r.close, r.average]).filter(Boolean), min = Math.min(...values), max = Math.max(...values);
  const point = (r, i, key) => [42 + i / Math.max(rows.length - 1, 1) * (width - 58), 18 + (max - r[key]) / Math.max(max - min, .01) * (height - 52)];
  const line = (key, color) => { ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath(); rows.forEach((r, i) => { const [x, y] = point(r, i, key); i ? ctx.lineTo(x, y) : ctx.moveTo(x, y); }); ctx.stroke(); };
  line('close', '#6fb7ff'); line('average', COLORS.average);
  ctx.fillStyle = COLORS.text; ctx.font = '11px system-ui'; ctx.fillText(rows[0].time.slice(-5), 42, height - 8); ctx.textAlign = 'right'; ctx.fillText(rows.at(-1).time.slice(-5), width - 16, height - 8);
}
