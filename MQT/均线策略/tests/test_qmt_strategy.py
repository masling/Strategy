import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd


try:
    strategy_path = Path(__file__).resolve().parents[1] / "qmt_multicycle_strategy.py"
    strategy_spec = importlib.util.spec_from_file_location(
        "qmt_multicycle_strategy", str(strategy_path)
    )
    strategy = importlib.util.module_from_spec(strategy_spec)
    strategy_spec.loader.exec_module(strategy)
except Exception:
    strategy = None


def invoke(name, *args, **kwargs):
    if strategy is None:
        return None
    function = getattr(strategy, name, None)
    if function is None:
        return None
    return function(*args, **kwargs)


class MarketRegimeTests(unittest.TestCase):
    def test_rising_71340_daily_trend_scores_100(self):
        daily = np.arange(1.0, 71.0)
        self.assertEqual(invoke("trend_71340_score", daily), 100.0)

    def test_falling_71340_daily_trend_scores_zero(self):
        daily = np.arange(71.0, 1.0, -1.0)
        self.assertEqual(invoke("trend_71340_score", daily), 0.0)

    def test_short_rebound_under_falling_ma40_does_not_activate_style(self):
        daily = np.concatenate([
            np.linspace(100.0, 60.0, 40),
            np.linspace(68.0, 100.0, 5),
        ])
        score = invoke("trend_71340_score", daily)
        self.assertLess(score, 70.0)
        self.assertEqual(
            invoke("style_exposure_map", {"000852.SH": score}), {}
        )

    def test_one_strong_style_opens_only_its_25_percent_budget(self):
        scores = {
            "000300.SH": 20.0,
            "000905.SH": 20.0,
            "000852.SH": 80.0,
            "399006.SZ": 20.0,
        }
        budgets = invoke("style_exposure_map", scores) or {}
        self.assertEqual(budgets, {"000852.SH": 0.25})

    def test_four_strong_styles_are_scaled_to_80_percent_cap(self):
        scores = {
            "000300.SH": 100.0,
            "000905.SH": 100.0,
            "000852.SH": 100.0,
            "399006.SZ": 100.0,
        }
        budgets = invoke("style_exposure_map", scores) or {}
        self.assertAlmostEqual(sum(budgets.values()), 0.80)
        self.assertTrue(all(abs(value - 0.20) < 1e-12
                            for value in budgets.values()))

    def test_market_state_reads_daily_data_only(self):
        class FakeContext(object):
            def __init__(self):
                self.periods = []

            def get_market_data_ex(self, fields, stocks, **kwargs):
                self.periods.append(kwargs["period"])
                return {
                    code: pd.DataFrame({"close": np.arange(1.0, 56.0)})
                    for code in stocks
                }

        context = FakeContext()
        market = invoke("_market_state", context, "20260803") or {}
        self.assertEqual(context.periods, ["1d"])
        self.assertAlmostEqual(market["exposure"], 0.80)


class SectorRankingTests(unittest.TestCase):
    def test_sector_index_name_maps_to_member_sector(self):
        self.assertEqual(
            invoke("sector_member_name", "SW1电子加权"), "SW1电子"
        )

    def test_sector_feature_uses_71340_relative_strength_to_benchmark(self):
        close = np.linspace(100.0, 140.0, 70)
        amount = np.linspace(100000000.0, 130000000.0, 70)
        frame = pd.DataFrame({"close": close, "amount": amount})
        benchmark = np.linspace(100.0, 115.0, 70)
        feature = invoke("sector_feature", frame, benchmark)
        self.assertIsInstance(feature, dict)
        self.assertTrue(feature["eligible"])
        self.assertGreater(feature["rel13"], 0.0)
        self.assertGreater(feature["rel40"], 0.0)
        self.assertEqual(feature["trend"], 1.0)

    def test_sector_ranking_rejects_weak_trends_and_penalizes_overheat(self):
        features = {
            "strong": {
                "rel13": 0.08, "rel40": 0.15, "trend": 1.0,
                "amount_ratio": 1.20, "distance_ma13": 0.05,
                "eligible": True,
            },
            "overheated": {
                "rel13": 0.12, "rel40": 0.18, "trend": 1.0,
                "amount_ratio": 1.30, "distance_ma13": 0.22,
                "eligible": True,
            },
            "weak": {
                "rel13": -0.05, "rel40": -0.10, "trend": 0.2,
                "amount_ratio": 0.80, "distance_ma13": -0.04,
                "eligible": False,
            },
        }
        ranked = invoke("rank_sectors", features, 3) or []
        self.assertEqual([item[0] for item in ranked], ["strong", "overheated"])
        self.assertGreater(ranked[0][1], ranked[1][1])

    def test_sector_proxy_compounds_equal_weight_member_returns(self):
        index = pd.Index(range(70))
        history = {
            "000001.SZ": pd.DataFrame({
                "close": 100.0 * np.power(1.01, np.arange(70)),
                "amount": np.repeat(100000000.0, 70),
            }, index=index),
            "600000.SH": pd.DataFrame({
                "close": 100.0 * np.power(1.03, np.arange(70)),
                "amount": np.repeat(200000000.0, 70),
            }, index=index),
        }

        proxy = invoke(
            "sector_proxy_frame", history,
            ["000001.SZ", "600000.SH"], 2,
        )

        self.assertIsInstance(proxy, pd.DataFrame)
        self.assertEqual(len(proxy), 70)
        self.assertAlmostEqual(float(proxy["close"].iloc[0]), 100.0)
        self.assertAlmostEqual(
            float(proxy["close"].iloc[-1]),
            100.0 * np.power(1.02, 69), places=6,
        )
        self.assertEqual(float(proxy["amount"].iloc[-1]), 300000000.0)

    def test_sector_selection_intersects_sw1_members_with_strong_style(self):
        class FakeContext(object):
            def __init__(self):
                self.members = {
                    "SW1汽车": ["000001.SZ", "000002.SZ"],
                    "SW1银行": ["600000.SH", "600036.SH"],
                }
                self.history = {}
                for code in self.members["SW1汽车"]:
                    self.history[code] = pd.DataFrame({
                        "close": 100.0 * np.power(1.005, np.arange(70)),
                        "amount": np.repeat(100000000.0, 70),
                    })
                for code in self.members["SW1银行"]:
                    self.history[code] = pd.DataFrame({
                        "close": 100.0 * np.power(0.998, np.arange(70)),
                        "amount": np.repeat(100000000.0, 70),
                    })

            def get_stock_list_in_sector(self, name):
                return list(self.members.get(name, []))

            def get_market_data_ex(self, fields, stocks, **kwargs):
                return {
                    code: self.history[code][list(fields)].copy()
                    for code in stocks if code in self.history
                }

        original_names = getattr(strategy, "SW1_SECTOR_NAMES", None)
        had_original_names = hasattr(strategy, "SW1_SECTOR_NAMES")
        strategy.SW1_SECTOR_NAMES = ("SW1汽车", "SW1银行")
        try:
            benchmark = 100.0 * np.power(1.001, np.arange(70))
            selected = invoke(
                "_sector_selection", FakeContext(), "20260803", benchmark,
                {"000001.SZ", "600000.SH"}, "000852.SH",
            ) or []
            self.assertEqual([item["member_sector"] for item in selected],
                             ["SW1汽车"])
            self.assertEqual(selected[0]["members"], ["000001.SZ"])
            self.assertEqual(selected[0]["style"], "000852.SH")
        finally:
            if had_original_names:
                strategy.SW1_SECTOR_NAMES = original_names
            else:
                delattr(strategy, "SW1_SECTOR_NAMES")


class StockSelectionTests(unittest.TestCase):
    @staticmethod
    def make_frame(last_close=130.0, amount=100000000.0):
        close = np.linspace(80.0, last_close, 130)
        return pd.DataFrame({
            "close": close,
            "high": close * 1.02,
            "low": close * 0.98,
            "amount": np.repeat(amount, 130),
            "volume": np.repeat(1000000.0, 130),
            "suspendFlag": np.zeros(130),
        })

    def test_stock_feature_accepts_liquid_orderly_uptrend(self):
        feature = invoke(
            "stock_feature", self.make_frame(), 0.01, 0.03, 50000000.0
        )
        self.assertIsNotNone(feature)
        self.assertGreater(feature["rs13"], 0.0)
        self.assertGreater(feature["rs40"], 0.0)

    def test_stock_feature_rejects_illiquid_stock(self):
        feature = invoke(
            "stock_feature", self.make_frame(amount=1000000.0),
            0.01, 0.03, 50000000.0
        )
        self.assertIsNone(feature)

    def test_position_metrics_remain_available_after_trend_break(self):
        frame = self.make_frame(last_close=130.0)
        frame.loc[frame.index[-1], "close"] = 100.0
        metrics = invoke("position_metrics", frame)
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["close"], 100.0)
        self.assertIn("ma13", metrics)
        self.assertIn("ma40", metrics)
        self.assertGreater(metrics["atr"], 0.0)

    def test_select_stocks_enforces_two_names_per_sector(self):
        candidates = [
            {"code": "A", "sector": "S1", "score": 100.0},
            {"code": "B", "sector": "S1", "score": 90.0},
            {"code": "C", "sector": "S1", "score": 80.0},
            {"code": "D", "sector": "S2", "score": 70.0},
        ]
        selected = invoke("select_stocks", candidates, 6, 2) or []
        self.assertEqual([item["code"] for item in selected], ["A", "B", "D"])

    def test_cross_sectional_stock_score_prefers_stronger_liquid_name(self):
        candidates = [
            {"code": "A", "sector": "S1", "feature": {
                "rs13": 0.10, "rs40": 0.20, "r13": 0.15,
                "high_proximity": 0.98, "average_amount": 200000000.0,
                "volatility": 0.01,
            }},
            {"code": "B", "sector": "S2", "feature": {
                "rs13": 0.02, "rs40": 0.04, "r13": 0.05,
                "high_proximity": 0.90, "average_amount": 60000000.0,
                "volatility": 0.03,
            }},
        ]
        scored = invoke("score_stock_candidates", candidates) or []
        self.assertEqual([item["code"] for item in scored], ["A", "B"])
        self.assertGreater(scored[0]["score"], scored[1]["score"])

    def test_board_filter_defaults_can_exclude_star_and_bse(self):
        self.assertFalse(invoke("board_allowed", "688001.SH", True, False, False))
        self.assertFalse(invoke("board_allowed", "430001.BJ", True, False, False))
        self.assertTrue(invoke("board_allowed", "300001.SZ", True, False, False))


class RiskAndSizingTests(unittest.TestCase):
    def test_initial_atr_stop_overrides_minimum_holding_period(self):
        reason = invoke(
            "exit_reason", close=90.0, high=92.0, ma13=95.0, ma40=94.0,
            atr=4.0, entry_price=100.0, prior_below_ma13_days=0,
            still_selected=True, style_exposure=0.25,
        )
        self.assertEqual(reason, "initial_stop")

    def test_style_rotation_exit_has_no_minimum_holding_period(self):
        reason = invoke(
            "exit_reason",
            105.0, 106.0, 100.0, 95.0, 3.0, 100.0, 0, False, 0.25,
        )
        self.assertEqual(reason, "sector_rotation")

    def test_profit_and_holding_days_do_not_force_exit(self):
        reason = invoke(
            "exit_reason",
            130.0, 132.0, 120.0, 110.0, 3.0, 100.0, 0, True, 0.25,
        )
        self.assertIsNone(reason)

    def test_ma40_break_exits_immediately(self):
        reason = invoke(
            "exit_reason",
            94.0, 96.0, 98.0, 95.0, 4.0, 100.0, 0, True, 0.25,
        )
        self.assertEqual(reason, "ma40_break")

    def test_failed_rebound_to_ma13_exits_after_prior_break(self):
        reason = invoke(
            "exit_reason", 99.0, 100.5, 100.0, 95.0, 3.0, 100.0,
            1, True, 0.25,
        )
        self.assertEqual(reason, "ma13_rebound_failed")

    def test_target_shares_rounds_down_to_board_lot(self):
        shares = invoke(
            "target_shares", total_asset=1000000.0, exposure=0.80,
            position_count=6, price=20.0, max_weight=0.15,
        )
        self.assertEqual(shares, 6600)

    def test_style_budget_is_divided_only_inside_that_style(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        snapshot = {"balance": 1000000.0}
        candidates = [
            {"code": "A", "style": "S1", "feature": {"close": 10.0}},
            {"code": "B", "style": "S1", "feature": {"close": 20.0}},
            {"code": "C", "style": "S2", "feature": {"close": 10.0}},
        ]
        desired = invoke(
            "_desired_share_map", snapshot, {"S1": 0.25, "S2": 0.10},
            candidates, {}, {"A": 10.0, "B": 20.0, "C": 10.0},
        )
        self.assertEqual(desired, {"A": 12500, "B": 6200, "C": 10000})

    def test_sizing_skips_zero_lot_candidate_and_uses_next_ranked_names(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        snapshot = {"balance": 1000000.0}
        candidates = [
            {"code": "EXPENSIVE", "style": "S1", "score": 100.0,
             "feature": {"close": 2000.0}},
            {"code": "B", "style": "S1", "score": 90.0,
             "feature": {"close": 10.0}},
            {"code": "C", "style": "S1", "score": 80.0,
             "feature": {"close": 20.0}},
        ]
        desired = invoke(
            "_desired_share_map", snapshot, {"S1": 0.25}, candidates, {},
            {"EXPENSIVE": 2000.0, "B": 10.0, "C": 20.0},
        ) or {}
        self.assertEqual(desired, {"B": 12500, "C": 6200})

    def test_allocation_metrics_report_planned_and_sizable_target_exposure(self):
        candidates = [
            {"code": "A", "feature": {"close": 10.0}},
            {"code": "B", "feature": {"close": 20.0}},
        ]
        metrics = invoke(
            "allocation_metrics", 1000000.0, {"S1": 0.25},
            {"A": 12500, "B": 6200}, candidates,
            {"A": 10.0, "B": 20.0},
        )
        self.assertAlmostEqual(metrics["planned_exposure"], 0.25)
        self.assertAlmostEqual(metrics["target_exposure"], 0.249)
        self.assertAlmostEqual(metrics["fill_rate"], 0.996)


class IntradayAggregationTests(unittest.TestCase):
    @staticmethod
    def make_5m(times):
        count = len(times)
        close = np.arange(10.0, 10.0 + count)
        return pd.DataFrame({
            "open": close - 0.2,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.arange(100.0, 100.0 + count),
            "amount": np.arange(1000.0, 1000.0 + count),
        }, index=pd.to_datetime(times))

    def test_5m_aggregation_keeps_only_complete_session_30m_bars(self):
        times = [
            "2026-08-03 09:35", "2026-08-03 09:40",
            "2026-08-03 09:45", "2026-08-03 09:50",
            "2026-08-03 09:55", "2026-08-03 10:00",
            "2026-08-03 10:05", "2026-08-03 10:10",
            "2026-08-03 10:15", "2026-08-03 10:20",
            "2026-08-03 10:25", "2026-08-03 10:30",
            "2026-08-03 13:05",
        ]
        bars = invoke("aggregate_5m_to_30m", self.make_5m(times))
        self.assertEqual(list(bars.index.strftime("%H:%M")), ["10:00", "10:30"])
        self.assertEqual(float(bars.iloc[0]["open"]), 9.8)
        self.assertEqual(float(bars.iloc[0]["close"]), 15.0)
        self.assertEqual(float(bars.iloc[0]["volume"]), 615.0)

    def test_confirmed_30m_volume_reversal_reduces_position(self):
        index = pd.date_range("2026-08-03 10:00", periods=22, freq="30min")
        frame = pd.DataFrame({
            "open": np.repeat(10.0, 22),
            "high": np.repeat(10.5, 22),
            "low": np.repeat(9.8, 22),
            "close": np.repeat(10.2, 22),
            "volume": np.repeat(100.0, 22),
            "amount": np.repeat(1000.0, 22),
        }, index=index)
        frame.iloc[-2] = [10.0, 12.0, 9.9, 10.4, 220.0, 2200.0]
        frame.iloc[-1] = [10.3, 10.4, 9.7, 9.8, 120.0, 1200.0]
        self.assertEqual(
            invoke("intraday_action", frame, 9.5, 9.0, False), "reduce"
        )

    def test_30m_reversal_near_daily_support_adds_reduced_part_back(self):
        frame = pd.DataFrame({
            "open": [10.1, 10.2],
            "high": [10.3, 10.6],
            "low": [9.95, 10.0],
            "close": [10.1, 10.5],
            "volume": [100.0, 120.0],
            "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        self.assertEqual(
            invoke("intraday_action", frame, 10.0, 9.7, True), "add"
        )


class QmtAdapterTests(unittest.TestCase):
    def test_backtest_execution_price_never_falls_back_to_adjusted_close(self):
        strategy.A.mode = "BACKTEST"
        candidates = {
            "000001.SZ": {"feature": {"close": 934.0}},
        }
        self.assertEqual(invoke(
            "_execution_price", "000001.SZ", candidates, {}, "buy",
            {"000001.SZ": 20.0},
        ), 20.0)
        self.assertEqual(invoke(
            "_execution_price", "000001.SZ", candidates, {}, "buy", {},
        ), 0.0)

    def test_raw_execution_price_query_disables_price_adjustment(self):
        class FakeContext(object):
            barpos = 12

            @staticmethod
            def get_bar_timetag(index):
                if index != 12:
                    raise AssertionError("unexpected bar index")
                return 20260806100500

            def get_market_data_ex(self, fields, stocks, **kwargs):
                self.kwargs = kwargs
                return {
                    "000001.SZ": pd.DataFrame({
                        "open": [20.0], "close": [20.5],
                    }),
                }

        original = getattr(strategy, "timetag_to_datetime", None)
        had_original = hasattr(strategy, "timetag_to_datetime")
        strategy.timetag_to_datetime = lambda *args: "20260806100500"
        context = FakeContext()
        try:
            prices = invoke(
                "_raw_execution_prices", context, ["000001.SZ"], "open"
            ) or {}
            self.assertEqual(prices, {"000001.SZ": 20.0})
            self.assertEqual(context.kwargs["period"], "5m")
            self.assertEqual(context.kwargs["count"], 1)
            self.assertEqual(context.kwargs["dividend_type"], "none")
        finally:
            if had_original:
                strategy.timetag_to_datetime = original
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_backtest_init_uses_qmt_compatible_test_account(self):
        class FakeContext(object):
            period = "5m"
            start = "2026-01-01 00:00:00"
            end = "2026-08-04 23:59:59"
            capital = 1000000.0

        context = FakeContext()
        invoke("init", context)
        self.assertEqual(strategy.A.acct, "testS")
        self.assertEqual(context.accountID, "testS")

    def test_backtest_order_uses_order_shares_for_visible_trade_records(self):
        class FakeContext(object):
            accountID = "testS"

            @staticmethod
            def get_history_data(*args):
                return {
                    "000001.SZ": [10.25],
                    "600000.SH": [8.50],
                }

        original_order_shares = getattr(strategy, "order_shares", None)
        had_order_shares = hasattr(strategy, "order_shares")
        original_passorder = getattr(strategy, "passorder", None)
        had_passorder = hasattr(strategy, "passorder")
        calls = []
        strategy.A.mode = "BACKTEST"
        strategy.A.acct = "testS"
        strategy.A.sent_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.order_shares = lambda *args: calls.append(args)
        strategy.passorder = lambda *args: (_ for _ in ()).throw(
            AssertionError("backtest must not use passorder")
        )
        context = FakeContext()
        try:
            self.assertTrue(invoke(
                "_send_order", context, "buy", "000001.SZ", 1000,
                "20260805", "rebalance",
            ))
            self.assertTrue(invoke(
                "_send_order", context, "sell", "600000.SH", 500,
                "20260805", "risk_stop",
            ))
            self.assertEqual(calls, [
                ("000001.SZ", 1000, "fix", 10.25, context, "testS"),
                ("600000.SH", -500, "fix", 8.50, context, "testS"),
            ])
        finally:
            if had_order_shares:
                strategy.order_shares = original_order_shares
            else:
                delattr(strategy, "order_shares")
            if had_passorder:
                strategy.passorder = original_passorder
            else:
                delattr(strategy, "passorder")

    def test_backtest_order_accepts_precomputed_price_outside_universe(self):
        class FakeContext(object):
            accountID = "testS"

            @staticmethod
            def get_history_data(*args):
                raise AssertionError("explicit price must avoid universe lookup")

        original = getattr(strategy, "order_shares", None)
        had_original = hasattr(strategy, "order_shares")
        calls = []
        strategy.A.mode = "BACKTEST"
        strategy.A.sent_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.order_shares = lambda *args: calls.append(args)
        context = FakeContext()
        try:
            self.assertTrue(invoke(
                "_send_order", context, "buy", "002755.SZ", 1000,
                "20260806", "rebalance", 13.25,
            ))
            self.assertEqual(calls, [
                ("002755.SZ", 1000, "fix", 13.25, context, "testS"),
            ])
        finally:
            if had_original:
                strategy.order_shares = original
            else:
                delattr(strategy, "order_shares")

    def test_simulation_order_keeps_passorder_execution_path(self):
        class FakeContext(object):
            pass

        original_passorder = getattr(strategy, "passorder", None)
        had_passorder = hasattr(strategy, "passorder")
        calls = []
        strategy.A.mode = "SIMULATION"
        strategy.A.acct = "SIM001"
        strategy.A.buy_code = 23
        strategy.A.sell_code = 24
        strategy.A.sent_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.passorder = lambda *args: calls.append(args)
        context = FakeContext()
        try:
            self.assertTrue(invoke(
                "_send_order", context, "buy", "000001.SZ", 1000,
                "20260805", "rebalance",
            ))
            self.assertEqual(calls[0], (
                23, 1101, "SIM001", "000001.SZ", 14, -1, 1000,
                strategy.STRATEGY_NAME, 1, "20260805_buy_rebalance", context,
            ))
        finally:
            if had_passorder:
                strategy.passorder = original_passorder
            else:
                delattr(strategy, "passorder")

    def test_backtest_init_rejects_non_5m_main_period(self):
        class FakeContext(object):
            period = "1d"
            start = "2026-01-01 00:00:00"
            end = "2026-08-04 23:59:59"

        with self.assertRaisesRegex(ValueError, "5m"):
            invoke("init", FakeContext())

    def test_backtest_init_sets_configured_capital_when_interface_is_invalid(self):
        class FakeContext(object):
            period = "5m"
            start = -1
            end = -1
            capital = -1.0

        context = FakeContext()
        invoke("init", context)
        self.assertEqual(context.capital, 1000000.0)

    def test_backtest_skips_bars_before_interface_start(self):
        class FakeContext(object):
            period = "5m"
            start = "2026-01-01 00:00:00"
            end = "2026-08-04 23:59:59"
            barpos = 0

            @staticmethod
            def get_bar_timetag(index):
                return index

        context = FakeContext()
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_original_timetag = hasattr(strategy, "timetag_to_datetime")
        original_daily = strategy.run_daily_cycle
        calls = []
        strategy.timetag_to_datetime = lambda *args: "20251231093500"
        strategy.run_daily_cycle = lambda *args: calls.append(args)
        try:
            invoke("init", context)
            invoke("handlebar", context)
            self.assertEqual(calls, [])
            self.assertEqual(context.start, "2026-01-01 00:00:00")
            self.assertEqual(context.end, "2026-08-04 23:59:59")
        finally:
            strategy.run_daily_cycle = original_daily
            if had_original_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_backtest_skips_bars_after_interface_end(self):
        class FakeContext(object):
            period = "5m"
            start = "2026-01-01 00:00:00"
            end = "2026-08-04 23:59:59"
            barpos = 0

            @staticmethod
            def get_bar_timetag(index):
                return index

        context = FakeContext()
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_original_timetag = hasattr(strategy, "timetag_to_datetime")
        original_daily = strategy.run_daily_cycle
        calls = []
        strategy.timetag_to_datetime = lambda *args: "20260805000500"
        strategy.run_daily_cycle = lambda *args: calls.append(args)
        try:
            invoke("init", context)
            invoke("handlebar", context)
            self.assertEqual(calls, [])
        finally:
            strategy.run_daily_cycle = original_daily
            if had_original_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_backtest_snapshot_uses_virtual_account_can_use_volume(self):
        class FakeAccount(object):
            m_dBalance = 1050000.0
            m_dAvailable = 1040000.0

        class FakePosition(object):
            m_strInstrumentID = "000001"
            m_strExchangeID = "SZ"
            m_nVolume = 1000
            m_nCanUseVolume = 0
            m_dOpenPrice = 9.50
            m_dLastPrice = 10.00

        class FakeContext(object):
            capital = 1000000.0
            barpos = 20

            @staticmethod
            def get_net_value(index):
                if index != 20:
                    raise AssertionError("unexpected bar index")
                return 1.05

        original_trade = getattr(strategy, "get_trade_detail_data", None)
        had_original_trade = hasattr(strategy, "get_trade_detail_data")
        original_records = getattr(strategy, "get_result_records", None)
        had_original_records = hasattr(strategy, "get_result_records")
        strategy.A.mode = "BACKTEST"
        strategy.A.acct = "test"
        strategy.A.acct_type = "STOCK"

        def fake_trade_detail(account, account_type, detail_type):
            self.assertEqual((account, account_type), ("test", "STOCK"))
            if detail_type == "account":
                return [FakeAccount()]
            if detail_type == "position":
                return [FakePosition()]
            raise AssertionError("unexpected detail type")

        strategy.get_trade_detail_data = fake_trade_detail
        strategy.get_result_records = lambda *args: (_ for _ in ()).throw(
            AssertionError("virtual account data must take priority")
        )
        try:
            snapshot = invoke("_account_snapshot", FakeContext())
            self.assertEqual(snapshot["balance"], 1050000.0)
            self.assertEqual(snapshot["available_cash"], 1040000.0)
            self.assertEqual(
                snapshot["positions"],
                {"000001.SZ": {
                    "volume": 1000,
                    "available": 0,
                    "open_price": 9.50,
                    "current_price": 10.00,
                }},
            )
        finally:
            if had_original_trade:
                strategy.get_trade_detail_data = original_trade
            else:
                delattr(strategy, "get_trade_detail_data")
            if had_original_records:
                strategy.get_result_records = original_records
            else:
                delattr(strategy, "get_result_records")

    def test_backtest_portfolio_log_is_printed_once_per_trade_day(self):
        class FakeAccount(object):
            m_dBalance = 1000000.0
            m_dAvailable = 1000000.0

        class FakeContext(object):
            capital = 1000000.0
            barpos = 20
            trade_day = "20251014"

            def get_bar_timetag(self, index):
                self.assert_bar_index(index)
                return self.trade_day + "103000"

            @staticmethod
            def assert_bar_index(index):
                if index != 20:
                    raise AssertionError("unexpected bar index")

        original_trade = getattr(strategy, "get_trade_detail_data", None)
        had_original_trade = hasattr(strategy, "get_trade_detail_data")
        strategy.A.acct = "test"
        strategy.A.acct_type = "STOCK"
        strategy.A.last_portfolio_log_date = ""
        strategy.get_trade_detail_data = lambda *args: (
            [FakeAccount()] if args[-1] == "account" else []
        )
        context = FakeContext()
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                invoke("_backtest_snapshot", context)
                invoke("_backtest_snapshot", context)
                context.trade_day = "20251015"
                invoke("_backtest_snapshot", context)
            self.assertEqual(output.getvalue().count("PORTFOLIO"), 2)
        finally:
            if had_original_trade:
                strategy.get_trade_detail_data = original_trade
            else:
                delattr(strategy, "get_trade_detail_data")

    def test_backtest_snapshot_fallback_excludes_same_day_buys_from_available(self):
        class FakeHolding(object):
            market = "SZ"
            stockcode = "000001"
            trade_price = 9.50
            current_price = 10.00
            position = 1000

        class FakeDeal(object):
            market = "SZ"
            stockcode = "000001"
            open_close = 1
            position = 1000

        class FakeContext(object):
            capital = 1000000.0
            barpos = 20

            @staticmethod
            def get_net_value(index):
                if index != 20:
                    raise AssertionError("unexpected bar index")
                return 1.05

        original_trade = getattr(strategy, "get_trade_detail_data", None)
        had_original_trade = hasattr(strategy, "get_trade_detail_data")
        original_records = getattr(strategy, "get_result_records", None)
        had_original_records = hasattr(strategy, "get_result_records")
        strategy.A.mode = "BACKTEST"
        strategy.A.acct = "test"
        strategy.A.acct_type = "STOCK"

        def unavailable_trade_detail(*args):
            return []

        def fake_result_records(record_type, index, context):
            self.assertIn(record_type, ("holdings", "dealdetails"))
            self.assertEqual(index, 20)
            self.assertIsInstance(context, FakeContext)
            if record_type == "holdings":
                return [FakeHolding()]
            return [FakeDeal()]

        strategy.get_trade_detail_data = unavailable_trade_detail
        strategy.get_result_records = fake_result_records
        try:
            snapshot = invoke("_account_snapshot", FakeContext())
            self.assertEqual(snapshot["balance"], 1050000.0)
            self.assertEqual(snapshot["available_cash"], 1040000.0)
            self.assertEqual(
                snapshot["positions"],
                {"000001.SZ": {
                    "volume": 1000,
                    "available": 0,
                    "open_price": 9.50,
                    "current_price": 10.00,
                }},
            )
        finally:
            if had_original_trade:
                strategy.get_trade_detail_data = original_trade
            else:
                delattr(strategy, "get_trade_detail_data")
            if had_original_records:
                strategy.get_result_records = original_records
            else:
                delattr(strategy, "get_result_records")

    def test_backtest_snapshot_fallback_keeps_prior_day_shares_available(self):
        class FakeHolding(object):
            market = "SZ"
            stockcode = "000001"
            trade_price = 9.50
            current_price = 10.00
            position = 1500

        class FakeDeal(object):
            market = "SZ"
            stockcode = "000001"
            open_close = 1

            def __init__(self, trade_date, position):
                self.trade_date = trade_date
                self.position = position

        class FakeContext(object):
            capital = 1000000.0
            barpos = 20

            @staticmethod
            def get_net_value(index):
                return 1.0

            @staticmethod
            def get_bar_timetag(index):
                return "20251014103000"

        original_trade = getattr(strategy, "get_trade_detail_data", None)
        had_original_trade = hasattr(strategy, "get_trade_detail_data")
        original_records = getattr(strategy, "get_result_records", None)
        had_original_records = hasattr(strategy, "get_result_records")
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_original_timetag = hasattr(strategy, "timetag_to_datetime")
        strategy.A.mode = "BACKTEST"
        strategy.A.acct = "test"
        strategy.A.acct_type = "STOCK"
        strategy.get_trade_detail_data = lambda *args: []
        strategy.get_result_records = lambda record_type, *args: (
            [FakeHolding()] if record_type == "holdings" else [
                FakeDeal("20251013", 1000),
                FakeDeal("20251014", 500),
            ]
        )
        strategy.timetag_to_datetime = lambda value, fmt: str(value)[:8]
        try:
            snapshot = invoke("_account_snapshot", FakeContext())
            self.assertEqual(
                snapshot["positions"]["000001.SZ"]["available"], 1000
            )
        finally:
            if had_original_trade:
                strategy.get_trade_detail_data = original_trade
            else:
                delattr(strategy, "get_trade_detail_data")
            if had_original_records:
                strategy.get_result_records = original_records
            else:
                delattr(strategy, "get_result_records")
            if had_original_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_backtest_snapshot_falls_back_when_context_capital_is_invalid(self):
        class FakeContext(object):
            capital = -1.0
            barpos = 0

            @staticmethod
            def get_net_value(index):
                return 1.0

        original_records = getattr(strategy, "get_result_records", None)
        had_original_records = hasattr(strategy, "get_result_records")
        strategy.get_result_records = lambda *args: []
        try:
            snapshot = invoke("_backtest_snapshot", FakeContext())
            self.assertEqual(snapshot["balance"], 1000000.0)
            self.assertEqual(snapshot["available_cash"], 1000000.0)
        finally:
            if had_original_records:
                strategy.get_result_records = original_records
            else:
                delattr(strategy, "get_result_records")

    def test_history_fetch_is_chunked_and_never_subscribes(self):
        class FakeContext(object):
            def __init__(self):
                self.calls = []

            def get_market_data_ex(self, fields, stocks, **kwargs):
                self.calls.append((list(stocks), kwargs))
                return {code: pd.DataFrame({"close": [1.0]}) for code in stocks}

        context = FakeContext()
        result = invoke(
            "fetch_history", context, ["close"], ["A", "B", "C", "D", "E"],
            "1d", 20, "20260803", "none", 2,
        ) or {}
        self.assertEqual(sorted(result.keys()), ["A", "B", "C", "D", "E"])
        self.assertEqual([len(call[0]) for call in context.calls], [2, 2, 1])
        self.assertTrue(all(call[1]["subscribe"] is False for call in context.calls))

    def test_blocked_stock_is_not_reintroduced_by_exposure_resize(self):
        strategy.A.blocked_codes = {"000001.SZ"}
        snapshot = {"balance": 1000000.0}
        candidates = [{
            "code": "000001.SZ",
            "style": "000852.SH",
            "feature": {"close": 10.0},
        }]
        desired = invoke(
            "_desired_share_map", snapshot,
            {"000852.SH": 0.25}, candidates, {}
        ) or {}
        self.assertEqual(desired, {})

    def test_pending_order_codes_exclude_terminal_orders(self):
        class FakeOrder(object):
            def __init__(self, code, market, status):
                self.m_strInstrumentID = code
                self.m_strExchangeID = market
                self.m_nOrderStatus = status

        original = getattr(strategy, "get_trade_detail_data", None)
        had_original = hasattr(strategy, "get_trade_detail_data")
        strategy.A.mode = "SIMULATION"
        strategy.A.acct = "SIM001"
        strategy.A.acct_type = "STOCK"
        strategy.get_trade_detail_data = lambda *args: [
            FakeOrder("000001", "SZ", 50),
            FakeOrder("600000", "SH", 56),
        ]
        try:
            pending = invoke("_pending_order_codes") or set()
            self.assertEqual(pending, {"000001.SZ"})
        finally:
            if had_original:
                strategy.get_trade_detail_data = original
            else:
                delattr(strategy, "get_trade_detail_data")


if __name__ == "__main__":
    unittest.main()
