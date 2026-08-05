#coding:gbk
# DOWNLOAD_BUILD: V1.4.3_20260805_BACKTEST_CAPITAL_FALLBACK

import datetime

import numpy as np
import pandas as pd


RUN_MODE = "BACKTEST"
STRATEGY_NAME = "QMT_MC_ROTATION_V1_4_3"
BACKTEST_INITIAL_CAPITAL = 1000000.0
REBALANCE_EVERY = 5
MAX_SECTORS_PER_STYLE = 3
MAX_STOCKS_PER_STYLE = 2
MAX_PER_SECTOR = 2
MAX_STOCK_WEIGHT = 0.15
MIN_AVERAGE_AMOUNT = 50000000.0
STYLE_STRONG_SCORE = 80.0
STYLE_WATCH_SCORE = 70.0
STYLE_STRONG_EXPOSURE = 0.25
STYLE_WATCH_EXPOSURE = 0.10
MAX_TOTAL_EXPOSURE = 0.80
INTRADAY_REDUCE_RATIO = 1.0 / 3.0
ALLOW_CHINEXT = True
ALLOW_STAR = False
ALLOW_BSE = False
SW1_SECTOR_NAMES = tuple("SW1" + name for name in (
    u"\u519c\u6797\u7267\u6e14",
    u"\u57fa\u7840\u5316\u5de5",
    u"\u94a2\u94c1",
    u"\u6709\u8272\u91d1\u5c5e",
    u"\u7535\u5b50",
    u"\u6c7d\u8f66",
    u"\u5bb6\u7528\u7535\u5668",
    u"\u98df\u54c1\u996e\u6599",
    u"\u7eba\u7ec7\u670d\u9970",
    u"\u8f7b\u5de5\u5236\u9020",
    u"\u533b\u836f\u751f\u7269",
    u"\u516c\u7528\u4e8b\u4e1a",
    u"\u4ea4\u901a\u8fd0\u8f93",
    u"\u623f\u5730\u4ea7",
    u"\u5546\u8d38\u96f6\u552e",
    u"\u793e\u4f1a\u670d\u52a1",
    u"\u7efc\u5408",
    u"\u5efa\u7b51\u6750\u6599",
    u"\u5efa\u7b51\u88c5\u9970",
    u"\u7535\u529b\u8bbe\u5907",
    u"\u56fd\u9632\u519b\u5de5",
    u"\u8ba1\u7b97\u673a",
    u"\u4f20\u5a92",
    u"\u901a\u4fe1",
    u"\u94f6\u884c",
    u"\u975e\u94f6\u91d1\u878d",
    u"\u7f8e\u5bb9\u62a4\u7406",
    u"\u7164\u70ad",
    u"\u77f3\u6cb9\u77f3\u5316",
    u"\u73af\u4fdd",
    u"\u673a\u68b0\u8bbe\u5907",
))
STYLE_INDEXES = [
    ("000300.SH", u"\u6caa\u6df1300"),
    ("000905.SH", u"\u4e2d\u8bc1500"),
    ("000852.SH", u"\u4e2d\u8bc11000"),
    ("399006.SZ", u"\u521b\u4e1a\u677f"),
]


class _State(object):
    pass


A = _State()


def _context_datetime(value, end_of_day=False):
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        suffix = "235959" if end_of_day else "000000"
        return datetime.datetime.strptime(value.strftime("%Y%m%d") + suffix,
                                          "%Y%m%d%H%M%S")
    digits = "".join(character for character in str(value or "")
                     if character.isdigit())
    if len(digits) >= 14:
        return datetime.datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
    if len(digits) >= 8:
        suffix = "235959" if end_of_day else "000000"
        return datetime.datetime.strptime(digits[:8] + suffix,
                                          "%Y%m%d%H%M%S")
    return None


def _backtest_capital(context):
    try:
        capital = float(getattr(context, "capital", -1.0))
    except (TypeError, ValueError):
        capital = -1.0
    if np.isfinite(capital) and capital > 0.0:
        return capital, False
    return float(BACKTEST_INITIAL_CAPITAL), True


def _clean_array(values):
    arr = np.asarray(values, dtype=float)
    return arr[np.isfinite(arr)]


def _mean_tail(values, count):
    arr = _clean_array(values)
    if len(arr) < count:
        return float("nan")
    return float(np.mean(arr[-count:]))


def _return(values, periods):
    arr = _clean_array(values)
    if len(arr) <= periods or arr[-periods - 1] <= 0:
        return float("nan")
    return float(arr[-1] / arr[-periods - 1] - 1.0)


def trend_71340_score(daily_close):
    daily = _clean_array(daily_close)
    if len(daily) < 45:
        return None
    ma7 = _mean_tail(daily, 7)
    ma13 = _mean_tail(daily, 13)
    ma40 = _mean_tail(daily, 40)
    ma13_prev = float(np.mean(daily[-18:-5]))
    ma40_prev = float(np.mean(daily[-45:-5]))
    score = 0.0
    score += 20.0 if daily[-1] > ma40 else 0.0
    score += 20.0 if ma40 > ma40_prev else 0.0
    score += 15.0 if daily[-1] > ma13 else 0.0
    score += 15.0 if ma13 > ma13_prev else 0.0
    score += 10.0 if ma13 > ma40 else 0.0
    score += 5.0 if daily[-1] > ma7 else 0.0
    score += 10.0 if ma7 > ma13 else 0.0
    score += 5.0 if _return(daily, 13) > 0.0 else 0.0
    if not (daily[-1] > ma40 and ma40 > ma40_prev):
        score = min(score, 69.0)
    return round(score, 2)


def style_exposure_map(scores, max_total=MAX_TOTAL_EXPOSURE):
    budgets = {}
    for code, score in (scores or {}).items():
        if score is None:
            continue
        if float(score) >= STYLE_STRONG_SCORE:
            budgets[code] = STYLE_STRONG_EXPOSURE
        elif float(score) >= STYLE_WATCH_SCORE:
            budgets[code] = STYLE_WATCH_EXPOSURE
    total = sum(budgets.values())
    if total > float(max_total) and total > 0.0:
        scale = float(max_total) / total
        budgets = {
            code: round(value * scale, 10)
            for code, value in budgets.items()
        }
    return budgets


def _percentile_map(items, field):
    ordered = sorted(items, key=lambda item: float(item[1].get(field, 0.0)))
    if not ordered:
        return {}
    if len(ordered) == 1:
        return {ordered[0][0]: 0.5}
    result = {}
    denominator = float(len(ordered) - 1)
    for index, item in enumerate(ordered):
        result[item[0]] = index / denominator
    return result


def rank_sectors(features, max_count=3):
    eligible = [(code, feature) for code, feature in features.items()
                if feature.get("eligible", False)]
    if not eligible:
        return []
    r13_rank = _percentile_map(eligible, "rel13")
    r40_rank = _percentile_map(eligible, "rel40")
    amount_rank = _percentile_map(eligible, "amount_ratio")
    ranked = []
    for code, feature in eligible:
        distance = max(0.0, float(feature.get("distance_ma13", 0.0)))
        overheat = min(80.0, max(0.0, (distance - 0.12) * 666.6667))
        score = (
            30.0 * r13_rank[code]
            + 25.0 * r40_rank[code]
            + 25.0 * float(feature.get("trend", 0.0))
            + 10.0 * amount_rank[code]
            - overheat
        )
        ranked.append((code, round(score, 4)))
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:max_count]


def sector_member_name(index_name):
    text = str(index_name or "").strip()
    for suffix in (u"\u52a0\u6743\u6307\u6570", u"\u52a0\u6743", "WeightedIndex", "Weighted"):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
    if "SW1" in text:
        return text[text.index("SW1"):]
    return "SW1" + text


def sector_proxy_frame(history, member_codes, min_members=5):
    return_parts = []
    amount_parts = []
    for code in member_codes or []:
        frame = history.get(code)
        if frame is None or len(frame) < 2 or "close" not in frame.columns:
            continue
        data = frame.replace([np.inf, -np.inf], np.nan).sort_index()
        close = pd.Series(
            np.asarray(data["close"], dtype=float),
            index=data.index,
            name=code,
        )
        close = close.where(close > 0.0)
        previous = close.shift(1)
        daily_return = close / previous - 1.0
        daily_return.loc[close.notna() & previous.isna()] = 0.0
        daily_return = daily_return.where(daily_return.abs() <= 0.35)
        return_parts.append(daily_return)
        if "amount" in data.columns:
            amount_parts.append(pd.Series(
                np.asarray(data["amount"], dtype=float),
                index=data.index,
                name=code,
            ))
    if not return_parts:
        return None

    returns = pd.concat(return_parts, axis=1).sort_index()
    required = min(max(1, int(min_members)), len(return_parts))
    valid_count = returns.notna().sum(axis=1)
    average_return = returns.mean(axis=1, skipna=True)
    average_return = average_return.where(valid_count >= required)
    proxy_close = (1.0 + average_return).cumprod() * 100.0

    if amount_parts:
        amounts = pd.concat(amount_parts, axis=1).sort_index()
        proxy_amount = amounts.sum(axis=1, min_count=1)
    else:
        proxy_amount = pd.Series(1.0, index=proxy_close.index)
    result = pd.DataFrame({
        "close": proxy_close,
        "amount": proxy_amount.reindex(proxy_close.index),
    })
    return result.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])


def sector_feature(frame, benchmark_close):
    if frame is None or len(frame) < 45 or "close" not in frame.columns:
        return None
    data = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    benchmark = _clean_array(benchmark_close)
    close = _clean_array(data["close"])
    if len(close) < 45 or len(benchmark) < 45:
        return None
    ma7 = float(np.mean(close[-7:]))
    ma13 = float(np.mean(close[-13:]))
    ma40 = float(np.mean(close[-40:]))
    ma13_prev = float(np.mean(close[-18:-5]))
    ma40_prev = float(np.mean(close[-45:-5]))
    r13 = _return(close, 13)
    r40 = _return(close, 40)
    b13 = _return(benchmark, 13)
    b40 = _return(benchmark, 40)
    trend = 0.0
    trend += 0.25 if close[-1] > ma13 else 0.0
    trend += 0.25 if ma13 > ma40 else 0.0
    trend += 0.25 if ma13 > ma13_prev else 0.0
    trend += 0.25 if ma40 > ma40_prev else 0.0
    if "amount" in data.columns and len(data["amount"].dropna()) >= 20:
        amount = np.asarray(data["amount"], dtype=float)
        base = float(np.mean(amount[-20:]))
        recent = float(np.mean(amount[-5:]))
        amount_ratio = recent / base if base > 0 else 0.0
    else:
        amount_ratio = 1.0
    distance = close[-1] / ma13 - 1.0 if ma13 > 0 else 0.0
    rel13 = r13 - b13
    rel40 = r40 - b40
    eligible = bool(
        close[-1] > ma13 > ma40
        and ma13 > ma13_prev and ma40 > ma40_prev
        and rel13 > 0.0 and rel40 > 0.0
    )
    return {
        "return13": r13,
        "return40": r40,
        "rel13": rel13,
        "rel40": rel40,
        "trend": round(trend, 4),
        "amount_ratio": amount_ratio,
        "distance_ma13": distance,
        "eligible": eligible,
    }


def fetch_history(context, fields, stock_codes, period, count, end_time,
                  dividend_type="none", chunk_size=200):
    result = {}
    codes = list(stock_codes or [])
    for start in range(0, len(codes), int(chunk_size)):
        chunk = codes[start:start + int(chunk_size)]
        data = context.get_market_data_ex(
            fields, chunk, period=period, start_time="", end_time=end_time,
            count=int(count), dividend_type=dividend_type,
            fill_data=False, subscribe=False,
        )
        if data:
            result.update(data)
    return result


def _atr(frame, count=14):
    high = np.asarray(frame["high"], dtype=float)
    low = np.asarray(frame["low"], dtype=float)
    close = np.asarray(frame["close"], dtype=float)
    if len(close) < count + 1:
        return float("nan")
    previous = close[:-1]
    true_range = np.maximum(
        high[1:] - low[1:],
        np.maximum(np.abs(high[1:] - previous), np.abs(low[1:] - previous)),
    )
    return float(np.mean(true_range[-count:]))


def stock_feature(frame, sector_return13, sector_return40,
                  min_average_amount=50000000.0):
    required = ["close", "high", "low", "amount", "volume"]
    if frame is None or len(frame) < 45:
        return None
    if any(field not in frame.columns for field in required):
        return None
    data = frame.copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    if len(data) < 45:
        return None

    close = np.asarray(data["close"], dtype=float)
    amount = np.asarray(data["amount"], dtype=float)
    volume = np.asarray(data["volume"], dtype=float)
    if close[-1] <= 0 or volume[-1] <= 0:
        return None
    if "suspendFlag" in data.columns and float(data["suspendFlag"].iloc[-1]) != 0.0:
        return None

    ma7 = float(np.mean(close[-7:]))
    ma13 = float(np.mean(close[-13:]))
    ma40 = float(np.mean(close[-40:]))
    ma13_prev = float(np.mean(close[-18:-5]))
    ma40_prev = float(np.mean(close[-45:-5]))
    average_amount = float(np.mean(amount[-20:]))
    r5 = _return(close, 5)
    r13 = _return(close, 13)
    r40 = _return(close, 40)
    distance_ma13 = close[-1] / ma13 - 1.0
    high40 = float(np.max(np.asarray(data["high"], dtype=float)[-40:]))
    high_proximity = close[-1] / high40 if high40 > 0 else 0.0
    atr = _atr(data, 14)

    if not (close[-1] > ma7 > ma13 > ma40):
        return None
    if not (ma13 > ma13_prev and ma40 > ma40_prev):
        return None
    if average_amount < float(min_average_amount):
        return None
    if not (-0.08 <= r5 <= 0.15):
        return None
    if not (0.0 <= distance_ma13 <= 0.12):
        return None
    if high_proximity < 0.85:
        return None
    rs13 = r13 - float(sector_return13)
    rs40 = r40 - float(sector_return40)
    if rs13 <= 0.0 or rs40 <= 0.0:
        return None

    returns = np.diff(close[-14:]) / close[-14:-1]
    volatility = float(np.std(returns)) if len(returns) else 0.0
    return {
        "close": float(close[-1]),
        "ma7": ma7,
        "ma13": ma13,
        "ma40": ma40,
        "r13": r13,
        "r40": r40,
        "rs13": rs13,
        "rs40": rs40,
        "distance_ma13": distance_ma13,
        "high_proximity": high_proximity,
        "average_amount": average_amount,
        "volatility": volatility,
        "atr": atr,
    }


def position_metrics(frame):
    required = ["close", "high", "low"]
    if frame is None or len(frame) < 45:
        return None
    if any(field not in frame.columns for field in required):
        return None
    data = frame.copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    if len(data) < 45:
        return None
    close = np.asarray(data["close"], dtype=float)
    return {
        "close": float(close[-1]),
        "high": float(data["high"].iloc[-1]),
        "ma7": float(np.mean(close[-7:])),
        "ma13": float(np.mean(close[-13:])),
        "ma40": float(np.mean(close[-40:])),
        "atr": _atr(data, 14),
    }


def select_stocks(candidates, max_count=6, max_per_sector=2):
    ordered = sorted(candidates, key=lambda item: item["score"], reverse=True)
    selected = []
    sector_counts = {}
    used_codes = set()
    for candidate in ordered:
        code = candidate["code"]
        sector = candidate["sector"]
        if code in used_codes:
            continue
        if sector_counts.get(sector, 0) >= max_per_sector:
            continue
        selected.append(candidate)
        used_codes.add(code)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(selected) >= max_count:
            break
    return selected


def score_stock_candidates(candidates):
    if not candidates:
        return []
    items = [(item["code"], item["feature"]) for item in candidates]
    rank_fields = {}
    for field in ("rs13", "rs40", "r13", "high_proximity", "average_amount"):
        rank_fields[field] = _percentile_map(items, field)
    volatility_order = sorted(
        items, key=lambda item: float(item[1].get("volatility", 0.0)), reverse=True
    )
    if len(volatility_order) == 1:
        volatility_rank = {volatility_order[0][0]: 0.5}
    else:
        denominator = float(len(volatility_order) - 1)
        volatility_rank = {
            item[0]: index / denominator for index, item in enumerate(volatility_order)
        }
    scored = []
    for item in candidates:
        code = item["code"]
        score = (
            30.0 * rank_fields["rs13"][code]
            + 25.0 * rank_fields["rs40"][code]
            + 15.0 * rank_fields["r13"][code]
            + 10.0 * rank_fields["high_proximity"][code]
            + 10.0 * rank_fields["average_amount"][code]
            + 10.0 * volatility_rank[code]
        )
        result = dict(item)
        result["score"] = round(score, 4)
        scored.append(result)
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored


def board_allowed(code, allow_chinext=True, allow_star=False, allow_bse=False):
    symbol = str(code).split(".")[0]
    market = str(code).split(".")[-1].upper() if "." in str(code) else ""
    if market == "BJ" or symbol.startswith(("4", "8", "92")):
        return bool(allow_bse)
    if symbol.startswith(("688", "689")):
        return bool(allow_star)
    if symbol.startswith(("300", "301")):
        return bool(allow_chinext)
    return True


def exit_reason(close, high, ma13, ma40, atr, entry_price,
                prior_below_ma13_days, still_selected, style_exposure):
    if style_exposure <= 0.0:
        return "style_risk"
    if atr > 0 and close <= entry_price - 2.0 * atr:
        return "initial_stop"
    if close < ma40:
        return "ma40_break"
    if (prior_below_ma13_days >= 1 and close < ma13
            and high >= ma13 * 0.995):
        return "ma13_rebound_failed"
    if close < ma13 and prior_below_ma13_days + 1 >= 3:
        return "ma13_break"
    if not still_selected:
        return "sector_rotation"
    return None


def _datetime_index(values):
    converted = []
    for value in values:
        if isinstance(value, (pd.Timestamp, datetime.datetime)):
            converted.append(pd.Timestamp(value))
            continue
        text = str(value).strip()
        if text.endswith(".0") and text[:-2].isdigit():
            text = text[:-2]
        digits = "".join(character for character in text if character.isdigit())
        try:
            if len(digits) >= 14:
                converted.append(pd.to_datetime(digits[:14], format="%Y%m%d%H%M%S"))
            elif len(digits) == 12:
                converted.append(pd.to_datetime(digits, format="%Y%m%d%H%M"))
            elif text.isdigit() and len(text) >= 13:
                converted.append(pd.to_datetime(int(text), unit="ms"))
            else:
                converted.append(pd.to_datetime(value))
        except Exception:
            converted.append(pd.NaT)
    return pd.DatetimeIndex(converted)


def aggregate_5m_to_30m(frame):
    required = ["open", "high", "low", "close", "volume"]
    columns = required + (["amount"] if frame is not None and "amount" in frame.columns else [])
    if frame is None or frame.empty or any(field not in frame.columns for field in required):
        return pd.DataFrame(columns=columns)
    data = frame[columns].copy()
    data.index = _datetime_index(data.index)
    data = data[~data.index.isna()].sort_index()
    groups = {}
    for timestamp, row in data.iterrows():
        minute = timestamp.hour * 60 + timestamp.minute
        session_start = None
        session_id = None
        if 9 * 60 + 30 < minute <= 11 * 60 + 30:
            session_start = 9 * 60 + 30
            session_id = "AM"
        elif 13 * 60 < minute <= 15 * 60:
            session_start = 13 * 60
            session_id = "PM"
        if session_start is None:
            continue
        offset = minute - session_start
        if offset % 5 != 0:
            continue
        slot = int((offset - 1) / 30)
        endpoint_minute = session_start + (slot + 1) * 30
        endpoint = timestamp.normalize() + pd.Timedelta(minutes=endpoint_minute)
        key = (timestamp.date(), session_id, slot, endpoint)
        groups.setdefault(key, []).append((timestamp, row))

    bars = []
    endpoints = []
    for key in sorted(groups.keys(), key=lambda item: item[3]):
        rows = sorted(groups[key], key=lambda item: item[0])
        endpoint = key[3]
        expected = [endpoint - pd.Timedelta(minutes=value)
                    for value in (25, 20, 15, 10, 5, 0)]
        timestamps = [item[0].replace(second=0, microsecond=0) for item in rows]
        if timestamps != expected:
            continue
        part = pd.DataFrame([item[1] for item in rows], index=timestamps)
        bar = {
            "open": float(part["open"].iloc[0]),
            "high": float(part["high"].max()),
            "low": float(part["low"].min()),
            "close": float(part["close"].iloc[-1]),
            "volume": float(part["volume"].sum()),
        }
        if "amount" in part.columns:
            bar["amount"] = float(part["amount"].sum())
        bars.append(bar)
        endpoints.append(endpoint)
    return pd.DataFrame(bars, index=pd.DatetimeIndex(endpoints), columns=columns)


def intraday_action(frame30, ma7, ma13, reduced):
    if frame30 is None or len(frame30) < 2:
        return None
    data = frame30.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["open", "high", "low", "close", "volume"]
    )
    if len(data) < 2:
        return None
    previous = data.iloc[-2]
    latest = data.iloc[-1]
    if reduced:
        near_support = any(
            level > 0.0 and abs(float(previous["low"]) / level - 1.0) <= 0.02
            for level in (float(ma7), float(ma13))
        )
        if (near_support and float(latest["low"]) >= float(previous["low"])
                and float(latest["close"]) > float(previous["high"])):
            return "add"
        return None
    if len(data) < 22:
        return None
    base_volume = float(np.mean(np.asarray(data["volume"].iloc[-22:-2], dtype=float)))
    price_range = float(previous["high"] - previous["low"])
    if base_volume <= 0.0 or price_range <= 0.0:
        return None
    upper_shadow = float(previous["high"] - max(previous["open"], previous["close"]))
    closes_low = float(previous["close"]) <= float(previous["low"]) + 0.5 * price_range
    reversal_bar = closes_low or upper_shadow >= 0.35 * price_range
    confirmed = float(latest["close"]) < float(previous["low"])
    if (float(previous["volume"]) >= 1.8 * base_volume
            and reversal_bar and confirmed):
        return "reduce"
    return None


def target_shares(total_asset, exposure, position_count, price,
                  max_weight=0.15):
    if total_asset <= 0 or exposure <= 0 or position_count <= 0 or price <= 0:
        return 0
    target_weight = min(float(max_weight), float(exposure) / position_count)
    target_value = float(total_asset) * target_weight
    return int(target_value / float(price) / 100.0) * 100


def _instrument_name(context, code):
    try:
        return str(context.get_stock_name(code) or code)
    except Exception:
        try:
            detail = context.get_instrument_detail(code)
            return str(detail.get("InstrumentName", code)) if detail else str(code)
        except Exception:
            return str(code)


def _is_st_on(context, code, asof):
    day = str(asof)[:8]
    try:
        history = context.get_his_st_data(code) or {}
        for ranges in history.values():
            for date_range in ranges:
                if len(date_range) >= 2:
                    if str(date_range[0]) <= day <= str(date_range[1]):
                        return True
    except Exception:
        pass
    name = _instrument_name(context, code).upper()
    return "ST" in name or "PT" in name


def _close_values(frame):
    if frame is None or "close" not in frame.columns:
        return np.asarray([], dtype=float)
    return _clean_array(frame["close"])


def _market_state(context, asof):
    codes = [item[0] for item in STYLE_INDEXES]
    daily = fetch_history(context, ["close"], codes, "1d", 55, asof)
    details = {}
    benchmarks = {}
    for code, _ in STYLE_INDEXES:
        daily_close = _close_values(daily.get(code))
        score = trend_71340_score(daily_close)
        if score is None:
            continue
        details[code] = score
        benchmarks[code] = daily_close
    style_exposures = style_exposure_map(details)
    return {
        "details": details,
        "style_exposures": style_exposures,
        "exposure": round(sum(style_exposures.values()), 10),
        "benchmarks": benchmarks,
    }


def _style_members(context, active_styles):
    board_by_code = dict(STYLE_INDEXES)
    result = {}
    for code in active_styles:
        board = board_by_code.get(code, "")
        try:
            members = context.get_stock_list_in_sector(board) or []
        except Exception:
            members = []
        allowed = set(
            member for member in members
            if board_allowed(member, ALLOW_CHINEXT, ALLOW_STAR, ALLOW_BSE)
        )
        if allowed:
            result[code] = allowed
        else:
            print("ERROR style board is empty:", code, board)
    return result


def _sector_selection(context, asof, benchmark, style_members, style_code):
    records = {}
    all_codes = []
    seen_codes = set()
    for sector_name in SW1_SECTOR_NAMES:
        try:
            members = context.get_stock_list_in_sector(sector_name) or []
        except Exception:
            members = []
        members = [
            code for code in members
            if code in style_members
            and board_allowed(code, ALLOW_CHINEXT, ALLOW_STAR, ALLOW_BSE)
        ]
        if not members:
            continue
        records[sector_name] = {
            "code": sector_name,
            "name": sector_name,
            "member_sector": sector_name,
            "members": members,
            "style": style_code,
        }
        for code in members:
            if code not in seen_codes:
                seen_codes.add(code)
                all_codes.append(code)
    if not records:
        print("ERROR SW1 sector boards are empty")
        return []

    history = fetch_history(
        context, ["close", "amount"], all_codes, "1d", 55, asof,
        "back_ratio",
    )
    features = {}
    for sector_name, record in records.items():
        proxy = sector_proxy_frame(history, record["members"], 5)
        feature = sector_feature(proxy, benchmark)
        if feature is None:
            continue
        features[sector_name] = feature
        record["feature"] = feature
    if not features:
        print("ERROR SW1 member history is insufficient")
        return []
    logged = getattr(A, "sector_source_logged", set())
    if style_code not in logged:
        print(
            "SECTOR_SOURCE", style_code, "SW1_MEMBER_PROXY boards", len(records),
            "stocks", len(all_codes), "histories", len(history)
        )
        logged.add(style_code)
        A.sector_source_logged = logged
    ranked = rank_sectors(features, MAX_SECTORS_PER_STYLE)
    selected = []
    for code, score in ranked:
        record = dict(records[code])
        record["score"] = score
        selected.append(record)
    return selected


def _stock_selection(context, asof, sectors):
    members_by_code = {}
    sector_by_code = {}
    all_codes = []
    for sector in sectors:
        for code in sector["members"]:
            if not board_allowed(
                    code, ALLOW_CHINEXT, ALLOW_STAR, ALLOW_BSE):
                continue
            if code not in members_by_code:
                members_by_code[code] = True
                all_codes.append(code)
                sector_by_code[code] = sector
    history = fetch_history(
        context,
        ["close", "high", "low", "amount", "volume", "suspendFlag"],
        all_codes,
        "1d",
        55,
        asof,
        "back_ratio",
    )
    candidates = []
    for code in all_codes:
        sector = sector_by_code[code]
        sector_feature_data = sector["feature"]
        feature = stock_feature(
            history.get(code),
            sector_feature_data["return13"],
            sector_feature_data["return40"],
            MIN_AVERAGE_AMOUNT,
        )
        if feature is None or _is_st_on(context, code, asof):
            continue
        candidates.append({
            "code": code,
            "sector": sector["member_sector"],
            "sector_code": sector["code"],
            "style": sector["style"],
            "feature": feature,
        })
    selected = select_stocks(
        score_stock_candidates(candidates), MAX_STOCKS_PER_STYLE, MAX_PER_SECTOR
    )
    for item in selected:
        item["name"] = _instrument_name(context, item["code"])
    return selected


def _backtest_snapshot(context):
    try:
        holdings = get_result_records("holdings", context.barpos, context) or []
        net_value = float(context.get_net_value(context.barpos))
        capital, used_fallback = _backtest_capital(context)
    except Exception as error:
        print("ERROR backtest portfolio query failed:", error)
        return None

    if used_fallback:
        print(
            "WARNING invalid context.capital, using configured capital",
            capital,
        )

    balance = capital * net_value
    market_value = 0.0
    position_map = {}
    for holding in holdings:
        volume = int(getattr(holding, "position", 0))
        if volume <= 0:
            continue
        code = str(holding.stockcode) + "." + str(holding.market)
        current_price = float(getattr(holding, "current_price", 0.0))
        open_price = float(getattr(holding, "trade_price", current_price))
        market_value += current_price * volume
        position_map[code] = {
            "volume": volume,
            "available": volume,
            "open_price": open_price,
        }
    available_cash = max(0.0, balance - market_value)
    print(
        "PORTFOLIO",
        "capital", capital,
        "net_value", net_value,
        "balance", balance,
        "market_value", market_value,
        "cash", available_cash,
        "positions", len(position_map),
    )
    return {
        "balance": balance,
        "available_cash": available_cash,
        "positions": position_map,
    }


def _account_snapshot(context):
    if A.mode == "BACKTEST":
        return _backtest_snapshot(context)
    try:
        accounts = get_trade_detail_data(A.acct, A.acct_type, "account")
        positions = get_trade_detail_data(A.acct, A.acct_type, "position")
    except Exception as error:
        print("ERROR account query failed:", error)
        return None
    if not accounts:
        print("ERROR account is not logged in:", A.acct)
        return None
    account_data = accounts[0]
    position_map = {}
    for position in positions or []:
        code = str(position.m_strInstrumentID) + "." + str(position.m_strExchangeID)
        volume = int(position.m_nVolume)
        if volume <= 0:
            continue
        position_map[code] = {
            "volume": volume,
            "available": int(position.m_nCanUseVolume),
            "open_price": float(position.m_dOpenPrice),
        }
    return {
        "balance": float(account_data.m_dBalance),
        "available_cash": float(account_data.m_dAvailable),
        "positions": position_map,
    }


def _refresh_owned_codes(snapshot):
    if A.mode == "BACKTEST":
        A.owned_codes.update(snapshot["positions"].keys())
        return
    try:
        deals = get_trade_detail_data(
            A.acct, A.acct_type, "deal", STRATEGY_NAME
        )
    except Exception:
        deals = []
    for deal in deals or []:
        code = str(deal.m_strInstrumentID) + "." + str(deal.m_strExchangeID)
        A.owned_codes.add(code)


def _managed_positions(snapshot):
    if A.mode == "BACKTEST":
        return dict(snapshot["positions"])
    return {
        code: value for code, value in snapshot["positions"].items()
        if code in A.owned_codes
    }


def _pending_order_codes():
    if A.mode == "BACKTEST":
        return set()
    try:
        orders = get_trade_detail_data(
            A.acct, A.acct_type, "order", STRATEGY_NAME
        )
    except Exception:
        orders = []
    terminal_statuses = {53, 54, 56, 57}
    pending = set()
    for order in orders or []:
        try:
            status = int(order.m_nOrderStatus)
        except Exception:
            status = -1
        if status in terminal_statuses:
            continue
        code = str(order.m_strInstrumentID) + "." + str(order.m_strExchangeID)
        pending.add(code)
    return pending


def _send_order(context, side, code, volume, trade_date, reason):
    volume = int(volume)
    if volume <= 0:
        return False
    key = (str(trade_date), str(code), str(side))
    if key in A.sent_order_keys:
        return False
    if side == "buy":
        operation = A.buy_code
    else:
        operation = A.sell_code
    price_type = 5 if A.mode == "BACKTEST" else 14
    quick_trade = 0 if A.mode == "BACKTEST" else 1
    remark = str(trade_date) + "_" + side + "_" + str(reason)
    try:
        passorder(
            operation, 1101, A.acct, code, price_type, -1, volume,
            STRATEGY_NAME, quick_trade, remark, context
        )
    except Exception as error:
        print("ERROR order failed:", side, code, volume, error)
        return False
    A.sent_order_keys.add(key)
    if side == "buy":
        A.owned_codes.add(code)
    print("ORDER", trade_date, side, code, volume, reason)
    return True


def _simulation_tick(context, codes):
    if A.mode == "BACKTEST" or not codes:
        return {}
    try:
        return context.get_full_tick(list(codes)) or {}
    except Exception as error:
        print("WARN tick query failed:", error)
        return {}


def _execution_price(code, candidate_map, tick_map, side):
    tick = tick_map.get(code, {})
    if tick:
        if side == "buy":
            prices = tick.get("askPrice", []) or []
        else:
            prices = tick.get("bidPrice", []) or []
        if prices and float(prices[0]) > 0:
            return float(prices[0])
        if float(tick.get("lastPrice", 0.0)) > 0:
            return float(tick["lastPrice"])
    candidate = candidate_map.get(code)
    if candidate:
        return float(candidate["feature"].get("close", 0.0))
    return 0.0


def _buy_is_tradeable(code, tick):
    if A.mode == "BACKTEST":
        return True
    if not tick:
        return False
    price = float(tick.get("lastPrice", 0.0))
    previous = float(tick.get("lastClose", 0.0))
    ask = tick.get("askPrice", []) or []
    if price <= 0 or previous <= 0 or not ask or float(ask[0]) <= 0:
        return False
    symbol = str(code).split(".")[0]
    limit_ratio = 1.20 if symbol.startswith(("300", "301", "688", "689")) else 1.10
    if str(code).endswith(".BJ"):
        limit_ratio = 1.30
    return price / previous < limit_ratio - 0.002


def _desired_share_map(snapshot, style_exposures, candidates, tick_map):
    desired = {}
    if not candidates or not style_exposures:
        return desired
    candidate_map = {item["code"]: item for item in candidates}
    counts = {}
    for item in candidates:
        style = item.get("style")
        if float(style_exposures.get(style, 0.0)) > 0.0:
            counts[style] = counts.get(style, 0) + 1
    for item in candidates:
        code = item["code"]
        if code in getattr(A, "blocked_codes", set()):
            continue
        style = item.get("style")
        style_exposure = float(style_exposures.get(style, 0.0))
        style_count = int(counts.get(style, 0))
        if style_exposure <= 0.0 or style_count <= 0:
            continue
        price = _execution_price(code, candidate_map, tick_map, "buy")
        shares = target_shares(
            snapshot["balance"], style_exposure, style_count,
            price, MAX_STOCK_WEIGHT
        )
        scale = float(getattr(A, "intraday_scales", {}).get(code, 1.0))
        desired[code] = int(shares * scale / 100.0) * 100
    return desired


def _rebalance_to_desired(context, snapshot, trade_date):
    positions = _managed_positions(snapshot)
    candidate_map = {item["code"]: item for item in A.target_candidates}
    codes = set(positions.keys()) | set(A.desired_shares.keys())
    tick_map = _simulation_tick(context, codes)
    sent_any = False
    retry = False
    sold_codes = set()
    pending_codes = _pending_order_codes()

    for code in sorted(codes):
        current = int(positions.get(code, {}).get("volume", 0))
        available = int(positions.get(code, {}).get("available", 0))
        desired = int(A.desired_shares.get(code, 0))
        if code in pending_codes:
            retry = True
            continue
        if current <= desired or available <= 0:
            continue
        raw_volume = min(available, current - desired)
        volume = raw_volume if desired == 0 else int(raw_volume / 100) * 100
        if _send_order(context, "sell", code, volume, trade_date, "rebalance"):
            sent_any = True
            retry = True
            sold_codes.add(code)

    cash = float(snapshot["available_cash"])
    for code in sorted(A.desired_shares.keys()):
        current = int(positions.get(code, {}).get("volume", 0))
        desired = int(A.desired_shares.get(code, 0))
        if code in pending_codes:
            retry = True
            continue
        volume = int((desired - current) / 100) * 100
        if volume <= 0 or code in sold_codes:
            continue
        price = _execution_price(code, candidate_map, tick_map, "buy")
        if price <= 0 or not _buy_is_tradeable(code, tick_map.get(code, {})):
            retry = True
            continue
        affordable = int(cash * 0.98 / price / 100) * 100
        order_volume = min(volume, affordable)
        if order_volume <= 0:
            retry = True
            continue
        if _send_order(
                context, "buy", code, order_volume, trade_date, "rebalance"):
            sent_any = True
            retry = True
            cash -= order_volume * price
            if code not in A.position_meta:
                A.position_meta[code] = {
                    "entry_price": price,
                    "below_ma13_days": 0,
                    "style": candidate_map.get(code, {}).get("style"),
                }
        if order_volume < volume:
            retry = True

    if not sent_any:
        for code, desired in A.desired_shares.items():
            current = int(positions.get(code, {}).get("volume", 0))
            if abs(current - int(desired)) >= 100:
                retry = True
                break
    return retry


def _risk_exits(context, snapshot, asof, trade_date, style_exposures):
    positions = _managed_positions(snapshot)
    if not positions:
        A.position_meta = {}
        return False
    if not style_exposures:
        sent = False
        for code, position in positions.items():
            A.desired_shares[code] = 0
            if _send_order(
                    context, "sell", code, position["available"],
                    trade_date, "style_risk"):
                sent = True
        return sent

    history = fetch_history(
        context, ["close", "high", "low"], list(positions.keys()),
        "1d", 55, asof, "back_ratio"
    )
    sent = False
    active_codes = set()
    for code, position in positions.items():
        active_codes.add(code)
        metrics = position_metrics(history.get(code))
        if metrics is None:
            continue
        meta = A.position_meta.get(code)
        if meta is None:
            entry = position["open_price"] if position["open_price"] > 0 else metrics["close"]
            meta = {
                "entry_price": entry,
                "below_ma13_days": 0,
                "style": None,
            }
        candidate = next(
            (item for item in A.target_candidates if item["code"] == code),
            None,
        )
        if candidate is not None:
            meta["style"] = candidate.get("style")
        still_selected = (
            int(A.desired_shares.get(code, 0)) > 0
            and code not in A.blocked_codes
        )
        prior_below_days = int(meta.get("below_ma13_days", 0))
        style_exposure = float(style_exposures.get(meta.get("style"), 0.0))
        reason = exit_reason(
            metrics["close"], metrics["high"], metrics["ma13"],
            metrics["ma40"], metrics["atr"], meta["entry_price"],
            prior_below_days, still_selected, style_exposure,
        )
        if metrics["close"] < metrics["ma13"]:
            meta["below_ma13_days"] = prior_below_days + 1
        else:
            meta["below_ma13_days"] = 0
        A.position_meta[code] = meta
        if reason is None:
            continue
        A.desired_shares[code] = 0
        A.blocked_codes.add(code)
        A.intraday_scales.pop(code, None)
        if _send_order(
                context, "sell", code, position["available"],
                trade_date, reason):
            sent = True
    for code in list(A.position_meta.keys()):
        if code not in active_codes and code not in A.desired_shares:
            del A.position_meta[code]
    return sent


def _print_daily_summary(trade_date, market, sectors, candidates):
    print(
        "STATE", trade_date, "exposure", market["exposure"],
        "style_exposures", market["style_exposures"],
        "scores", market["details"]
    )
    if sectors:
        print(
            "SECTORS",
            [(item["style"], item["member_sector"], item["score"])
             for item in sectors],
        )
    if candidates:
        print(
            "TARGETS",
            [(item["style"], item["code"], item.get("name", ""), item["score"])
             for item in candidates],
        )


def _is_30m_close(moment):
    return moment.strftime("%H%M") in {
        "1000", "1030", "1100", "1130",
        "1330", "1400", "1430",
    }


def run_intraday_cycle(context, end_time, trade_date):
    snapshot = _account_snapshot(context)
    if snapshot is None:
        return
    positions = _managed_positions(snapshot)
    candidate_map = {item["code"]: item for item in A.target_candidates}
    codes = sorted(set(positions.keys()) & set(candidate_map.keys()))
    if not codes:
        return
    history = fetch_history(
        context,
        ["open", "high", "low", "close", "volume", "amount"],
        codes, "5m", 150, end_time, "back_ratio", 100,
    )
    tick_map = _simulation_tick(context, codes)
    for code in codes:
        candidate = candidate_map[code]
        feature = candidate["feature"]
        bars30 = aggregate_5m_to_30m(history.get(code))
        reduced = float(A.intraday_scales.get(code, 1.0)) < 0.999
        action = intraday_action(
            bars30, feature["ma7"], feature["ma13"], reduced
        )
        if action == "reduce":
            current = int(positions[code].get("volume", 0))
            available = int(positions[code].get("available", 0))
            volume = int(current * INTRADAY_REDUCE_RATIO / 100.0) * 100
            volume = min(volume, available)
            if volume <= 0:
                continue
            if _send_order(
                    context, "sell", code, volume, trade_date,
                    "intraday_top"):
                remaining_ratio = max(0.0, float(current - volume) / current)
                A.intraday_scales[code] = remaining_ratio
                A.desired_shares[code] = current - volume
                print("INTRADAY", trade_date, code, "reduce", volume)
        elif action == "add":
            previous_scale = float(A.intraday_scales.get(code, 1.0))
            A.intraday_scales[code] = 1.0
            base_desired = _desired_share_map(
                snapshot, A.current_style_exposures,
                A.target_candidates, tick_map,
            ).get(code, 0)
            current = int(positions[code].get("volume", 0))
            price = _execution_price(code, candidate_map, tick_map, "buy")
            volume = int((base_desired - current) / 100.0) * 100
            affordable = int(
                float(snapshot["available_cash"]) * 0.98
                / max(price, 1e-12) / 100.0
            ) * 100
            volume = min(volume, affordable)
            if volume <= 0 or price <= 0.0:
                A.intraday_scales[code] = previous_scale
                continue
            if _send_order(
                    context, "buy", code, volume, trade_date,
                    "intraday_addback"):
                A.desired_shares[code] = base_desired
                print("INTRADAY", trade_date, code, "add", volume)
            else:
                A.intraday_scales[code] = previous_scale


def run_daily_cycle(context, asof, trade_date):
    market = _market_state(context, asof)
    exposure = float(market["exposure"])
    style_exposures = market["style_exposures"]
    snapshot = _account_snapshot(context)
    if snapshot is None:
        return
    _refresh_owned_codes(snapshot)

    style_changed = style_exposures != A.last_style_exposures
    rebalance_due = A.rebalance_age >= REBALANCE_EVERY or style_changed
    selected_sectors = []

    if exposure <= 0.0:
        A.target_candidates = []
        A.desired_shares = {
            code: 0 for code in _managed_positions(snapshot).keys()
        }
    elif rebalance_due:
        members_by_style = _style_members(context, style_exposures.keys())
        targets = []
        used_codes = set()
        ordered_styles = sorted(
            style_exposures.keys(),
            key=lambda code: market["details"].get(code, 0.0),
            reverse=True,
        )
        for style in ordered_styles:
            members = members_by_style.get(style, set())
            benchmark = market["benchmarks"].get(style, np.asarray([]))
            if not members or len(benchmark) < 45:
                continue
            sectors = _sector_selection(
                context, asof, benchmark, members, style
            )
            selected_sectors.extend(sectors)
            for item in _stock_selection(context, asof, sectors):
                if item["code"] in used_codes:
                    continue
                used_codes.add(item["code"])
                targets.append(item)
        A.target_candidates = targets
        A.blocked_codes = set()
        A.intraday_scales = {
            code: scale for code, scale in A.intraday_scales.items()
            if code in used_codes
        }
        tick_map = _simulation_tick(
            context, [item["code"] for item in A.target_candidates]
        )
        A.desired_shares = _desired_share_map(
            snapshot, style_exposures, A.target_candidates, tick_map
        )
        print("DESIRED", trade_date, A.desired_shares)
        A.rebalance_age = 0

    exit_sent = _risk_exits(
        context, snapshot, asof, trade_date, style_exposures
    )
    should_rebalance = (
        rebalance_due or exposure <= 0.0
        or A.retry_rebalance or exit_sent
    )
    if should_rebalance:
        A.retry_rebalance = _rebalance_to_desired(
            context, snapshot, trade_date
        )
    A.rebalance_age += 1
    A.last_exposure = exposure
    A.last_style_exposures = dict(style_exposures)
    A.current_style_exposures = dict(style_exposures)
    _print_daily_summary(
        trade_date, market, selected_sectors, A.target_candidates
    )


def init(context):
    A.mode = str(RUN_MODE).upper()
    if A.mode not in ("BACKTEST", "SIMULATION"):
        raise ValueError("RUN_MODE must be BACKTEST or SIMULATION")
    if (A.mode == "BACKTEST"
            and str(getattr(context, "period", "")).lower() != "5m"):
        raise ValueError("QMT main chart period must be 5m for this strategy")
    if A.mode == "BACKTEST":
        capital, used_fallback = _backtest_capital(context)
        if used_fallback:
            context.capital = capital
            print(
                "WARNING invalid context.capital, set configured capital",
                capital,
            )
    A.backtest_start = _context_datetime(getattr(context, "start", ""))
    A.backtest_end = _context_datetime(
        getattr(context, "end", ""), end_of_day=True
    )
    A.acct = "test" if A.mode == "BACKTEST" else str(globals().get("account", ""))
    A.acct_type = "STOCK" if A.mode == "BACKTEST" else str(
        globals().get("accountType", "STOCK")
    ).upper()
    A.buy_code = 23 if A.acct_type == "STOCK" else 33
    A.sell_code = 24 if A.acct_type == "STOCK" else 34
    A.rebalance_age = REBALANCE_EVERY
    A.last_exposure = None
    A.last_style_exposures = {}
    A.current_style_exposures = {}
    A.last_processed_date = ""
    A.last_intraday_key = ""
    A.target_candidates = []
    A.desired_shares = {}
    A.position_meta = {}
    A.intraday_scales = {}
    A.blocked_codes = set()
    A.owned_codes = set()
    A.sent_order_keys = set()
    A.retry_rebalance = False
    A.sector_source_logged = set()
    A.first_bar_logged = False
    print("INIT", STRATEGY_NAME, A.mode, A.acct, A.acct_type)
    if A.mode == "BACKTEST":
        print(
            "ENGINE", "period", getattr(context, "period", ""),
            "start", getattr(context, "start", ""),
            "end", getattr(context, "end", ""),
        )


def handlebar(context):
    if A.mode == "BACKTEST":
        bar_text = timetag_to_datetime(
            context.get_bar_timetag(context.barpos), "%Y%m%d%H%M%S"
        )
        digits = "".join(
            character for character in str(bar_text) if character.isdigit()
        )
        bar_time = datetime.datetime.strptime(digits[:14], "%Y%m%d%H%M%S")
        if A.backtest_start is not None and bar_time < A.backtest_start:
            return
        if A.backtest_end is not None and bar_time > A.backtest_end:
            return
        if not A.first_bar_logged:
            print("FIRST_BAR", bar_time.strftime("%Y-%m-%d %H:%M:%S"))
            A.first_bar_logged = True
        trade_date = bar_time.strftime("%Y%m%d")
        asof = (bar_time - datetime.timedelta(days=1)).strftime("%Y%m%d")
    else:
        if not context.is_last_bar():
            return
        now = datetime.datetime.now()
        now_time = now.strftime("%H%M%S")
        if now_time < "093500" or now_time > "145000":
            return
        trade_date = now.strftime("%Y%m%d")
        asof = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
        bar_time = now
    if trade_date != A.last_processed_date:
        A.last_processed_date = trade_date
        try:
            run_daily_cycle(context, asof, trade_date)
        except Exception as error:
            print("ERROR daily cycle failed:", trade_date, error)
    if _is_30m_close(bar_time):
        intraday_key = bar_time.strftime("%Y%m%d%H%M")
        if intraday_key != A.last_intraday_key:
            A.last_intraday_key = intraday_key
            try:
                run_intraday_cycle(
                    context, bar_time.strftime("%Y%m%d%H%M%S"), trade_date
                )
            except Exception as error:
                print("ERROR intraday cycle failed:", intraday_key, error)
