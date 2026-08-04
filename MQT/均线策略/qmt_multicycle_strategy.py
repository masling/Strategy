#coding:gbk
# DOWNLOAD_BUILD: V1.3.0_20260804_SW1_PROXY

import datetime

import numpy as np
import pandas as pd


RUN_MODE = "BACKTEST"
STRATEGY_NAME = "QMT_MC_ROTATION_V1"
REBALANCE_EVERY = 5
MAX_SECTORS = 3
MAX_STOCKS = 6
MAX_PER_SECTOR = 2
MAX_STOCK_WEIGHT = 0.15
MIN_AVERAGE_AMOUNT = 50000000.0
TAKE_PROFIT_RATE = 0.12
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
MARKET_INDEXES = [
    ("000300.SH", 0.30),
    ("000905.SH", 0.25),
    ("000852.SH", 0.25),
    ("399006.SZ", 0.20),
]


class _State(object):
    pass


A = _State()


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


def market_leg_score(daily_close, weekly_close, monthly_close):
    daily = _clean_array(daily_close)
    weekly = _clean_array(weekly_close)
    monthly = _clean_array(monthly_close)
    if len(daily) < 125 or len(weekly) < 20 or len(monthly) < 20:
        return None

    d_ma20 = _mean_tail(daily, 20)
    d_ma60 = _mean_tail(daily, 60)
    d_ma120 = _mean_tail(daily, 120)
    d_ma20_prev = float(np.mean(daily[-25:-5]))
    w_ma10 = _mean_tail(weekly, 10)
    w_ma20 = _mean_tail(weekly, 20)
    m_ma10 = _mean_tail(monthly, 10)
    m_ma20 = _mean_tail(monthly, 20)
    rolling_high = float(np.max(daily[-20:]))
    drawdown = daily[-1] / rolling_high - 1.0 if rolling_high > 0 else -1.0

    score = 0.0
    score += 10.0 if daily[-1] > d_ma20 else 0.0
    score += 12.0 if d_ma20 > d_ma60 else 0.0
    score += 8.0 if d_ma20 > d_ma20_prev else 0.0
    score += 12.0 if weekly[-1] > w_ma10 else 0.0
    score += 12.0 if w_ma10 > w_ma20 else 0.0
    score += 6.0 if _return(weekly, 10) > 0 else 0.0
    score += 15.0 if monthly[-1] > m_ma10 else 0.0
    score += 15.0 if m_ma10 > m_ma20 else 0.0
    score += 5.0 if daily[-1] > d_ma120 else 0.0
    score += 5.0 if drawdown > -0.08 else 0.0
    return round(score, 2)


def exposure_from_score(score):
    if score is None or score < 50.0:
        return 0.0
    if score < 60.0:
        return 0.25
    if score < 70.0:
        return 0.45
    if score < 80.0:
        return 0.65
    return 0.80


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
    r20_rank = _percentile_map(eligible, "rel20")
    r60_rank = _percentile_map(eligible, "rel60")
    amount_rank = _percentile_map(eligible, "amount_ratio")
    ranked = []
    for code, feature in eligible:
        distance = max(0.0, float(feature.get("distance_ma20", 0.0)))
        overheat = min(80.0, max(0.0, (distance - 0.10) * 666.6667))
        score = (
            30.0 * r20_rank[code]
            + 25.0 * r60_rank[code]
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
    if frame is None or len(frame) < 61 or "close" not in frame.columns:
        return None
    data = frame.replace([np.inf, -np.inf], np.nan).dropna(subset=["close"])
    benchmark = _clean_array(benchmark_close)
    close = _clean_array(data["close"])
    if len(close) < 61 or len(benchmark) < 61:
        return None
    ma20 = float(np.mean(close[-20:]))
    ma60 = float(np.mean(close[-60:]))
    ma20_prev = float(np.mean(close[-25:-5]))
    r20 = _return(close, 20)
    r60 = _return(close, 60)
    b20 = _return(benchmark, 20)
    b60 = _return(benchmark, 60)
    trend = 0.0
    trend += 0.4 if close[-1] > ma20 else 0.0
    trend += 0.4 if ma20 > ma60 else 0.0
    trend += 0.2 if ma20 > ma20_prev else 0.0
    if "amount" in data.columns and len(data["amount"].dropna()) >= 20:
        amount = np.asarray(data["amount"], dtype=float)
        base = float(np.mean(amount[-20:]))
        recent = float(np.mean(amount[-5:]))
        amount_ratio = recent / base if base > 0 else 0.0
    else:
        amount_ratio = 1.0
    distance = close[-1] / ma20 - 1.0 if ma20 > 0 else 0.0
    rel20 = r20 - b20
    rel60 = r60 - b60
    eligible = bool(close[-1] > ma20 > ma60 and rel20 > 0.0 and rel60 > 0.0)
    return {
        "return20": r20,
        "return60": r60,
        "rel20": rel20,
        "rel60": rel60,
        "trend": round(trend, 4),
        "amount_ratio": amount_ratio,
        "distance_ma20": distance,
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


def stock_feature(frame, sector_return20, sector_return60,
                  min_average_amount=50000000.0):
    required = ["close", "high", "low", "amount", "volume"]
    if frame is None or len(frame) < 120:
        return None
    if any(field not in frame.columns for field in required):
        return None
    data = frame.copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    if len(data) < 120:
        return None

    close = np.asarray(data["close"], dtype=float)
    amount = np.asarray(data["amount"], dtype=float)
    volume = np.asarray(data["volume"], dtype=float)
    if close[-1] <= 0 or volume[-1] <= 0:
        return None
    if "suspendFlag" in data.columns and float(data["suspendFlag"].iloc[-1]) != 0.0:
        return None

    ma20 = float(np.mean(close[-20:]))
    ma60 = float(np.mean(close[-60:]))
    ma120 = float(np.mean(close[-120:]))
    average_amount = float(np.mean(amount[-20:]))
    r5 = _return(close, 5)
    r20 = _return(close, 20)
    r60 = _return(close, 60)
    distance_ma20 = close[-1] / ma20 - 1.0
    high60 = float(np.max(np.asarray(data["high"], dtype=float)[-60:]))
    high_proximity = close[-1] / high60 if high60 > 0 else 0.0
    atr = _atr(data, 14)

    if not (close[-1] > ma20 > ma60 > ma120):
        return None
    if average_amount < float(min_average_amount):
        return None
    if not (-0.05 <= r5 <= 0.12):
        return None
    if not (0.0 <= distance_ma20 <= 0.10):
        return None
    if high_proximity < 0.88:
        return None
    rs20 = r20 - float(sector_return20)
    rs60 = r60 - float(sector_return60)
    if rs20 <= 0.0 or rs60 <= 0.0:
        return None

    returns = np.diff(close[-21:]) / close[-21:-1]
    volatility = float(np.std(returns)) if len(returns) else 0.0
    return {
        "close": float(close[-1]),
        "ma20": ma20,
        "ma60": ma60,
        "ma120": ma120,
        "r20": r20,
        "r60": r60,
        "rs20": rs20,
        "rs60": rs60,
        "distance_ma20": distance_ma20,
        "high_proximity": high_proximity,
        "average_amount": average_amount,
        "volatility": volatility,
        "atr": atr,
    }


def position_metrics(frame):
    required = ["close", "high", "low"]
    if frame is None or len(frame) < 21:
        return None
    if any(field not in frame.columns for field in required):
        return None
    data = frame.copy()
    data = data.replace([np.inf, -np.inf], np.nan).dropna(subset=required)
    if len(data) < 21:
        return None
    close = np.asarray(data["close"], dtype=float)
    return {
        "close": float(close[-1]),
        "ma20": float(np.mean(close[-20:])),
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
    for field in ("rs20", "rs60", "r20", "high_proximity", "average_amount"):
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
            30.0 * rank_fields["rs20"][code]
            + 25.0 * rank_fields["rs60"][code]
            + 15.0 * rank_fields["r20"][code]
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


def exit_reason(close, ma20, atr, entry_price, peak_price, holding_days,
                still_selected, exposure, take_profit_rate=0.12):
    if exposure <= 0.0:
        return "market_risk"
    if atr > 0 and close <= entry_price - 2.0 * atr:
        return "initial_stop"
    if atr > 0 and close <= peak_price - 2.5 * atr:
        return "trailing_stop"
    profit_rate = close / entry_price - 1.0 if entry_price > 0 else 0.0
    if take_profit_rate > 0 and profit_rate >= take_profit_rate - 1e-12:
        return "take_profit"
    if holding_days >= 20:
        return "max_holding"
    if close < ma20:
        return "trend_break"
    if not still_selected:
        return "sector_rotation"
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
    codes = [item[0] for item in MARKET_INDEXES]
    daily = fetch_history(context, ["close"], codes, "1d", 130, asof)
    weekly = fetch_history(context, ["close"], codes, "1w", 26, asof)
    monthly = fetch_history(context, ["close"], codes, "1mon", 24, asof)
    weighted_score = 0.0
    valid_weight = 0.0
    details = {}
    benchmark = np.asarray([], dtype=float)
    for code, weight in MARKET_INDEXES:
        daily_close = _close_values(daily.get(code))
        weekly_close = _close_values(weekly.get(code))
        monthly_close = _close_values(monthly.get(code))
        score = market_leg_score(daily_close, weekly_close, monthly_close)
        if score is None:
            continue
        details[code] = score
        weighted_score += float(weight) * score
        valid_weight += float(weight)
        if len(benchmark) == 0:
            benchmark = daily_close
    if valid_weight < 0.50 or len(benchmark) < 61:
        return {
            "score": None,
            "exposure": 0.0,
            "details": details,
            "benchmark": benchmark,
        }
    score = round(weighted_score / valid_weight, 2)
    return {
        "score": score,
        "exposure": exposure_from_score(score),
        "details": details,
        "benchmark": benchmark,
    }


def _sector_selection(context, asof, benchmark):
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
            if board_allowed(code, ALLOW_CHINEXT, ALLOW_STAR, ALLOW_BSE)
        ]
        if not members:
            continue
        records[sector_name] = {
            "code": sector_name,
            "name": sector_name,
            "member_sector": sector_name,
            "members": members,
        }
        for code in members:
            if code not in seen_codes:
                seen_codes.add(code)
                all_codes.append(code)
    if not records:
        print("ERROR SW1 sector boards are empty")
        return []

    history = fetch_history(
        context, ["close", "amount"], all_codes, "1d", 70, asof,
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
    if not getattr(A, "sector_source_logged", False):
        print(
            "SECTOR_SOURCE SW1_MEMBER_PROXY boards", len(records),
            "stocks", len(all_codes), "histories", len(history)
        )
        A.sector_source_logged = True
    ranked = rank_sectors(features, MAX_SECTORS)
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
        130,
        asof,
        "back_ratio",
    )
    candidates = []
    for code in all_codes:
        sector = sector_by_code[code]
        sector_feature_data = sector["feature"]
        feature = stock_feature(
            history.get(code),
            sector_feature_data["return20"],
            sector_feature_data["return60"],
            MIN_AVERAGE_AMOUNT,
        )
        if feature is None or _is_st_on(context, code, asof):
            continue
        candidates.append({
            "code": code,
            "sector": sector["member_sector"],
            "sector_code": sector["code"],
            "feature": feature,
        })
    selected = select_stocks(
        score_stock_candidates(candidates), MAX_STOCKS, MAX_PER_SECTOR
    )
    for item in selected:
        item["name"] = _instrument_name(context, item["code"])
    return selected


def _backtest_snapshot(context):
    try:
        holdings = get_result_records("holdings", context.barpos, context) or []
        net_value = float(context.get_net_value(context.barpos))
        capital = float(context.capital)
    except Exception as error:
        print("ERROR backtest portfolio query failed:", error)
        return None

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
    return {
        "balance": balance,
        "available_cash": max(0.0, balance - market_value),
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


def _desired_share_map(snapshot, exposure, candidates, tick_map):
    desired = {}
    count = len(candidates)
    if count <= 0 or exposure <= 0:
        return desired
    candidate_map = {item["code"]: item for item in candidates}
    for item in candidates:
        code = item["code"]
        if code in getattr(A, "blocked_codes", set()):
            continue
        price = _execution_price(code, candidate_map, tick_map, "buy")
        desired[code] = target_shares(
            snapshot["balance"], exposure, count, price, MAX_STOCK_WEIGHT
        )
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
                    "peak_price": price,
                    "holding_days": 0,
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


def _risk_exits(context, snapshot, asof, trade_date, exposure):
    positions = _managed_positions(snapshot)
    if not positions:
        A.position_meta = {}
        return False
    if exposure <= 0.0:
        sent = False
        for code, position in positions.items():
            A.desired_shares[code] = 0
            if _send_order(
                    context, "sell", code, position["available"],
                    trade_date, "market_risk"):
                sent = True
        return sent

    history = fetch_history(
        context, ["close", "high", "low"], list(positions.keys()),
        "1d", 130, asof, "back_ratio"
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
                "peak_price": max(entry, metrics["close"]),
                "holding_days": 1,
            }
        else:
            meta["holding_days"] = int(meta.get("holding_days", 0)) + 1
            meta["peak_price"] = max(
                float(meta.get("peak_price", metrics["close"])), metrics["close"]
            )
        A.position_meta[code] = meta
        still_selected = (
            int(A.desired_shares.get(code, 0)) > 0
            and code not in A.blocked_codes
        )
        reason = exit_reason(
            metrics["close"], metrics["ma20"], metrics["atr"],
            meta["entry_price"], meta["peak_price"], meta["holding_days"],
            still_selected, exposure, TAKE_PROFIT_RATE,
        )
        if reason is None:
            continue
        A.desired_shares[code] = 0
        A.blocked_codes.add(code)
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
        "STATE", trade_date, "score", market["score"],
        "exposure", market["exposure"], "legs", market["details"]
    )
    if sectors:
        print("SECTORS", [(item["member_sector"], item["score"]) for item in sectors])
    if candidates:
        print(
            "TARGETS",
            [(item["code"], item.get("name", ""), item["score"])
             for item in candidates],
        )


def run_daily_cycle(context, asof, trade_date):
    market = _market_state(context, asof)
    exposure = float(market["exposure"])
    snapshot = _account_snapshot(context)
    if snapshot is None:
        return
    _refresh_owned_codes(snapshot)

    risk_on_restart = (
        A.last_exposure is not None
        and A.last_exposure <= 0.0
        and exposure > 0.0
    )
    rebalance_due = A.rebalance_age >= REBALANCE_EVERY or risk_on_restart
    exposure_decrease = (
        A.last_exposure is not None and exposure < A.last_exposure
    )
    selected_sectors = []

    if exposure <= 0.0:
        A.target_candidates = []
        A.desired_shares = {
            code: 0 for code in _managed_positions(snapshot).keys()
        }
    elif rebalance_due:
        selected_sectors = _sector_selection(
            context, asof, market["benchmark"]
        )
        A.target_candidates = _stock_selection(
            context, asof, selected_sectors
        )
        A.blocked_codes = set()
        tick_map = _simulation_tick(
            context, [item["code"] for item in A.target_candidates]
        )
        A.desired_shares = _desired_share_map(
            snapshot, exposure, A.target_candidates, tick_map
        )
        A.rebalance_age = 0
    elif exposure_decrease:
        tick_map = _simulation_tick(
            context, [item["code"] for item in A.target_candidates]
        )
        A.desired_shares = _desired_share_map(
            snapshot, exposure, A.target_candidates, tick_map
        )

    exit_sent = _risk_exits(
        context, snapshot, asof, trade_date, exposure
    )
    should_rebalance = (
        rebalance_due or exposure_decrease or exposure <= 0.0
        or A.retry_rebalance or exit_sent
    )
    if should_rebalance:
        A.retry_rebalance = _rebalance_to_desired(
            context, snapshot, trade_date
        )
    A.rebalance_age += 1
    A.last_exposure = exposure
    _print_daily_summary(
        trade_date, market, selected_sectors, A.target_candidates
    )


def init(context):
    A.mode = str(RUN_MODE).upper()
    if A.mode not in ("BACKTEST", "SIMULATION"):
        raise ValueError("RUN_MODE must be BACKTEST or SIMULATION")
    A.acct = "test" if A.mode == "BACKTEST" else str(globals().get("account", ""))
    A.acct_type = "STOCK" if A.mode == "BACKTEST" else str(
        globals().get("accountType", "STOCK")
    ).upper()
    A.buy_code = 23 if A.acct_type == "STOCK" else 33
    A.sell_code = 24 if A.acct_type == "STOCK" else 34
    A.rebalance_age = REBALANCE_EVERY
    A.last_exposure = None
    A.last_processed_date = ""
    A.target_candidates = []
    A.desired_shares = {}
    A.position_meta = {}
    A.blocked_codes = set()
    A.owned_codes = set()
    A.sent_order_keys = set()
    A.retry_rebalance = False
    A.sector_source_logged = False
    print("INIT", STRATEGY_NAME, A.mode, A.acct, A.acct_type)


def handlebar(context):
    if A.mode == "BACKTEST":
        bar_time = timetag_to_datetime(
            context.get_bar_timetag(context.barpos), "%Y%m%d%H%M%S"
        )
        trade_date = str(bar_time)[:8]
        asof = trade_date
    else:
        if not context.is_last_bar():
            return
        now = datetime.datetime.now()
        now_time = now.strftime("%H%M%S")
        if now_time < "093500" or now_time > "145000":
            return
        trade_date = now.strftime("%Y%m%d")
        asof = (now - datetime.timedelta(days=1)).strftime("%Y%m%d")
    if trade_date == A.last_processed_date:
        return
    A.last_processed_date = trade_date
    try:
        run_daily_cycle(context, asof, trade_date)
    except Exception as error:
        print("ERROR daily cycle failed:", trade_date, error)
