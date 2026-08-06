function tencentCode(code) {
  const [symbol, exchange = ''] = String(code).toLowerCase().split('.');
  return `${exchange === 'sh' ? 'sh' : 'sz'}${symbol}`;
}

function dateText(value) {
  const text = String(value || '').replaceAll('-', '');
  return text.length === 8 ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6)}` : '';
}

function dateBefore(endDate, days) {
  const end = dateText(endDate);
  if (!end) return '';
  const date = new Date(`${end}T00:00:00`);
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
}

async function tencent(path, param, origin = 'https://web.ifzq.gtimg.cn') {
  const url = `${origin}/appstock/app/${path}?param=${encodeURIComponent(param)}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error('腾讯财经行情请求失败');
  const payload = await response.json();
  if (payload?.code !== 0) throw new Error('腾讯财经行情暂时不可用');
  return payload;
}

function rows(payload, code, field) {
  const raw = payload?.data?.[tencentCode(code)]?.[field] || [];
  return raw.map((row) => {
    const [time, open, close, high, low, volume, amount] = row;
    return { time, open: +open, close: +close, high: +high, low: +low, volume: +volume, amount: +amount };
  }).filter(row => Number.isFinite(row.open) && Number.isFinite(row.close) && Number.isFinite(row.high) && Number.isFinite(row.low));
}

export async function fetchDaily(code, endDate = '', startDate = '') {
  const end = dateText(endDate) || '2050-01-01';
  const start = dateBefore(startDate || endDate, startDate ? 90 : 900);
  const payload = await tencent('fqkline/get', `${tencentCode(code)},day,${start},${end},640,qfq`);
  return rows(payload, code, 'qfqday');
}

export async function fetchThirtyMinute(code, endDate = '') {
  const payload = await tencent('kline/mkline', `${tencentCode(code)},m30,,640`, 'https://ifzq.gtimg.cn');
  return rows(payload, code, 'm30');
}
