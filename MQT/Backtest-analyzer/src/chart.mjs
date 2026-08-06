const COLORS = { up: '#ef5350', down: '#19a974', grid: '#263248', text: '#8d9bb3', average: '#f6c85f' };

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

export function drawCandles(canvas, rows, selectedDate, orders = []) {
  const { ctx, width, height } = setup(canvas); ctx.clearRect(0, 0, width, height);
  if (!rows.length) return empty(ctx, width, height, '暂无K线数据');
  const pad = { l: 46, r: 16, t: 20, b: 34 }, chartH = height - pad.t - pad.b;
  const min = Math.min(...rows.map(r => r.low)), max = Math.max(...rows.map(r => r.high));
  const y = value => pad.t + (max - value) / Math.max(max - min, 0.01) * chartH;
  const step = (width - pad.l - pad.r) / rows.length;
  ctx.strokeStyle = COLORS.grid; ctx.fillStyle = COLORS.text; ctx.font = '11px system-ui';
  for (let i = 0; i <= 4; i += 1) {
    const py = pad.t + chartH * i / 4; ctx.beginPath(); ctx.moveTo(pad.l, py); ctx.lineTo(width - pad.r, py); ctx.stroke();
    ctx.fillText((max - (max - min) * i / 4).toFixed(2), 3, py + 4);
  }
  rows.forEach((r, i) => {
    const x = pad.l + step * (i + .5), color = r.close >= r.open ? COLORS.up : COLORS.down;
    ctx.strokeStyle = color; ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(x, y(r.high)); ctx.lineTo(x, y(r.low)); ctx.stroke();
    const top = y(Math.max(r.open, r.close)), bottom = y(Math.min(r.open, r.close));
    ctx.fillRect(x - Math.max(1, step * .28), top, Math.max(2, step * .56), Math.max(1, bottom - top));
    if (r.time.replaceAll('-', '') === selectedDate && orders.length) {
      ctx.fillStyle = orders.some(o => o.side === 'buy') ? '#ffcf5c' : '#6fb7ff';
      ctx.beginPath(); ctx.moveTo(x, y(r.low) + 14); ctx.lineTo(x - 5, y(r.low) + 23); ctx.lineTo(x + 5, y(r.low) + 23); ctx.fill();
    }
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
