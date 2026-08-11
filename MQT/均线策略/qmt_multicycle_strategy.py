#coding:gbk
# DOWNLOAD_BUILD: V1.8.1_20260811_PRICE_COORDINATE_GUARD

import datetime

import numpy as np
import pandas as pd


RUN_MODE = "BACKTEST"
STRATEGY_NAME = "QMT_MC_ROTATION_V1_8_1"
BACKTEST_INITIAL_CAPITAL = 1000000.0
REBALANCE_EVERY = 5
MAX_SECTORS_PER_STYLE = 3
MAX_STOCKS_PER_STYLE = 4
STOCK_CANDIDATE_POOL_PER_STYLE = 6
MAX_PER_SECTOR = 2
MAX_STOCK_WEIGHT = 0.15
MIN_AVERAGE_AMOUNT = 50000000.0
STYLE_STRONG_SCORE = 80.0
STYLE_WATCH_SCORE = 70.0
STYLE_STRONG_EXPOSURE = 0.25
STYLE_WATCH_EXPOSURE = 0.10
MAX_TOTAL_EXPOSURE = 0.80
INTRADAY_REDUCE_RATIO = 1.0 / 3.0
ENTRY_MAX_DISTANCE_MA40 = 0.15
ENTRY_MAX_DISTANCE_MA7 = 0.04
ENTRY_MAX_MA7_MA13_GAP = 0.035
ENTRY_ABSOLUTE_MAX_MA7_MA13_GAP = 0.035
ENTRY_MAX_GAP_RATIO = 1.25
ENTRY_MAX_EXECUTION_GAP = 0.03
ENTRY_MIN_MA7_SLOPE_3D = 0.003
ENTRY_MIN_MA13_SLOPE_3D = 0.0015
ADDBACK_WINDOW_DAYS = 3
ADDBACK_FIRST_RATIO = 0.5
ADDBACK_SUPPORT_TOLERANCE = 0.02
ADDBACK_MIN_MA7_SLOPE_3D = 0.001
ADDBACK_MIN_MA13_SLOPE_3D = 0.0005
ADDBACK_MIN_DISTANCE_MA7 = 0.05
ADDBACK_MIN_DISTANCE_MA13 = 0.08
STARTER_POSITION_SCALE = 0.5
STARTER_MAX_MA7_MA13_GAP = 0.02
STARTER_MAX_DISTANCE_MA40 = 0.15
STARTER_MAX_DISTANCE_MA7 = 0.08
STARTER_SUPPORT_TOLERANCE = 0.035
STARTER_MIN_MA13_SLOPE_3D = -0.008
TREND_ADD_WINDOW_DAYS = 15
TREND_ADD_SUPPORT_TOLERANCE = 0.02
INTRADAY_STAND_TOLERANCE = 0.005
MA7_ADD_MIN_PULLBACK = 0.06
MA7_ADD_MAX_ROLLOVER = 0.001
MA7_ADD_MIN_GAP_RATIO = 0.50
MA7_ADD_MAX_GAP_RATIO = 1.25
MA7_ADD_MAX_DISTANCE_MA40 = 0.18
BASE_RECLAIM_SUPPORT_TOLERANCE = 0.04
BASE_RECLAIM_MAX_DISTANCE_MA40 = 0.15
BASE_RECLAIM_RESUME_DAYS = 3
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


def sector_rotation_exposure_map(scores, sectors_by_style,
                                 max_total=MAX_TOTAL_EXPOSURE):
    budgets = {}
    for code, sector_items in (sectors_by_style or {}).items():
        score = float((scores or {}).get(code, 0.0))
        if score < STYLE_WATCH_SCORE:
            continue
        sector_scores = [
            float(item.get("score", 0.0))
            for item in (sector_items or [])
        ]
        count = min(MAX_SECTORS_PER_STYLE, len(sector_scores))
        if count <= 0:
            continue
        average_score = sum(sector_scores[:count]) / float(count)
        if score >= STYLE_STRONG_SCORE:
            exposure = 0.20 + 0.10 * count
            if count >= 2 and average_score >= 70.0:
                exposure += 0.10
            exposure = min(0.60, exposure)
        else:
            exposure = min(0.40, 0.10 + 0.10 * count)
        budgets[code] = round(exposure, 10)
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


def entry_setup_kind(metrics):
    close = float(metrics["close"])
    low = float(metrics["low"])
    previous_high = float(metrics["previous_high"])
    ma7 = float(metrics["ma7"])
    ma13 = float(metrics["ma13"])
    ma40 = float(metrics["ma40"])
    ma13_prev = float(metrics["ma13_prev"])
    ma40_prev = float(metrics["ma40_prev"])
    slope7 = float(metrics["ma7_slope3"])
    slope13 = float(metrics["ma13_slope3"])
    distance40 = float(metrics["distance_ma40"])
    distance7 = close / ma7 - 1.0 if ma7 > 0.0 else float("inf")
    gap7 = float(metrics["ma7_ma13_gap"])
    gap13 = float(metrics["ma13_ma40_gap"])
    ma7_prev1 = float(metrics.get("ma7_prev1", ma7 - 1e-12))
    ma7_prev2 = float(metrics.get("ma7_prev2", ma7_prev1 - 1e-12))
    trend_entry = bool(
        close > ma7 > ma13 > ma40
        and ma13 > ma13_prev and ma40 > ma40_prev
        and ma7 > ma7_prev1 >= ma7_prev2
        and slope7 >= ENTRY_MIN_MA7_SLOPE_3D
        and slope13 >= ENTRY_MIN_MA13_SLOPE_3D
        and distance7 <= ENTRY_MAX_DISTANCE_MA7
        and distance40 <= ENTRY_MAX_DISTANCE_MA40
        and gap7 <= ENTRY_ABSOLUTE_MAX_MA7_MA13_GAP
        and gap7 <= max(
            ENTRY_MAX_MA7_MA13_GAP,
            ENTRY_MAX_GAP_RATIO * gap13
        )
    )
    if trend_entry:
        return "trend"
    ma40_starter = bool(
        close > ma13 > ma40
        and ma40 > ma40_prev
        and slope13 >= STARTER_MIN_MA13_SLOPE_3D
        and ma7 >= ma13 * (1.0 - STARTER_MAX_MA7_MA13_GAP)
        and slope7 >= -0.02
        and abs(low / ma40 - 1.0) <= STARTER_SUPPORT_TOLERANCE
        and close > previous_high
        and distance7 <= STARTER_MAX_DISTANCE_MA7
        and distance40 <= STARTER_MAX_DISTANCE_MA40
    )
    if ma40_starter:
        return "ma40_starter"
    base_reclaim = bool(
        close > ma7 > ma13 > ma40
        and ma40 > ma40_prev
        and slope7 >= ENTRY_MIN_MA7_SLOPE_3D
        and STARTER_MIN_MA13_SLOPE_3D <= slope13 < ENTRY_MIN_MA13_SLOPE_3D
        and min(abs(low / ma7 - 1.0), abs(low / ma13 - 1.0))
        <= BASE_RECLAIM_SUPPORT_TOLERANCE
        and close > previous_high
        and distance7 <= STARTER_MAX_DISTANCE_MA7
        and distance40 <= BASE_RECLAIM_MAX_DISTANCE_MA40
        and gap7 <= max(
            ENTRY_MAX_MA7_MA13_GAP,
            ENTRY_MAX_GAP_RATIO * gap13,
        )
    )
    return "base_reclaim" if base_reclaim else None


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
    ma7_prev1 = float(np.mean(close[-8:-1]))
    ma7_prev2 = float(np.mean(close[-9:-2]))
    ma13 = float(np.mean(close[-13:]))
    ma40 = float(np.mean(close[-40:]))
    ma7_prev3 = float(np.mean(close[-10:-3]))
    ma13_prev3 = float(np.mean(close[-16:-3]))
    ma13_prev = float(np.mean(close[-18:-5]))
    ma40_prev = float(np.mean(close[-45:-5]))
    average_amount = float(np.mean(amount[-20:]))
    r5 = _return(close, 5)
    r13 = _return(close, 13)
    r40 = _return(close, 40)
    distance_ma13 = close[-1] / ma13 - 1.0
    distance_ma7 = close[-1] / ma7 - 1.0
    distance_ma40 = close[-1] / ma40 - 1.0
    ma7_ma13_gap = ma7 / ma13 - 1.0
    ma13_ma40_gap = ma13 / ma40 - 1.0
    ma7_slope3 = ma7 / ma7_prev3 - 1.0
    ma13_slope3 = ma13 / ma13_prev3 - 1.0
    latest_low = float(data["low"].iloc[-1])
    previous_high = float(data["high"].iloc[-2])
    high40 = float(np.max(np.asarray(data["high"], dtype=float)[-40:]))
    recent_peak_price = float(
        np.max(np.asarray(data["high"], dtype=float)[-10:])
    )
    high_proximity = close[-1] / high40 if high40 > 0 else 0.0
    atr = _atr(data, 14)

    entry_setup = entry_setup_kind({
        "close": close[-1], "low": latest_low,
        "previous_high": previous_high,
        "ma7": ma7, "ma7_prev1": ma7_prev1,
        "ma7_prev2": ma7_prev2,
        "ma13": ma13, "ma40": ma40,
        "ma13_prev": ma13_prev, "ma40_prev": ma40_prev,
        "ma7_slope3": ma7_slope3, "ma13_slope3": ma13_slope3,
        "distance_ma40": distance_ma40,
        "ma7_ma13_gap": ma7_ma13_gap,
        "ma13_ma40_gap": ma13_ma40_gap,
    })
    if entry_setup is None:
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
        "ma7_prev1": ma7_prev1,
        "ma7_prev2": ma7_prev2,
        "ma13": ma13,
        "ma40": ma40,
        "r13": r13,
        "r40": r40,
        "rs13": rs13,
        "rs40": rs40,
        "distance_ma13": distance_ma13,
        "distance_ma7": distance_ma7,
        "distance_ma40": distance_ma40,
        "ma7_ma13_gap": ma7_ma13_gap,
        "ma13_ma40_gap": ma13_ma40_gap,
        "ma7_slope3": ma7_slope3,
        "ma13_slope3": ma13_slope3,
        "entry_setup": entry_setup,
        "high_proximity": high_proximity,
        "recent_peak_price": recent_peak_price,
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
    ma7 = float(np.mean(close[-7:]))
    ma7_prev1 = float(np.mean(close[-8:-1]))
    ma13 = float(np.mean(close[-13:]))
    ma40 = float(np.mean(close[-40:]))
    ma7_prev3 = float(np.mean(close[-10:-3]))
    ma13_prev3 = float(np.mean(close[-16:-3]))
    ma40_prev5 = float(np.mean(close[-45:-5]))
    recent = data.iloc[-10:]
    recent_high = np.asarray(recent["high"], dtype=float)
    recent_low = np.asarray(recent["low"], dtype=float)
    peak_index = int(np.argmax(recent_high))
    peak_price = float(recent_high[peak_index])
    post_peak_low = float(np.min(recent_low[peak_index:]))
    recent_pullback = (
        1.0 - post_peak_low / peak_price
        if peak_price > 0.0 and post_peak_low > 0.0 else 0.0
    )
    return {
        "close": float(close[-1]),
        "high": float(data["high"].iloc[-1]),
        "low": float(data["low"].iloc[-1]),
        "previous_high": float(data["high"].iloc[-2]),
        "ma7": ma7,
        "ma7_prev1": ma7_prev1,
        "ma13": ma13,
        "ma40": ma40,
        "ma7_ma13_gap": ma7 / ma13 - 1.0,
        "ma13_ma40_gap": ma13 / ma40 - 1.0,
        "ma7_slope3": ma7 / ma7_prev3 - 1.0,
        "ma13_slope3": ma13 / ma13_prev3 - 1.0,
        "ma40_slope5": ma40 / ma40_prev5 - 1.0,
        "recent_peak_price": peak_price,
        "recent_pullback": recent_pullback,
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


def entry_structure_score(feature):
    distance_ma40 = max(0.0, float(feature.get("distance_ma40", 0.0)))
    distance_ma13 = max(0.0, float(feature.get("distance_ma13", 0.0)))
    gap7 = max(0.0, float(feature.get("ma7_ma13_gap", 0.0)))
    gap13 = max(0.0, float(feature.get("ma13_ma40_gap", 0.0)))
    slope7 = max(0.0, float(feature.get("ma7_slope3", 0.0)))
    slope13 = max(0.0, float(feature.get("ma13_slope3", 0.0)))
    distance_score = 1.0 - min(
        1.0, 0.65 * distance_ma40 / ENTRY_MAX_DISTANCE_MA40
        + 0.35 * distance_ma13 / 0.12,
    )
    gap_excess = max(0.0, gap7 - gap13)
    gap_score = 1.0 - min(1.0, gap_excess / max(gap13, 0.02))
    slope_score = min(1.0, 0.5 * slope7 / 0.018 + 0.5 * slope13 / 0.012)
    return round(
        0.40 * distance_score + 0.30 * gap_score + 0.30 * slope_score,
        6,
    )


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
        structure = entry_structure_score(item["feature"])
        score = (
            25.0 * rank_fields["rs13"][code]
            + 20.0 * rank_fields["rs40"][code]
            + 10.0 * rank_fields["r13"][code]
            + 5.0 * rank_fields["high_proximity"][code]
            + 10.0 * rank_fields["average_amount"][code]
            + 5.0 * volatility_rank[code]
            + 25.0 * structure
        )
        result = dict(item)
        result["score"] = round(score, 4)
        result["entry_structure_score"] = structure
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


def addback_trend_ready(metrics, peak_price=None):
    if not metrics:
        return False
    ma7 = float(metrics.get("ma7", 0.0))
    ma13 = float(metrics.get("ma13", 0.0))
    ma40 = float(metrics.get("ma40", 0.0))
    if not (ma7 > ma13 > ma40 > 0.0):
        return False
    if float(metrics.get("ma7_slope3", 0.0)) < ADDBACK_MIN_MA7_SLOPE_3D:
        return False
    if float(metrics.get("ma13_slope3", 0.0)) < ADDBACK_MIN_MA13_SLOPE_3D:
        return False
    if peak_price is None:
        return True
    price = float(peak_price)
    return (
        price / ma7 - 1.0 >= ADDBACK_MIN_DISTANCE_MA7
        and price / ma13 - 1.0 >= ADDBACK_MIN_DISTANCE_MA13
    )


def ma7_pullback_add_ready(metrics, peak_price=None, pullback_low=None):
    if not metrics:
        return False
    ma7 = float(metrics.get("ma7", 0.0))
    ma7_prev1 = float(metrics.get("ma7_prev1", 0.0))
    ma13 = float(metrics.get("ma13", 0.0))
    ma40 = float(metrics.get("ma40", 0.0))
    if not (ma7 > ma13 > ma40 > 0.0) or ma7_prev1 <= 0.0:
        return False
    if ma7 < ma7_prev1 * (1.0 - MA7_ADD_MAX_ROLLOVER):
        return False
    gap7 = ma7 / ma13 - 1.0
    gap13 = ma13 / ma40 - 1.0
    if gap13 <= 0.0:
        return False
    gap_ratio = gap7 / gap13
    if not (MA7_ADD_MIN_GAP_RATIO
            <= gap_ratio <= MA7_ADD_MAX_GAP_RATIO):
        return False
    if ma7 / ma40 - 1.0 > MA7_ADD_MAX_DISTANCE_MA40:
        return False
    if peak_price is not None and pullback_low is not None:
        peak = float(peak_price)
        low = float(pullback_low)
        pullback = 1.0 - low / peak if peak > 0.0 and low > 0.0 else 0.0
    else:
        pullback = float(metrics.get("recent_pullback", 0.0))
    return pullback >= MA7_ADD_MIN_PULLBACK


def trend_add_signal(metrics, age, setup=""):
    if not metrics or int(age) > TREND_ADD_WINDOW_DAYS:
        return None
    ma7 = float(metrics.get("ma7", 0.0))
    ma13 = float(metrics.get("ma13", 0.0))
    ma40 = float(metrics.get("ma40", 0.0))
    if not (ma7 > ma13 > ma40 > 0.0):
        return None
    if float(metrics.get("ma7_slope3", 0.0)) < ENTRY_MIN_MA7_SLOPE_3D:
        return None
    if float(metrics.get("ma13_slope3", 0.0)) < ENTRY_MIN_MA13_SLOPE_3D:
        return None
    low = float(metrics.get("low", 0.0))
    close = float(metrics.get("close", 0.0))
    previous_high = float(metrics.get("previous_high", 0.0))
    if not (low > 0.0 and close > previous_high > 0.0):
        return None
    distance7 = abs(low / ma7 - 1.0)
    distance13 = abs(low / ma13 - 1.0)
    if distance13 <= TREND_ADD_SUPPORT_TOLERANCE:
        return "ma13"
    if (distance7 <= TREND_ADD_SUPPORT_TOLERANCE
            and ma7_pullback_add_ready(metrics)):
        return "ma7"
    if (str(setup) == "base_reclaim"
            and int(age) <= BASE_RECLAIM_RESUME_DAYS
            and close > ma7):
        return "resume"
    return None


def trend_add_ready(metrics, age, setup=""):
    return trend_add_signal(metrics, age, setup) is not None


def intraday_build_add_signal(frame30, daily_metrics, age, setup=""):
    """Use complete 30m bars to confirm support defined by daily MA values."""
    if not daily_metrics or int(age) > TREND_ADD_WINDOW_DAYS:
        return None
    if frame30 is None or len(frame30) < 2:
        return None
    data = frame30.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["open", "high", "low", "close", "volume"]
    )
    if len(data) < 2:
        return None
    previous = data.iloc[-2]
    latest = data.iloc[-1]
    previous_time = pd.Timestamp(data.index[-2])
    latest_time = pd.Timestamp(data.index[-1])
    if previous_time.date() != latest_time.date():
        return None

    ma7 = float(daily_metrics.get("ma7", 0.0))
    ma13 = float(daily_metrics.get("ma13", 0.0))
    ma40 = float(daily_metrics.get("ma40", 0.0))
    if not (ma7 > ma13 > ma40 > 0.0):
        return None
    if float(daily_metrics.get("ma7_slope3", 0.0)) < ENTRY_MIN_MA7_SLOPE_3D:
        return None
    if float(daily_metrics.get("ma13_slope3", 0.0)) < ENTRY_MIN_MA13_SLOPE_3D:
        return None

    support_low = min(float(previous["low"]), float(latest["low"]))

    def stands_on(support):
        return bool(
            float(previous["close"]) >= support
            and float(latest["close"]) >= support
            and float(latest["low"])
            >= support * (1.0 - INTRADAY_STAND_TOLERANCE)
            and float(latest["close"]) >= float(previous["close"])
        )

    if (abs(support_low / ma13 - 1.0) <= TREND_ADD_SUPPORT_TOLERANCE
            and stands_on(ma13)):
        return "ma13"
    if (abs(support_low / ma7 - 1.0) <= TREND_ADD_SUPPORT_TOLERANCE
            and stands_on(ma7)
            and ma7_pullback_add_ready(
                daily_metrics,
                daily_metrics.get("recent_peak_price"), support_low,
            )):
        return "ma7"
    return None


def first_hour_daily_support_confirmed(frame30, trade_date, support):
    """Return None before 10:30, otherwise confirm two bars over a daily MA."""
    if frame30 is None or frame30.empty or float(support) <= 0.0:
        return None
    data = frame30.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["open", "high", "low", "close", "volume"]
    )
    if data.empty:
        return None
    index = _datetime_index(data.index)
    day = pd.to_datetime(str(trade_date), format="%Y%m%d", errors="coerce")
    if pd.isna(day):
        return None
    same_day = data[index.normalize() == day.normalize()].copy()
    same_day.index = index[index.normalize() == day.normalize()]
    first_hour = same_day[
        same_day.index.strftime("%H%M").isin(["1000", "1030"])
    ]
    if len(first_hour) < 2 or first_hour.index[-1].strftime("%H%M") < "1030":
        return None
    first = first_hour.iloc[-2]
    second = first_hour.iloc[-1]
    return bool(
        float(first["close"]) >= float(support)
        and float(second["close"]) >= float(support)
        and float(second["low"])
        >= float(support) * (1.0 - INTRADAY_STAND_TOLERANCE)
        and float(second["close"]) >= float(first["close"])
    )


def build_add_rollback_volume(position_volume, available_volume, plan):
    current = max(0, int(position_volume))
    available = max(0, int(available_volume))
    added = max(0, int((plan or {}).get("added_volume", 0)))
    base = max(0, int((plan or {}).get(
        "base_volume", max(0, current - added)
    )))
    excess = max(0, current - base)
    return int(min(available, added, excess) / 100.0) * 100


def _confirmed_30m_reversal(previous, latest):
    return (
        float(latest["low"]) >= float(previous["low"])
        and float(latest["close"]) > float(previous["high"])
    )


def intraday_action(frame30, ma7, ma13, reduced, trend_ready=True,
                    addback_stage=0, addback_age=0,
                    ma7_add_ready=False):
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
        if not trend_ready or int(addback_age) > ADDBACK_WINDOW_DAYS:
            return None
        if not _confirmed_30m_reversal(previous, latest):
            return None
        near_ma7 = (
            float(ma7) > 0.0
            and abs(float(previous["low"]) / float(ma7) - 1.0)
            <= ADDBACK_SUPPORT_TOLERANCE
        )
        near_ma13 = (
            float(ma13) > 0.0
            and abs(float(previous["low"]) / float(ma13) - 1.0)
            <= ADDBACK_SUPPORT_TOLERANCE
        )
        if near_ma13:
            return "add_ma13"
        if int(addback_stage) <= 0 and near_ma7 and ma7_add_ready:
            return "add_ma7"
        if (int(addback_stage) == 1
                and float(latest["close"]) > float(ma7)):
            return "add_resume"
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
        score_stock_candidates(candidates),
        STOCK_CANDIDATE_POOL_PER_STYLE, MAX_PER_SECTOR
    )
    raw_history = fetch_history(
        context, ["close"], [item["code"] for item in selected],
        "1d", 1, asof, "none",
    )
    for item in selected:
        raw_frame = raw_history.get(item["code"])
        raw_close = 0.0
        if raw_frame is not None and "close" in raw_frame.columns:
            values = _clean_array(raw_frame["close"])
            if len(values) > 0 and values[-1] > 0.0:
                raw_close = float(values[-1])
        item["feature"]["raw_signal_close"] = raw_close
        item["name"] = _instrument_name(context, item["code"])
        if not A.price_coordinate_probe_logged and raw_close > 0.0:
            adjusted_close = float(item["feature"].get("close", 0.0))
            if adjusted_close > 0.0:
                print(
                    "PRICE_COORD", asof, item["code"],
                    "adjusted_close", round(adjusted_close, 6),
                    "raw_close", round(raw_close, 6),
                    "raw_per_adjusted", round(
                        raw_close / adjusted_close, 10
                    ),
                )
                A.price_coordinate_probe_logged = True
    return selected


def _virtual_backtest_snapshot():
    try:
        accounts = get_trade_detail_data(
            A.acct, A.acct_type, "account"
        ) or []
        positions = get_trade_detail_data(
            A.acct, A.acct_type, "position"
        ) or []
    except Exception as error:
        print("WARN virtual backtest account query failed:", error)
        return None
    if not accounts:
        return None

    account_data = accounts[0]
    position_map = {}
    for position in positions:
        volume = int(getattr(position, "m_nVolume", 0))
        if volume <= 0:
            continue
        code = (str(position.m_strInstrumentID) + "."
                + str(position.m_strExchangeID))
        available = int(getattr(position, "m_nCanUseVolume", 0))
        position_map[code] = {
            "volume": volume,
            "available": max(0, min(volume, available)),
            "open_price": float(getattr(position, "m_dOpenPrice", 0.0)),
            "current_price": float(getattr(position, "m_dLastPrice", 0.0)),
        }
    snapshot = {
        "balance": float(account_data.m_dBalance),
        "available_cash": max(0.0, float(account_data.m_dAvailable)),
        "positions": position_map,
    }
    return snapshot


def _record_code(record):
    return str(record.stockcode) + "." + str(record.market)


def _record_trade_day(value):
    text = str(value or "").strip()
    if text.endswith(".0"):
        text = text[:-2]
    digits = "".join(character for character in text
                     if character.isdigit())
    if len(digits) >= 14:
        return digits[:8]
    if len(digits) == 8:
        return digits
    if len(digits) == 13:
        try:
            formatted = timetag_to_datetime(int(digits), "%Y%m%d")
            result = "".join(character for character in str(formatted)
                             if character.isdigit())
            if len(result) >= 8:
                return result[:8]
        except Exception:
            pass
    return ""


def _record_value(record, names, default=None):
    for name in names:
        if hasattr(record, name):
            value = getattr(record, name)
            if value is not None:
                return value
    return default


def _record_trade_clock(record):
    value = _record_value(
        record,
        ("trade_time", "deal_time", "m_strTradeTime", "trade_date"),
        "",
    )
    digits = "".join(character for character in str(value or "")
                     if character.isdigit())
    if len(digits) >= 14:
        return digits[8:14]
    if 6 <= len(digits) < 8:
        return digits[-6:]
    return "000000"


def _log_backtest_deals(context):
    try:
        records = get_result_records(
            "dealdetails", context.barpos, context
        ) or []
    except Exception:
        return
    occurrences = {}
    logged_keys = getattr(A, "logged_deal_keys", set())
    for record in records:
        trade_day = _record_trade_day(_record_value(
            record, ("trade_date", "m_strTradeDate", "trade_time"), ""
        ))
        if not trade_day:
            continue
        try:
            code = _record_code(record)
            side = (
                "buy"
                if int(_record_value(record, ("open_close",), -1)) == 1
                else "sell"
            )
            volume = int(_record_value(
                record, ("position", "volume", "trade_volume"), 0
            ))
            price = round(float(_record_value(
                record, ("trade_price", "price"), 0.0
            )), 4)
        except Exception:
            continue
        if volume <= 0 or price <= 0.0:
            continue
        clock = _record_trade_clock(record)
        base_key = (trade_day, clock, side, code, volume, price)
        occurrence = occurrences.get(base_key, 0)
        occurrences[base_key] = occurrence + 1
        key = base_key + (occurrence,)
        if key in logged_keys:
            continue
        logged_keys.add(key)
        print(
            "DEAL", trade_day, clock, side, code, volume,
            "price", price,
        )
    A.logged_deal_keys = logged_keys


def _backtest_trade_day(context):
    try:
        value = context.get_bar_timetag(context.barpos)
    except Exception:
        return ""
    return _record_trade_day(value)


def _backtest_order_price(context, code):
    try:
        price_map = context.get_history_data(1, "5m", "open", 3) or {}
        values = price_map.get(code, [])
        if len(values) > 0:
            price = float(values[-1])
            if np.isfinite(price) and price > 0.0:
                return price
    except Exception as error:
        print("WARNING backtest fixed price unavailable:", code, error)
    return None


def _portfolio_log_due(context):
    trade_day = _backtest_trade_day(context) or "UNKNOWN"
    if getattr(A, "last_portfolio_log_date", "") == trade_day:
        return False
    A.last_portfolio_log_date = trade_day
    return True


def _backtest_snapshot(context):
    _log_backtest_deals(context)
    virtual_snapshot = _virtual_backtest_snapshot()
    if virtual_snapshot is not None:
        if _portfolio_log_due(context):
            capital, _ = _backtest_capital(context)
            print(
                "PORTFOLIO", "source", "virtual_account",
                "capital", capital,
                "balance", virtual_snapshot["balance"],
                "cash", virtual_snapshot["available_cash"],
                "positions", len(virtual_snapshot["positions"]),
            )
        return virtual_snapshot
    try:
        holdings = get_result_records("holdings", context.barpos, context) or []
        dealdetails = get_result_records(
            "dealdetails", context.barpos, context
        ) or []
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
    same_day_buys = {}
    current_trade_day = _backtest_trade_day(context)
    for deal in dealdetails:
        if int(getattr(deal, "open_close", -1)) != 1:
            continue
        deal_trade_day = _record_trade_day(
            getattr(deal, "trade_date", "")
        )
        if (current_trade_day and deal_trade_day
                and deal_trade_day != current_trade_day):
            continue
        code = _record_code(deal)
        volume = max(0, int(getattr(deal, "position", 0)))
        same_day_buys[code] = same_day_buys.get(code, 0) + volume
    for holding in holdings:
        volume = int(getattr(holding, "position", 0))
        if volume <= 0:
            continue
        code = _record_code(holding)
        current_price = float(getattr(holding, "current_price", 0.0))
        open_price = float(getattr(holding, "trade_price", current_price))
        market_value += current_price * volume
        position_map[code] = {
            "volume": volume,
            "available": max(0, volume - same_day_buys.get(code, 0)),
            "open_price": open_price,
            "current_price": current_price,
        }
    available_cash = max(0.0, balance - market_value)
    if _portfolio_log_due(context):
        print(
            "PORTFOLIO", "source", "result_records",
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


def _order_time(context):
    try:
        timetag = context.get_bar_timetag(context.barpos)
        order_text = timetag_to_datetime(timetag, "%Y%m%d%H%M%S")
        order_digits = "".join(
            character for character in str(order_text)
            if character.isdigit()
        )
        if len(order_digits) >= 14:
            return order_digits[8:14]
    except Exception:
        pass
    return datetime.datetime.now().strftime("%H%M%S")


def _send_order(context, side, code, volume, trade_date, reason, price=None):
    volume = int(volume)
    if volume <= 0:
        return False
    order_time = _order_time(context)
    key = (str(trade_date), order_time, str(code), str(side))
    if key in A.sent_order_keys:
        return False
    remark = str(trade_date) + "_" + side + "_" + str(reason)
    logged_price = price
    try:
        if A.mode == "BACKTEST":
            signed_volume = volume if side == "buy" else -volume
            try:
                fixed_price = float(price)
            except (TypeError, ValueError):
                fixed_price = float("nan")
            if not np.isfinite(fixed_price) or fixed_price <= 0.0:
                fixed_price = _backtest_order_price(context, code)
            if fixed_price is None:
                print("ERROR backtest order skipped, invalid price:", code)
                return False
            logged_price = fixed_price
            order_shares(code, signed_volume, "fix", fixed_price,
                         context, context.accountID)
        else:
            operation = A.buy_code if side == "buy" else A.sell_code
            passorder(
                operation, 1101, A.acct, code, 14, -1, volume,
                STRATEGY_NAME, 1, remark, context
            )
    except Exception as error:
        print("ERROR order failed:", side, code, volume, error)
        return False
    A.sent_order_keys.add(key)
    if side == "buy":
        A.owned_codes.add(code)
    try:
        logged_price = round(float(logged_price), 4)
    except (TypeError, ValueError):
        logged_price = -1
    print(
        "ORDER_SUBMITTED", trade_date, order_time, side, code, volume,
        "price", logged_price, reason,
    )
    return True


def _simulation_tick(context, codes):
    if A.mode == "BACKTEST" or not codes:
        return {}
    try:
        return context.get_full_tick(list(codes)) or {}
    except Exception as error:
        print("WARN tick query failed:", error)
        return {}


def _raw_execution_prices(context, codes, field="open"):
    try:
        timetag = context.get_bar_timetag(context.barpos)
        text = timetag_to_datetime(timetag, "%Y%m%d%H%M%S")
        digits = "".join(character for character in str(text)
                         if character.isdigit())
        end_time = digits[:14]
    except Exception as error:
        print("ERROR raw execution time unavailable:", error)
        return {}
    history = fetch_history(
        context, ["open", "close"], sorted(set(codes or [])),
        "5m", 1, end_time, "none", 100,
    )
    result = {}
    for code, frame in history.items():
        if frame is None or len(frame) == 0 or field not in frame.columns:
            continue
        try:
            price = float(frame[field].iloc[-1])
        except (TypeError, ValueError, IndexError):
            continue
        if np.isfinite(price) and price > 0.0:
            result[code] = price
    return result


def _execution_price(code, candidate_map, tick_map, side,
                     execution_prices=None):
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
    raw_price = float((execution_prices or {}).get(code, 0.0))
    if raw_price > 0.0:
        return raw_price
    if A.mode == "BACKTEST":
        return 0.0
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


def entry_raw_price_levels(candidate):
    feature = (candidate or {}).get("feature", {})
    ma7 = float(feature.get("ma7", 0.0))
    signal_close = float(feature.get("close", 0.0))
    ma40 = float(feature.get("ma40", 0.0))
    raw_signal_close = float(feature.get("raw_signal_close", 0.0))
    if (ma7 <= 0.0 or signal_close <= 0.0 or ma40 <= 0.0
            or raw_signal_close <= 0.0):
        return None
    raw_per_adjusted = raw_signal_close / signal_close
    if not np.isfinite(raw_per_adjusted) or raw_per_adjusted <= 0.0:
        return None
    return {
        "ma7": ma7 * raw_per_adjusted,
        "ma40": ma40 * raw_per_adjusted,
        "signal_close": raw_signal_close,
        "raw_per_adjusted": raw_per_adjusted,
    }


def buy_entry_price_allowed(price, candidate):
    levels = entry_raw_price_levels(candidate)
    feature = (candidate or {}).get("feature", {})
    setup = str(feature.get("entry_setup", ""))
    if price <= 0.0 or levels is None:
        return False
    max_distance = (
        STARTER_MAX_DISTANCE_MA7
        if setup in ("ma40_starter", "base_reclaim")
        else ENTRY_MAX_DISTANCE_MA7
    )
    return bool(
        price <= levels["ma7"] * (1.0 + max_distance)
        and price <= levels["ma40"] * (1.0 + ENTRY_MAX_DISTANCE_MA40)
        and price <= levels["signal_close"] * (1.0 + ENTRY_MAX_EXECUTION_GAP)
    )


def _desired_share_map(snapshot, style_exposures, candidates, tick_map,
                       execution_prices=None):
    desired = {}
    if not candidates or not style_exposures:
        return desired
    candidate_map = {item["code"]: item for item in candidates}
    selected = []
    style_counts = {}
    ordered = sorted(
        candidates, key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    for item in ordered:
        code = item["code"]
        if code in getattr(A, "blocked_codes", set()):
            continue
        style = item.get("style")
        style_exposure = float(style_exposures.get(style, 0.0))
        if style_exposure <= 0.0:
            continue
        if style_counts.get(style, 0) >= MAX_STOCKS_PER_STYLE:
            continue
        price = _execution_price(
            code, candidate_map, tick_map, "buy", execution_prices
        )
        if target_shares(
                snapshot["balance"], style_exposure, 1,
                price, MAX_STOCK_WEIGHT) < 100:
            continue
        selected.append(item)
        style_counts[style] = style_counts.get(style, 0) + 1
    for item in selected:
        code = item["code"]
        style = item.get("style")
        style_exposure = float(style_exposures.get(style, 0.0))
        style_count = int(style_counts.get(style, 0))
        if style_exposure <= 0.0 or style_count <= 0:
            continue
        price = _execution_price(
            code, candidate_map, tick_map, "buy", execution_prices
        )
        shares = target_shares(
            snapshot["balance"], style_exposure, style_count,
            price, MAX_STOCK_WEIGHT
        )
        scale = (
            float(getattr(A, "intraday_scales", {}).get(code, 1.0))
            * float(getattr(A, "entry_scales", {}).get(code, 1.0))
        )
        sized = int(shares * scale / 100.0) * 100
        if sized > 0:
            desired[code] = sized
    return desired


def allocation_metrics(total_asset, style_exposures, desired_shares,
                       candidates, execution_prices=None):
    total = float(total_asset)
    planned = sum(float(value) for value in (style_exposures or {}).values())
    prices = dict(execution_prices or {}) or {
        item["code"]: float(item.get("feature", {}).get("close", 0.0))
        for item in candidates or []
    }
    target_value = sum(
        int(shares) * prices.get(code, 0.0)
        for code, shares in (desired_shares or {}).items()
    )
    target_exposure = target_value / total if total > 0.0 else 0.0
    fill_rate = target_exposure / planned if planned > 0.0 else 1.0
    return {
        "planned_exposure": round(planned, 6),
        "target_exposure": round(target_exposure, 6),
        "fill_rate": round(fill_rate, 6),
        "unallocated_cash": round(max(0.0, total * planned - target_value), 2),
    }


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
        price = float(A.execution_prices.get(code, 0.0))
        if _send_order(context, "sell", code, volume, trade_date,
                       "rebalance", price):
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
        price = _execution_price(
            code, candidate_map, tick_map, "buy", A.execution_prices
        )
        if price <= 0 or not _buy_is_tradeable(code, tick_map.get(code, {})):
            retry = True
            continue
        candidate = candidate_map.get(code)
        if current <= 0 and not buy_entry_price_allowed(price, candidate):
            raw_levels = entry_raw_price_levels(candidate) or {}
            A.desired_shares[code] = 0
            A.blocked_codes.add(code)
            print(
                "SKIP_BUY", trade_date, code, "entry_price_too_far",
                "price", round(price, 4),
                "raw_ma7", round(float(raw_levels.get("ma7", 0.0)), 4),
                "raw_ma40", round(float(raw_levels.get("ma40", 0.0)), 4),
                "raw_signal_close", round(float(raw_levels.get(
                    "signal_close", 0.0
                )), 4),
            )
            continue
        affordable = int(cash * 0.98 / price / 100) * 100
        order_volume = min(volume, affordable)
        if order_volume <= 0:
            retry = True
            continue
        add_signal = A.trend_add_reasons.get(code)
        order_reason = (
            "trend_add_" + str(add_signal)
            if add_signal else "rebalance"
        )
        if _send_order(
                context, "buy", code, order_volume, trade_date,
                order_reason, price):
            sent_any = True
            retry = True
            cash -= order_volume * price
            A.trend_add_reasons.pop(code, None)
            if (current <= 0
                    and float(A.entry_scales.get(code, 1.0)) < 0.999):
                A.build_plans[code] = {
                    "start_date": str(trade_date),
                    "last_age_date": str(trade_date),
                    "age": 0,
                    "setup": candidate_map.get(code, {}).get(
                        "feature", {}
                    ).get("entry_setup", ""),
                }
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
        A.daily_position_metrics = {}
        A.addback_plans = {}
        A.build_plans = {}
        A.build_confirm_plans = {}
        A.trend_add_reasons = {}
        return False
    if not style_exposures:
        sent = False
        for code, position in positions.items():
            A.desired_shares[code] = 0
            if _send_order(
                    context, "sell", code, position["available"],
                    trade_date, "style_risk",
                    A.execution_prices.get(code)):
                sent = True
        A.addback_plans = {}
        A.build_plans = {}
        A.build_confirm_plans = {}
        A.entry_scales = {}
        A.trend_add_reasons = {}
        return sent

    history = fetch_history(
        context, ["close", "high", "low"], list(positions.keys()),
        "1d", 55, asof, "back_ratio"
    )
    sent = False
    active_codes = set()
    A.daily_position_metrics = {}
    for code, position in positions.items():
        active_codes.add(code)
        metrics = position_metrics(history.get(code))
        if metrics is None:
            continue
        A.daily_position_metrics[code] = metrics
        plan = A.addback_plans.get(code)
        if plan and int(plan.get("age", 0)) > ADDBACK_WINDOW_DAYS:
            planned_added = int(plan.get("added_volume", 0))
            added_volume = min(
                int(position.get("available", 0)),
                planned_added,
            )
            if planned_added <= 0:
                A.addback_plans.pop(code, None)
            elif added_volume > 0 and metrics["close"] >= metrics["ma7"]:
                current = int(position.get("volume", 0))
                original = max(int(plan.get("original_volume", current)), 1)
                if _send_order(
                        context, "sell", code, added_volume, trade_date,
                        "addback_timeout", A.execution_prices.get(code)):
                    sent = True
                    A.desired_shares[code] = max(0, current - added_volume)
                    A.intraday_scales[code] = max(
                        0.0, float(current - added_volume) / original
                    )
                    A.addback_plans.pop(code, None)
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
        A.addback_plans.pop(code, None)
        A.build_plans.pop(code, None)
        A.build_confirm_plans.pop(code, None)
        A.entry_scales.pop(code, None)
        A.trend_add_reasons.pop(code, None)
        if _send_order(
                context, "sell", code, position["available"],
                trade_date, reason, A.execution_prices.get(code)):
            sent = True
    for code in list(A.position_meta.keys()):
        if code not in active_codes and code not in A.desired_shares:
            del A.position_meta[code]
    for plans in (A.addback_plans, A.build_plans, A.build_confirm_plans):
        for code in list(plans.keys()):
            if code not in active_codes:
                plans.pop(code, None)
    return sent


def _advance_position_plans(trade_date):
    for plans in (A.addback_plans, A.build_plans):
        for plan in plans.values():
            if str(plan.get("last_age_date", "")) == str(trade_date):
                continue
            if str(plan.get("start_date", "")) != str(trade_date):
                plan["age"] = int(plan.get("age", 0)) + 1
            plan["last_age_date"] = str(trade_date)


def _activate_trend_adds(snapshot):
    positions = _managed_positions(snapshot)
    activated = False
    for code in list(A.build_plans.keys()):
        plan = A.build_plans[code]
        if code not in positions:
            A.build_plans.pop(code, None)
            continue
        age = int(plan.get("age", 0))
        if age > TREND_ADD_WINDOW_DAYS:
            A.build_plans.pop(code, None)
            continue
        signal = trend_add_signal(
            A.daily_position_metrics.get(code), age,
            plan.get("setup", ""),
        )
        if signal != "resume":
            continue
        A.entry_scales[code] = 1.0
        A.build_plans.pop(code, None)
        A.trend_add_reasons[code] = signal
        activated = True
    return activated


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
    intraday_codes = (
        set(candidate_map.keys())
        | set(A.build_plans.keys())
        | set(A.build_confirm_plans.keys())
    )
    codes = sorted(set(positions.keys()) & intraday_codes)
    if not codes:
        return
    history = fetch_history(
        context,
        ["open", "high", "low", "close", "volume", "amount"],
        codes, "5m", 150, end_time, "back_ratio", 100,
    )
    tick_map = _simulation_tick(context, codes)
    execution_prices = _raw_execution_prices(context, codes, "close")
    for code in codes:
        candidate = candidate_map.get(code)
        feature = (candidate or {}).get("feature", {})
        bars30 = aggregate_5m_to_30m(history.get(code))
        daily_metrics = A.daily_position_metrics.get(code, feature)

        confirm_plan = A.build_confirm_plans.get(code)
        if (confirm_plan
                and str(confirm_plan.get("add_date", "")) != str(trade_date)):
            support_kind = str(confirm_plan.get("support_kind", ""))
            support = float((daily_metrics or {}).get(support_kind, 0.0))
            prior_close = float((daily_metrics or {}).get("close", 0.0))
            if support > 0.0 and prior_close >= support:
                print(
                    "BUILD_CONFIRMED", trade_date, code,
                    support_kind, round(support, 4), "daily_close",
                )
                A.build_confirm_plans.pop(code, None)
            else:
                confirmed = first_hour_daily_support_confirmed(
                    bars30, trade_date, support
                )
                if confirmed is True:
                    print(
                        "BUILD_CONFIRMED", trade_date, code,
                        support_kind, round(support, 4), "first_hour",
                    )
                    A.build_confirm_plans.pop(code, None)
                elif confirmed is False:
                    current = int(positions[code].get("volume", 0))
                    available = int(positions[code].get("available", 0))
                    volume = build_add_rollback_volume(
                        current, available, confirm_plan
                    )
                    if volume > 0 and _send_order(
                            context, "sell", code, volume, trade_date,
                            "build_add_unconfirmed",
                            execution_prices.get(code)):
                        A.desired_shares[code] = max(0, current - volume)
                        A.entry_scales[code] = STARTER_POSITION_SCALE
                        A.build_confirm_plans.pop(code, None)
                    elif current <= int(confirm_plan.get(
                            "base_volume", current)):
                        A.entry_scales[code] = STARTER_POSITION_SCALE
                        A.build_confirm_plans.pop(code, None)
                    continue
                else:
                    continue

        if candidate is None or not daily_metrics:
            continue
        reduced = float(A.intraday_scales.get(code, 1.0)) < 0.999
        plan = A.addback_plans.get(code)
        build_plan = A.build_plans.get(code)
        previous_low = (
            float(bars30.iloc[-2]["low"])
            if len(bars30) >= 2 else 0.0
        )
        ma7_add_allowed = bool(
            plan and ma7_pullback_add_ready(
                daily_metrics, plan.get("peak_price"), previous_low
            )
        )
        action = intraday_action(
            bars30, daily_metrics["ma7"], daily_metrics["ma13"], reduced,
            addback_trend_ready(daily_metrics),
            int((plan or {}).get("stage", 0)),
            int((plan or {}).get("age", ADDBACK_WINDOW_DAYS + 1)),
            ma7_add_allowed,
        )
        build_signal = None
        if action is None and not reduced and build_plan:
            build_signal = intraday_build_add_signal(
                bars30, daily_metrics,
                int(build_plan.get("age", TREND_ADD_WINDOW_DAYS + 1)),
                build_plan.get("setup", ""),
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
                    "intraday_top", execution_prices.get(code)):
                remaining_ratio = max(0.0, float(current - volume) / current)
                A.intraday_scales[code] = remaining_ratio
                A.desired_shares[code] = current - volume
                peak_price = (
                    float(bars30.iloc[-2]["high"])
                    if len(bars30) >= 2 else execution_prices.get(code)
                )
                if addback_trend_ready(daily_metrics, peak_price):
                    first_volume = max(
                        100,
                        int(
                            volume * ADDBACK_FIRST_RATIO / 100.0
                        ) * 100,
                    )
                    first_volume = min(first_volume, volume)
                    A.addback_plans[code] = {
                        "start_date": str(trade_date),
                        "last_age_date": str(trade_date),
                        "age": 0,
                        "stage": 0,
                        "original_volume": current,
                        "reduced_volume": volume,
                        "first_volume": first_volume,
                        "added_volume": 0,
                        "peak_price": peak_price,
                    }
                else:
                    A.addback_plans.pop(code, None)
        elif action in ("add_ma7", "add_ma13", "add_resume") and plan:
            previous_scale = float(A.intraday_scales.get(code, 1.0))
            A.intraday_scales[code] = 1.0
            base_desired = _desired_share_map(
                snapshot, A.current_style_exposures,
                A.target_candidates, tick_map, execution_prices,
            ).get(code, 0)
            current = int(positions[code].get("volume", 0))
            price = _execution_price(
                code, candidate_map, tick_map, "buy", execution_prices
            )
            missing = int((base_desired - current) / 100.0) * 100
            if int(plan.get("stage", 0)) <= 0:
                planned_volume = int(plan.get("first_volume", 0))
            else:
                planned_volume = (
                    int(plan.get("reduced_volume", 0))
                    - int(plan.get("added_volume", 0))
                )
            volume = min(missing, int(planned_volume / 100.0) * 100)
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
                    "intraday_" + action, price):
                plan["added_volume"] = int(plan.get("added_volume", 0)) + volume
                remaining = (
                    int(plan.get("reduced_volume", 0))
                    - int(plan.get("added_volume", 0))
                )
                restored = current + volume
                A.desired_shares[code] = restored
                if remaining < 100 or restored >= base_desired:
                    A.intraday_scales[code] = 1.0
                    A.addback_plans.pop(code, None)
                else:
                    plan["stage"] = 1
                    A.intraday_scales[code] = max(
                        0.0, float(restored) / max(base_desired, 1)
                    )
            else:
                A.intraday_scales[code] = previous_scale
        elif build_signal in ("ma7", "ma13") and build_plan:
            previous_scale = float(A.entry_scales.get(
                code, STARTER_POSITION_SCALE
            ))
            A.entry_scales[code] = 1.0
            base_desired = _desired_share_map(
                snapshot, A.current_style_exposures,
                A.target_candidates, tick_map, execution_prices,
            ).get(code, 0)
            current = int(positions[code].get("volume", 0))
            missing = int((base_desired - current) / 100.0) * 100
            price = _execution_price(
                code, candidate_map, tick_map, "buy", execution_prices
            )
            affordable = int(
                float(snapshot["available_cash"]) * 0.98
                / max(price, 1e-12) / 100.0
            ) * 100
            if missing <= 0:
                A.build_plans.pop(code, None)
                continue
            if price <= 0.0 or affordable < missing:
                A.entry_scales[code] = previous_scale
                continue
            if _send_order(
                    context, "buy", code, missing, trade_date,
                    "trend_add_" + build_signal, price):
                A.desired_shares[code] = current + missing
                A.build_plans.pop(code, None)
                A.build_confirm_plans[code] = {
                    "add_date": str(trade_date),
                    "base_volume": current,
                    "added_volume": missing,
                    "support_kind": build_signal,
                }
            else:
                A.entry_scales[code] = previous_scale


def run_daily_cycle(context, asof, trade_date):
    market = _market_state(context, asof)
    market_gate_exposures = dict(market["style_exposures"])
    snapshot = _account_snapshot(context)
    if snapshot is None:
        return
    _refresh_owned_codes(snapshot)
    _advance_position_plans(trade_date)

    style_changed = market_gate_exposures != A.last_market_gate_exposures
    rebalance_due = A.rebalance_age >= REBALANCE_EVERY or style_changed
    selected_sectors = []
    style_exposures = dict(A.current_style_exposures)

    if not market_gate_exposures:
        style_exposures = {}
        A.target_candidates = []
        A.desired_shares = {
            code: 0 for code in _managed_positions(snapshot).keys()
        }
    elif rebalance_due:
        members_by_style = _style_members(
            context, market_gate_exposures.keys()
        )
        targets = []
        used_codes = set()
        sectors_by_style = {}
        ordered_styles = sorted(
            market_gate_exposures.keys(),
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
            sectors_by_style[style] = sectors
            selected_sectors.extend(sectors)
            for item in _stock_selection(context, asof, sectors):
                if item["code"] in used_codes:
                    continue
                used_codes.add(item["code"])
                targets.append(item)
        style_exposures = sector_rotation_exposure_map(
            market["details"], sectors_by_style
        )
        targets = [
            item for item in targets
            if item.get("style") in style_exposures
        ]
        used_codes = {item["code"] for item in targets}
        A.target_candidates = targets
        A.blocked_codes = set()
        held_codes = set(_managed_positions(snapshot).keys())
        A.entry_scales = {
            code: scale for code, scale in A.entry_scales.items()
            if code in used_codes or code in held_codes
        }
        for item in A.target_candidates:
            code = item["code"]
            if code in held_codes or code in A.entry_scales:
                continue
            A.entry_scales[code] = (
                STARTER_POSITION_SCALE
                if item.get("feature", {}).get("entry_setup")
                in ("ma40_starter", "base_reclaim") else 1.0
            )
        A.intraday_scales = {
            code: scale for code, scale in A.intraday_scales.items()
            if code in used_codes
        }
        tick_map = _simulation_tick(
            context, [item["code"] for item in A.target_candidates]
        )
        execution_codes = (
            set(_managed_positions(snapshot).keys())
            | {item["code"] for item in A.target_candidates}
        )
        A.execution_prices = _raw_execution_prices(
            context, execution_codes, "open"
        )
        A.desired_shares = _desired_share_map(
            snapshot, style_exposures, A.target_candidates, tick_map,
            A.execution_prices,
        )
        print("DESIRED", trade_date, A.desired_shares)
        allocation = allocation_metrics(
            snapshot["balance"], style_exposures,
            A.desired_shares, A.target_candidates, A.execution_prices
        )
        print(
            "ALLOCATION", trade_date,
            "planned_exposure", allocation["planned_exposure"],
            "target_exposure", allocation["target_exposure"],
            "fill_rate", allocation["fill_rate"],
            "unallocated_cash", allocation["unallocated_cash"],
        )
        A.rebalance_age = 0

    exposure = round(sum(style_exposures.values()), 10)
    market["style_exposures"] = dict(style_exposures)
    market["exposure"] = exposure

    if not rebalance_due or not style_exposures:
        execution_codes = (
            set(_managed_positions(snapshot).keys())
            | {item["code"] for item in A.target_candidates}
        )
        A.execution_prices = _raw_execution_prices(
            context, execution_codes, "open"
        )

    exit_sent = _risk_exits(
        context, snapshot, asof, trade_date, style_exposures
    )
    # MA7/MA13 starter additions are confirmed intraday. Only the independent
    # secondary-base resume setup may still complete from a daily signal.
    trend_add_due = _activate_trend_adds(snapshot)
    if trend_add_due:
        tick_map = _simulation_tick(
            context, [item["code"] for item in A.target_candidates]
        )
        A.desired_shares = _desired_share_map(
            snapshot, style_exposures, A.target_candidates, tick_map,
            A.execution_prices,
        )
        print("DESIRED", trade_date, A.desired_shares)
    should_rebalance = (
        rebalance_due or not market_gate_exposures
        or A.retry_rebalance or exit_sent or trend_add_due
    )
    if should_rebalance:
        A.retry_rebalance = _rebalance_to_desired(
            context, snapshot, trade_date
        )
    A.rebalance_age += 1
    A.last_exposure = exposure
    A.last_market_gate_exposures = dict(market_gate_exposures)
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
    A.acct = "testS" if A.mode == "BACKTEST" else str(
        globals().get("account", "")
    )
    context.accountID = A.acct
    A.acct_type = "STOCK" if A.mode == "BACKTEST" else str(
        globals().get("accountType", "STOCK")
    ).upper()
    A.buy_code = 23 if A.acct_type == "STOCK" else 33
    A.sell_code = 24 if A.acct_type == "STOCK" else 34
    A.rebalance_age = REBALANCE_EVERY
    A.last_exposure = None
    A.last_market_gate_exposures = {}
    A.last_style_exposures = {}
    A.current_style_exposures = {}
    A.last_processed_date = ""
    A.last_intraday_key = ""
    A.target_candidates = []
    A.desired_shares = {}
    A.position_meta = {}
    A.intraday_scales = {}
    A.addback_plans = {}
    A.daily_position_metrics = {}
    A.entry_scales = {}
    A.build_plans = {}
    A.build_confirm_plans = {}
    A.trend_add_reasons = {}
    A.blocked_codes = set()
    A.owned_codes = set()
    A.sent_order_keys = set()
    A.logged_deal_keys = set()
    A.retry_rebalance = False
    A.execution_prices = {}
    A.sector_source_logged = set()
    A.price_coordinate_probe_logged = False
    A.first_bar_logged = False
    A.last_portfolio_log_date = ""
    A.actual_backtest_start = None
    A.actual_backtest_end = None
    A.range_logged = False
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
            A.actual_backtest_start = bar_time
        A.actual_backtest_end = bar_time
        trade_date = bar_time.strftime("%Y%m%d")
        range_due = False
        try:
            range_due = bool(context.is_last_bar())
        except Exception:
            pass
        if range_due and not A.range_logged:
            print(
                "BACKTEST_RANGE", "start",
                A.actual_backtest_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end", A.actual_backtest_end.strftime("%Y-%m-%d %H:%M:%S"),
            )
            A.range_logged = True
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
