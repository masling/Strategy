function secid(code) {
  const [symbol, exchange = ''] = String(code).toUpperCase().split('.');
  return `${exchange === 'SH' ? 1 : 0}.${symbol}`;
}

function jsonp(url) {
  return new Promise((resolve, reject) => {
    const callback = `qmt_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    const script = document.createElement('script');
    const timer = setTimeout(() => finish(new Error('行情请求超时')), 9000);
    function finish(error, value) {
      clearTimeout(timer); delete window[callback]; script.remove();
      error ? reject(error) : resolve(value);
    }
    window[callback] = (value) => finish(null, value);
    script.onerror = () => finish(new Error('公开行情源暂时不可用'));
    script.src = `${url}&cb=${callback}`;
    document.head.appendChild(script);
  });
}

export async function fetchDaily(code, endDate = '') {
  const end = String(endDate || '20500101').replaceAll('-', '');
  const url = `https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=${secid(code)}&klt=101&fqt=1&beg=0&end=${end}&lmt=160&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61`;
  const payload = await jsonp(url);
  return (payload?.data?.klines || []).map((row) => {
    const [time, open, close, high, low, volume, amount] = row.split(',');
    return { time, open: +open, close: +close, high: +high, low: +low, volume: +volume, amount: +amount };
  });
}

export async function fetchIntraday(code) {
  const url = `https://push2his.eastmoney.com/api/qt/stock/trends2/get?secid=${secid(code)}&ndays=1&iscr=0&fields1=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13&fields2=f51,f52,f53,f54,f55,f56,f57,f58`;
  const payload = await jsonp(url);
  return (payload?.data?.trends || []).map((row) => {
    const [time, open, close, high, low, volume, amount, average] = row.split(',');
    return { time, open: +open, close: +close, high: +high, low: +low, volume: +volume, amount: +amount, average: +average };
  });
}
