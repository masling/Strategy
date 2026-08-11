import importlib.util
import io
import datetime
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

    def test_regime_requires_two_days_to_open_and_strengthen(self):
        first = invoke("advance_style_regime", {"state": "OFF"}, 80.0)
        self.assertEqual(first["state"], "OFF")
        second = invoke("advance_style_regime", first, 80.0)
        self.assertEqual(second["state"], "WATCH")
        third = invoke("advance_style_regime", second, 90.0)
        self.assertEqual(third["state"], "WATCH")
        fourth = invoke("advance_style_regime", third, 90.0)
        self.assertEqual(fourth["state"], "STRONG")

    def test_strong_regime_exits_in_stages_after_persistent_weakness(self):
        state = {"state": "STRONG", "last_score": 90.0}
        state = invoke("advance_style_regime", state, 60.0)
        self.assertEqual(state["state"], "STRONG")
        self.assertEqual(
            invoke("style_risk_cap_map", {"S": state}), {"S": 0.30}
        )
        state = invoke("advance_style_regime", state, 60.0)
        self.assertEqual(state["state"], "WATCH")
        self.assertEqual(
            invoke("style_risk_cap_map", {"S": state}), {"S": 0.15}
        )
        state = invoke("advance_style_regime", state, 60.0)
        self.assertEqual(state["state"], "WATCH")
        state = invoke("advance_style_regime", state, 60.0)
        self.assertEqual(state["state"], "OFF")

    def test_risk_caps_reduce_exposure_without_forcing_immediate_zero(self):
        reduced = invoke(
            "apply_style_risk_caps",
            {"000300.SH": 0.60, "399006.SZ": 0.20},
            {"000300.SH": 0.30, "399006.SZ": 0.15},
        ) or {}
        self.assertEqual(reduced, {
            "000300.SH": 0.30, "399006.SZ": 0.15,
        })

    def test_one_strong_style_with_three_active_sectors_reaches_sixty_percent(self):
        budgets = invoke(
            "sector_rotation_exposure_map",
            {"000300.SH": 100.0},
            {"000300.SH": [
                {"score": 85.0}, {"score": 75.0}, {"score": 70.0},
            ]},
        ) or {}
        self.assertEqual(budgets, {"000300.SH": 0.60})

    def test_isolated_strong_sector_concentrates_sixty_percent(self):
        sectors = {"000852.SH": [{
            "member_sector": "SW1电子", "score": 82.0,
        }]}
        focus = invoke(
            "isolated_sector_focus", {"000852.SH": 95.0}, sectors
        ) or {}
        self.assertEqual(focus["sector"], "SW1电子")
        self.assertEqual(focus["exposure"], 0.60)
        self.assertEqual(invoke(
            "sector_rotation_exposure_map",
            {"000852.SH": 95.0}, sectors,
        ), {"000852.SH": 0.60})

    def test_isolated_moderate_sector_uses_thirty_percent(self):
        sectors = {"000905.SH": [{
            "member_sector": "SW1机械设备", "score": 68.0,
        }]}
        focus = invoke(
            "isolated_sector_focus", {"000905.SH": 80.0}, sectors
        ) or {}
        self.assertEqual(focus["exposure"], 0.30)

    def test_duplicate_sector_across_styles_is_counted_once(self):
        sectors = {
            "000905.SH": [{"member_sector": "SW1通信", "score": 80.0}],
            "000852.SH": [{"member_sector": "SW1通信", "score": 78.0}],
        }
        budgets = invoke(
            "sector_rotation_exposure_map",
            {"000905.SH": 90.0, "000852.SH": 95.0}, sectors,
        ) or {}
        self.assertEqual(budgets, {"000852.SH": 0.60})

    def test_two_comparable_sectors_do_not_trigger_isolated_focus(self):
        sectors = {"000300.SH": [
            {"member_sector": "SW1电子", "score": 80.0},
            {"member_sector": "SW1通信", "score": 72.0},
        ]}
        self.assertIsNone(invoke(
            "isolated_sector_focus", {"000300.SH": 95.0}, sectors
        ))

    def test_watch_style_exposure_follows_active_sector_count(self):
        budgets = invoke(
            "sector_rotation_exposure_map",
            {"000300.SH": 75.0},
            {"000300.SH": [{"score": 80.0}, {"score": 65.0}]},
        ) or {}
        self.assertEqual(budgets, {"000300.SH": 0.30})

    def test_style_without_active_sector_has_no_exposure(self):
        budgets = invoke(
            "sector_rotation_exposure_map",
            {"000300.SH": 100.0}, {"000300.SH": []},
        ) or {}
        self.assertEqual(budgets, {})

    def test_sector_driven_style_budgets_keep_eighty_percent_total_cap(self):
        budgets = invoke(
            "sector_rotation_exposure_map",
            {"000300.SH": 100.0, "399006.SZ": 100.0},
            {
                "000300.SH": [{"score": 80.0}] * 3,
                "399006.SZ": [{"score": 80.0}] * 3,
            },
        ) or {}
        self.assertAlmostEqual(sum(budgets.values()), 0.80)
        self.assertEqual(budgets, {"000300.SH": 0.4, "399006.SZ": 0.4})

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
        strategy.A.style_regimes = {
            code: {"state": "OFF"} for code, _ in strategy.STYLE_INDEXES
        }
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
        self.assertTrue({"open", "high", "low", "close", "amount"}.issubset(proxy.columns))
        self.assertTrue((proxy["high"] >= proxy[["open", "close"]].max(axis=1)).all())
        self.assertTrue((proxy["low"] <= proxy[["open", "close"]].min(axis=1)).all())
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
                    close = 100.0 * np.power(1.005, np.arange(70))
                    self.history[code] = pd.DataFrame({
                        "open": close * 0.998,
                        "high": close * 1.006,
                        "low": close * 0.994,
                        "close": close,
                        "amount": np.repeat(100000000.0, 70),
                    })
                for code in self.members["SW1银行"]:
                    close = 100.0 * np.power(0.998, np.arange(70))
                    self.history[code] = pd.DataFrame({
                        "open": close * 1.002,
                        "high": close * 1.006,
                        "low": close * 0.994,
                        "close": close,
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

    def test_liquidity_ignores_suspended_and_limit_days(self):
        frame = self.make_frame(amount=100000000.0).iloc[-25:].copy()
        frame.loc[frame.index[-8:-5], "suspendFlag"] = 1.0
        frame.loc[frame.index[-8:-5], "amount"] = 1000000.0
        limit_index = frame.index[-10]
        previous_index = frame.index[-11]
        frame.loc[limit_index, "close"] = (
            frame.loc[previous_index, "close"] * 1.10
        )
        frame.loc[limit_index, "amount"] = 1000000.0
        metrics = invoke(
            "effective_amount_metrics", frame, "000001.SZ"
        )
        self.assertAlmostEqual(metrics[0], 100000000.0)
        self.assertEqual(metrics[3], 16)

    def test_liquidity_requires_enough_normal_trading_days(self):
        frame = self.make_frame(amount=100000000.0)
        frame.loc[frame.index[-20:-9], "suspendFlag"] = 1.0
        feature = invoke(
            "stock_feature", frame, 0.01, 0.03,
            50000000.0, False, "000001.SZ",
        )
        self.assertIsNone(feature)

    def test_stock_feature_rejects_flat_ma7_after_prior_rally(self):
        close = np.concatenate([np.linspace(80.0, 125.0, 118),
                                np.repeat(130.0, 12)])
        frame = pd.DataFrame({
            "close": close, "high": close * 1.01, "low": close * 0.99,
            "amount": np.repeat(100000000.0, len(close)),
            "volume": np.repeat(1000000.0, len(close)),
            "suspendFlag": np.zeros(len(close)),
        })
        self.assertIsNone(invoke("stock_feature", frame, 0.01, 0.03))

    def test_watchlist_keeps_strong_stock_without_current_entry_setup(self):
        close = np.concatenate([np.linspace(80.0, 125.0, 118),
                                np.repeat(130.0, 12)])
        frame = pd.DataFrame({
            "close": close, "high": close * 1.01, "low": close * 0.99,
            "amount": np.repeat(100000000.0, len(close)),
            "volume": np.repeat(1000000.0, len(close)),
            "suspendFlag": np.zeros(len(close)),
        })
        feature = invoke(
            "stock_feature", frame, 0.01, 0.03, 50000000.0, False
        )
        self.assertIsNotNone(feature)
        self.assertIsNone(feature["entry_setup"])

    def test_held_candidate_is_retained_when_rank_falls_out(self):
        previous = [{
            "code": "A", "style": "S1", "score": 80.0,
            "entry_ready": True,
        }]
        retained = invoke(
            "retain_held_watch_candidates", [], previous, {"A"}, {"S1"}
        ) or []
        self.assertEqual([item["code"] for item in retained], ["A"])
        self.assertFalse(retained[0]["entry_ready"])
        self.assertTrue(retained[0]["held_retained"])

    def test_stock_feature_rejects_price_far_above_ma40(self):
        close = np.concatenate([np.linspace(60.0, 80.0, 110),
                                np.linspace(82.0, 125.0, 20)])
        frame = pd.DataFrame({
            "close": close, "high": close * 1.01, "low": close * 0.99,
            "amount": np.repeat(100000000.0, len(close)),
            "volume": np.repeat(1000000.0, len(close)),
            "suspendFlag": np.zeros(len(close)),
        })
        self.assertIsNone(invoke("stock_feature", frame, 0.01, 0.03))

    def test_daily_refresh_preserves_softly_ineligible_reserve_name(self):
        close = np.concatenate([np.linspace(60.0, 80.0, 110),
                                np.linspace(82.0, 125.0, 20)])
        frame = pd.DataFrame({
            "close": close, "high": close * 1.01, "low": close * 0.99,
            "amount": np.repeat(100000000.0, len(close)),
            "volume": np.repeat(1000000.0, len(close)),
            "suspendFlag": np.zeros(len(close)),
        })
        feature = invoke(
            "stock_feature", frame, 0.01, 0.03,
            50000000.0, False, "000001.SZ", False,
        )
        self.assertIsNotNone(feature)
        self.assertFalse(feature["selection_eligible"])

    def test_trend_entry_rejects_price_more_than_four_percent_above_ma7(self):
        setup = invoke("entry_setup_kind", {
            "close": 108.0, "low": 105.0, "previous_high": 107.0,
            "ma7": 100.0, "ma13": 98.0, "ma40": 92.0,
            "ma13_prev": 96.0, "ma40_prev": 90.0,
            "ma7_slope3": 0.02, "ma13_slope3": 0.01,
            "distance_ma40": 108.0 / 92.0 - 1.0,
            "ma7_ma13_gap": 100.0 / 98.0 - 1.0,
            "ma13_ma40_gap": 98.0 / 92.0 - 1.0,
        })
        self.assertIsNone(setup)

    def test_shanghai_xinyang_september_entry_rejects_ma7_rollover(self):
        setup = invoke("entry_setup_kind", {
            "close": 55.682, "low": 54.622, "previous_high": 59.022,
            "ma7": 55.642, "ma7_prev1": 55.419, "ma7_prev2": 55.479,
            "ma13": 53.501, "ma40": 50.0,
            "ma13_prev": 51.8, "ma40_prev": 49.5,
            "ma7_slope3": 0.025, "ma13_slope3": 0.02,
            "distance_ma40": 55.682 / 50.0 - 1.0,
            "ma7_ma13_gap": 55.642 / 53.501 - 1.0,
            "ma13_ma40_gap": 53.501 / 50.0 - 1.0,
        })
        self.assertIsNone(setup)

    def test_shanghai_xinyang_october_entry_rejects_ma40_distance(self):
        setup = invoke("entry_setup_kind", {
            "close": 61.672, "low": 60.672, "previous_high": 63.312,
            "ma7": 61.229, "ma7_prev1": 60.298, "ma7_prev2": 59.185,
            "ma13": 57.680, "ma40": 53.125,
            "ma13_prev": 55.8, "ma40_prev": 51.5,
            "ma7_slope3": 0.05, "ma13_slope3": 0.03,
            "distance_ma40": 61.672 / 53.125 - 1.0,
            "ma7_ma13_gap": 61.229 / 57.680 - 1.0,
            "ma13_ma40_gap": 57.680 / 53.125 - 1.0,
        })
        self.assertIsNone(setup)

    def test_shengtun_september_5_rejects_expanded_ma7_ma13_gap(self):
        setup = invoke("entry_setup_kind", {
            "close": 8.702, "low": 8.332, "previous_high": 9.042,
            "ma7": 8.628, "ma7_prev1": 8.505, "ma7_prev2": 8.456,
            "ma13": 8.292, "ma40": 7.835,
            "ma13_prev": 8.05, "ma40_prev": 7.75,
            "ma7_slope3": 0.02, "ma13_slope3": 0.012,
            "distance_ma40": 8.702 / 7.835 - 1.0,
            "ma7_ma13_gap": 8.628 / 8.292 - 1.0,
            "ma13_ma40_gap": 8.292 / 7.835 - 1.0,
        })
        self.assertIsNone(setup)

    def test_shengtun_september_26_rejects_falling_ma7_starter(self):
        setup = invoke("entry_setup_kind", {
            "close": 8.962, "low": 8.512, "previous_high": 8.702,
            "ma7": 8.359, "ma7_prev1": 8.315, "ma7_prev2": 8.338,
            "ma13": 8.517, "ma40": 8.244,
            "ma13_prev": 8.558, "ma40_prev": 8.169,
            "ma7_slope3": -0.0051, "ma13_slope3": -0.0048,
            "distance_ma40": 8.962 / 8.244 - 1.0,
            "ma7_ma13_gap": 8.359 / 8.517 - 1.0,
            "ma13_ma40_gap": 8.517 / 8.244 - 1.0,
        })
        self.assertIsNone(setup)

    def test_flowing_trend_requires_normalized_gap_and_slope_alignment(self):
        setup = invoke("entry_setup_kind", {
            "close": 105.0, "low": 103.0, "previous_high": 104.0,
            "ma7": 101.2, "ma7_prev1": 100.8, "ma7_prev2": 100.4,
            "ma13": 100.5, "ma40": 97.5,
            "ma13_prev": 99.8, "ma40_prev": 96.8,
            "ma7_slope3": 0.015, "ma13_slope3": 0.009,
            "ma40_slope5": 0.0072,
            "distance_ma40": 105.0 / 97.5 - 1.0,
            "ma7_ma13_gap": 101.2 / 100.5 - 1.0,
            "ma13_ma40_gap": 100.5 / 97.5 - 1.0,
        })
        self.assertEqual(setup, "trend")

    def test_trend_rejects_short_gap_when_ma13_ma40_is_overextended(self):
        setup = invoke("entry_setup_kind", {
            "close": 105.0, "low": 103.0, "previous_high": 104.0,
            "ma7": 101.0, "ma7_prev1": 100.4, "ma7_prev2": 99.8,
            "ma13": 100.0, "ma40": 90.0,
            "ma13_prev": 99.3, "ma40_prev": 89.4,
            "ma7_slope3": 0.015, "ma13_slope3": 0.009,
            "ma40_slope5": 0.0072,
            "distance_ma40": 105.0 / 90.0 - 1.0,
            "ma7_ma13_gap": 101.0 / 100.0 - 1.0,
            "ma13_ma40_gap": 100.0 / 90.0 - 1.0,
        })
        self.assertIsNone(setup)

    def test_ma40_starter_needs_ma7_turn_and_flat_to_rising_ma13(self):
        setup = invoke("entry_setup_kind", {
            "close": 104.0, "low": 98.5, "previous_high": 103.0,
            "ma7": 100.3, "ma7_prev1": 100.0, "ma7_prev2": 100.2,
            "ma13": 100.0, "ma40": 97.0,
            "ma13_prev": 99.8, "ma40_prev": 96.6,
            "ma7_slope3": -0.001, "ma13_slope3": 0.003,
            "ma40_slope5": 0.0041,
            "distance_ma40": 104.0 / 97.0 - 1.0,
            "ma7_ma13_gap": 100.3 / 100.0 - 1.0,
            "ma13_ma40_gap": 100.0 / 97.0 - 1.0,
        })
        self.assertEqual(setup, "ma40_starter")

    def test_ma7_pullback_enters_small_when_opening_is_still_widening(self):
        setup = invoke("entry_setup_kind", {
            "close": 102.0, "low": 101.8, "previous_high": 103.0,
            "ma7": 101.5, "ma7_prev1": 101.0, "ma7_prev2": 100.6,
            "ma13": 100.0, "ma13_prev1": 99.7, "ma13_prev": 99.2,
            "ma40": 92.0, "ma40_prev": 91.4,
            "ma7_slope3": 0.012, "ma13_slope3": 0.009,
            "ma40_slope5": 0.006,
            "distance_ma40": 102.0 / 92.0 - 1.0,
            "ma7_ma13_gap": 101.5 / 100.0 - 1.0,
            "ma13_ma40_gap": 100.0 / 92.0 - 1.0,
        })
        self.assertEqual(setup, "ma7_pullback")
        self.assertLess(invoke("entry_setup_scale", setup), 1.0)

    def test_ma13_rebound_enters_small_after_same_day_recovery(self):
        setup = invoke("entry_setup_kind", {
            "close": 100.5, "low": 100.3, "previous_high": 102.0,
            "ma7": 102.5, "ma7_prev1": 102.4, "ma7_prev2": 102.2,
            "ma13": 100.0, "ma13_prev1": 99.8, "ma13_prev": 99.1,
            "ma40": 91.7, "ma40_prev": 91.2,
            "ma7_slope3": 0.002, "ma13_slope3": 0.009,
            "ma40_slope5": 0.005,
            "distance_ma40": 100.5 / 91.7 - 1.0,
            "ma7_ma13_gap": 102.5 / 100.0 - 1.0,
            "ma13_ma40_gap": 100.0 / 91.7 - 1.0,
        })
        self.assertEqual(setup, "ma13_rebound")

    def test_bottom_cross_starter_is_only_below_ma13_entry_exception(self):
        setup = invoke("entry_setup_kind", {
            "close": 99.8, "low": 98.9, "previous_high": 99.5,
            "ma7": 99.6, "ma7_prev1": 99.0, "ma7_prev2": 98.5,
            "ma13": 100.5, "ma13_prev1": 100.6, "ma13_prev": 100.8,
            "ma40": 96.0, "ma40_prev": 95.9,
            "ma7_slope3": 0.008, "ma13_slope3": -0.001,
            "ma40_slope5": 0.001,
            "distance_ma40": 99.8 / 96.0 - 1.0,
            "ma7_ma13_gap": 99.6 / 100.5 - 1.0,
            "ma13_ma40_gap": 100.5 / 96.0 - 1.0,
        })
        self.assertEqual(setup, "bottom_cross_starter")
        self.assertLess(invoke("entry_setup_scale", setup), 0.35)

    def test_bottom_cross_starter_completes_only_after_ma13_reclaim(self):
        metrics = {
            "close": 101.0, "ma7": 100.0, "ma13": 100.5,
            "ma40": 96.0, "ma7_slope3": 0.008,
            "ma13_slope3": -0.001,
        }
        self.assertEqual(
            invoke("trend_add_signal", metrics, 2, "bottom_cross_starter"),
            "ma13_reclaim",
        )

    def test_pullback_build_adds_on_recent_high_breakout(self):
        metrics = {
            "close": 106.5, "low": 104.5, "previous_high": 105.0,
            "previous_peak_price": 105.8,
            "ma7": 102.0, "ma13": 99.5, "ma40": 95.0,
            "ma7_slope3": 0.012, "ma13_slope3": 0.008,
        }
        self.assertEqual(
            invoke("trend_add_signal", metrics, 3, "ma7_pullback"),
            "breakout",
        )

    def test_shanghai_xinyang_starter_rejects_ma7_falling_toward_ma13(self):
        setup = invoke("entry_setup_kind", {
            "close": 61.95, "low": 59.9, "previous_high": 61.2,
            "ma7": 60.8, "ma7_prev1": 61.4, "ma7_prev2": 62.0,
            "ma13": 60.2, "ma40": 57.8,
            "ma13_prev": 60.0, "ma40_prev": 57.2,
            "ma7_slope3": -0.010, "ma13_slope3": 0.003,
            "ma40_slope5": 0.005,
            "distance_ma40": 61.95 / 57.8 - 1.0,
            "ma7_ma13_gap": 60.8 / 60.2 - 1.0,
            "ma13_ma40_gap": 60.2 / 57.8 - 1.0,
        })
        self.assertIsNone(setup)

    def test_entry_structure_score_prefers_smooth_lower_position(self):
        smooth = {
            "distance_ma40": 0.12, "distance_ma13": 0.03,
            "ma7_ma13_gap": 0.025, "ma13_ma40_gap": 0.08,
            "ma7_slope3": 0.012, "ma13_slope3": 0.008,
        }
        high = {
            "distance_ma40": 0.24, "distance_ma13": 0.11,
            "ma7_ma13_gap": 0.08, "ma13_ma40_gap": 0.04,
            "ma7_slope3": 0.003, "ma13_slope3": 0.002,
        }
        self.assertGreater(
            invoke("entry_structure_score", smooth),
            invoke("entry_structure_score", high),
        )

    def test_tinci_april_10_rejects_unconfirmed_ma7_reversal(self):
        setup = invoke("entry_setup_kind", {
            "close": 46.421, "low": 43.551, "previous_high": 45.101,
            "ma7": 44.46, "ma13": 44.69, "ma40": 43.54,
            "ma13_prev": 44.1, "ma40_prev": 43.2,
            "ma7_slope3": -0.0148, "ma13_slope3": 0.0142,
            "distance_ma40": 46.421 / 43.54 - 1.0,
            "ma7_ma13_gap": 44.46 / 44.69 - 1.0,
            "ma13_ma40_gap": 44.69 / 43.54 - 1.0,
        })
        self.assertIsNone(setup)

    def test_tinci_april_24_ma13_reversal_activates_trend_add(self):
        metrics = {
            "close": 52.741, "low": 48.301, "previous_high": 52.081,
            "ma7": 50.41, "ma13": 48.52, "ma40": 45.52,
            "ma7_slope3": 0.0306, "ma13_slope3": 0.0371,
        }
        self.assertTrue(invoke("trend_add_ready", metrics, 10))

    def test_salt_lake_december_17_rejects_declining_ma13_starter(self):
        setup = invoke("entry_setup_kind", {
            "close": 26.98, "low": 25.67, "previous_high": 25.28,
            "ma7": 25.49, "ma13": 25.62, "ma40": 25.52,
            "ma13_prev": 25.8, "ma40_prev": 25.4,
            "ma7_slope3": 0.001, "ma13_slope3": -0.007,
            "distance_ma40": 26.98 / 25.52 - 1.0,
            "ma7_ma13_gap": 25.49 / 25.62 - 1.0,
            "ma13_ma40_gap": 25.62 / 25.52 - 1.0,
        })
        self.assertIsNone(setup)

    def test_salt_lake_december_31_adds_near_ma7(self):
        metrics = {
            "close": 28.16, "low": 27.98, "previous_high": 28.04,
            "ma7": 28.25, "ma13": 27.41, "ma40": 26.46,
            "ma7_slope3": 0.0099, "ma13_slope3": 0.0206,
            "ma7_prev1": 28.253, "recent_pullback": 0.067,
        }
        self.assertEqual(
            invoke("trend_add_signal", metrics, 8, "ma40_starter"),
            "ma7",
        )

    def test_shallow_ma7_touch_does_not_trigger_add(self):
        metrics = {
            "close": 10.4, "low": 10.0, "previous_high": 10.3,
            "ma7": 10.0, "ma7_prev1": 9.98,
            "ma13": 9.5, "ma40": 9.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_pullback": 0.03,
        }
        self.assertIsNone(
            invoke("trend_add_signal", metrics, 5, "ma40_starter")
        )

    def test_ma13_touch_has_priority_when_both_supports_are_near(self):
        metrics = {
            "close": 10.3, "low": 10.0, "previous_high": 10.2,
            "ma7": 10.1, "ma7_prev1": 10.0,
            "ma13": 9.95, "ma40": 9.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_pullback": 0.08,
        }
        self.assertEqual(
            invoke("trend_add_signal", metrics, 5, "ma40_starter"),
            "ma13",
        )

    def test_ma7_add_waits_for_ma13_when_short_gap_is_too_small(self):
        metrics = {
            "close": 10.5, "low": 10.3, "previous_high": 10.4,
            "ma7": 10.3, "ma7_prev1": 10.2,
            "ma13": 10.0, "ma40": 8.5,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_pullback": 0.08,
        }
        self.assertIsNone(
            invoke("trend_add_signal", metrics, 5, "ma40_starter")
        )

    def test_salt_lake_february_24_rejects_unbalanced_base_reclaim(self):
        setup = invoke("entry_setup_kind", {
            "close": 35.66, "low": 34.51, "previous_high": 33.91,
            "ma7": 33.65, "ma13": 33.28, "ma40": 32.22,
            "ma13_prev": 33.5, "ma40_prev": 31.9,
            "ma7_slope3": 0.021, "ma13_slope3": -0.006,
            "distance_ma40": 35.66 / 32.22 - 1.0,
            "ma7_ma13_gap": 33.65 / 33.28 - 1.0,
            "ma13_ma40_gap": 33.28 / 32.22 - 1.0,
        })
        self.assertIsNone(setup)

    def test_secondary_base_can_complete_on_immediate_resume(self):
        metrics = {
            "close": 36.20, "low": 35.72, "previous_high": 35.83,
            "ma7": 34.19, "ma13": 33.43, "ma40": 32.44,
            "ma7_slope3": 0.034, "ma13_slope3": 0.003,
        }
        self.assertEqual(
            invoke("trend_add_signal", metrics, 1, "base_reclaim"),
            "resume",
        )

    def test_secondary_base_does_not_chase_resume_after_three_days(self):
        metrics = {
            "close": 36.20, "low": 35.72, "previous_high": 35.83,
            "ma7": 34.19, "ma13": 33.43, "ma40": 32.44,
            "ma7_slope3": 0.034, "ma13_slope3": 0.003,
        }
        self.assertIsNone(
            invoke("trend_add_signal", metrics, 4, "base_reclaim")
        )

    def test_position_metrics_remain_available_after_trend_break(self):
        frame = self.make_frame(last_close=130.0)
        frame.loc[frame.index[-1], "close"] = 100.0
        metrics = invoke("position_metrics", frame)
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["close"], 100.0)
        self.assertIn("ma13", metrics)
        self.assertIn("ma40", metrics)
        self.assertGreater(metrics["atr"], 0.0)

    def test_position_metrics_are_converted_to_raw_price_coordinate(self):
        adjusted = {
            "close": 934.0, "high": 950.0, "low": 910.0,
            "previous_high": 940.0,
            "ma7": 925.0, "ma7_prev1": 920.0,
            "ma13": 900.0, "ma40": 850.0,
            "recent_peak_price": 960.0, "atr": 28.0,
            "ma7_slope3": 0.02, "ma13_slope3": 0.01,
        }
        raw = invoke(
            "position_metrics_in_raw_coordinate", adjusted, 20.0
        ) or {}
        factor = 20.0 / 934.0
        self.assertAlmostEqual(raw["close"], 20.0)
        self.assertAlmostEqual(raw["ma7"], 925.0 * factor)
        self.assertAlmostEqual(raw["ma13"], 900.0 * factor)
        self.assertAlmostEqual(raw["ma40"], 850.0 * factor)
        self.assertAlmostEqual(raw["atr"], 28.0 * factor)
        self.assertAlmostEqual(raw["ma7_slope3"], 0.02)
        self.assertAlmostEqual(raw["raw_per_adjusted"], factor)

    def test_position_coordinate_conversion_rejects_missing_raw_close(self):
        self.assertIsNone(invoke(
            "position_metrics_in_raw_coordinate", {"close": 934.0}, 0.0
        ))

    def test_select_stocks_enforces_two_names_per_sector(self):
        candidates = [
            {"code": "A", "sector": "S1", "score": 100.0},
            {"code": "B", "sector": "S1", "score": 90.0},
            {"code": "C", "sector": "S1", "score": 80.0},
            {"code": "D", "sector": "S2", "score": 70.0},
        ]
        selected = invoke("select_stocks", candidates, 6, 2) or []
        self.assertEqual([item["code"] for item in selected], ["A", "B", "D"])

    def test_cross_sectional_stock_score_prefers_better_entry_timing(self):
        candidates = [
            {"code": "A", "sector": "S1", "feature": {
                "rs13": 0.10, "rs40": 0.20, "r13": 0.15,
                "high_proximity": 0.98, "average_amount": 200000000.0,
                "volatility": 0.01, "amount_ratio5": 1.0,
                "close": 10.2, "low": 9.95, "ma7": 10.1,
                "ma13": 10.0, "ma40": 9.3,
                "distance_ma40": 10.2 / 9.3 - 1.0,
                "distance_ma13": 0.02, "ma7_ma13_gap": 0.01,
                "ma13_ma40_gap": 10.0 / 9.3 - 1.0,
                "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            }},
            {"code": "B", "sector": "S2", "feature": {
                "rs13": 0.02, "rs40": 0.04, "r13": 0.05,
                "high_proximity": 0.90, "average_amount": 60000000.0,
                "volatility": 0.03, "amount_ratio5": 1.0,
                "close": 12.0, "low": 11.7, "ma7": 10.0,
                "ma13": 9.8, "ma40": 9.0,
                "distance_ma40": 12.0 / 9.0 - 1.0,
                "distance_ma13": 12.0 / 9.8 - 1.0,
                "ma7_ma13_gap": 10.0 / 9.8 - 1.0,
                "ma13_ma40_gap": 9.8 / 9.0 - 1.0,
                "ma7_slope3": 0.02, "ma13_slope3": 0.012,
            }},
        ]
        scored = invoke("score_stock_candidates", candidates) or []
        self.assertEqual([item["code"] for item in scored], ["A", "B"])
        self.assertGreater(scored[0]["score"], scored[1]["score"])

    def test_watchlist_score_is_recomputed_instead_of_reusing_old_score(self):
        candidates = [
            {"code": "A", "style": "S1", "score": 1.0,
             "sector": "X", "feature": {
                 "rs13": 0.10, "rs40": 0.20, "r13": 0.15,
                 "high_proximity": 0.98, "average_amount": 200000000.0,
                 "volatility": 0.01, "distance_ma40": 0.08,
                 "distance_ma13": 0.02, "ma7_ma13_gap": 0.02,
                 "ma13_ma40_gap": 0.08, "ma7_slope3": 0.012,
                 "ma13_slope3": 0.008, "amount_ratio5": 1.0,
                 "close": 10.2, "low": 9.95, "ma7": 10.1,
                 "ma13": 10.0, "ma40": 9.3,
             }},
            {"code": "B", "style": "S1", "score": 99.0,
             "sector": "Y", "feature": {
                 "rs13": 0.01, "rs40": 0.02, "r13": 0.03,
                 "high_proximity": 0.86, "average_amount": 60000000.0,
                 "volatility": 0.04, "distance_ma40": 0.20,
                 "distance_ma13": 0.10, "ma7_ma13_gap": 0.07,
                 "ma13_ma40_gap": 0.03, "ma7_slope3": 0.002,
                 "ma13_slope3": 0.001, "amount_ratio5": 1.0,
                 "close": 12.0, "low": 11.7, "ma7": 10.0,
                 "ma13": 9.8, "ma40": 9.0,
             }},
        ]
        rescored = invoke(
            "score_watch_candidates_by_style", candidates
        ) or []
        self.assertEqual([item["code"] for item in rescored], ["A", "B"])
        self.assertGreater(rescored[0]["score"], rescored[1]["score"])

    def test_entry_requires_absolute_score_floor(self):
        base = {"feature": {
            "entry_setup": "trend", "raw_signal_close": 10.0,
            "amount_ratio5": 1.0,
        }}
        low = dict(base, entry_score=64.99, strength_score=70.0, score=80.0)
        ready = dict(base, entry_score=65.0, strength_score=70.0, score=65.0)
        wait = {"score": 90.0, "feature": {
            "entry_setup": None, "raw_signal_close": 10.0,
            "amount_ratio5": 1.0,
        }}
        self.assertEqual(
            invoke("entry_candidate_status", low), "LOW_ENTRY_SCORE"
        )
        self.assertEqual(invoke("entry_candidate_status", ready), "READY")
        self.assertEqual(invoke("entry_candidate_status", wait), "WAIT")

    def test_entry_strength_fit_peaks_near_seventy(self):
        self.assertEqual(invoke("entry_strength_fit_score", 70.0), 100.0)
        self.assertGreater(
            invoke("entry_strength_fit_score", 70.0),
            invoke("entry_strength_fit_score", 60.0),
        )
        self.assertGreater(
            invoke("entry_strength_fit_score", 70.0),
            invoke("entry_strength_fit_score", 80.0),
        )
        self.assertEqual(
            invoke("entry_strength_fit_score", 60.0),
            invoke("entry_strength_fit_score", 80.0),
        )
        self.assertEqual(invoke("entry_strength_fit_score", 95.0), 0.0)

    def test_entry_rejects_overpowered_or_lagging_strength(self):
        base = {
            "score": 80.0, "entry_score": 80.0,
            "feature": {
                "entry_setup": "trend", "raw_signal_close": 10.0,
                "amount_ratio5": 1.0,
            },
        }
        lagging = dict(base, strength_score=30.0)
        overpowered = dict(base, strength_score=95.0)
        self.assertEqual(
            invoke("entry_candidate_status", lagging), "LOW_STRENGTH"
        )
        self.assertEqual(
            invoke("entry_candidate_status", overpowered), "OVERPOWERED"
        )

    def test_entry_score_penalizes_overextended_strong_stock(self):
        near = {
            "close": 10.2, "low": 9.95,
            "ma7": 10.1, "ma13": 10.0, "ma40": 9.3,
            "distance_ma7": 10.2 / 10.1 - 1.0,
            "distance_ma13": 0.02,
            "distance_ma40": 10.2 / 9.3 - 1.0,
            "ma7_ma13_gap": 0.01, "ma13_ma40_gap": 10.0 / 9.3 - 1.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "average_amount": 200000000.0, "amount_ratio5": 1.0,
        }
        extended = dict(near)
        extended.update({
            "close": 12.0, "low": 11.7,
            "distance_ma7": 12.0 / 10.1 - 1.0,
            "distance_ma13": 0.20,
            "distance_ma40": 12.0 / 9.3 - 1.0,
        })
        self.assertGreater(
            invoke("entry_opportunity_score", near),
            invoke("entry_opportunity_score", extended),
        )
        self.assertEqual(
            invoke("participation_wait_reason", extended),
            "OVEREXTENDED",
        )

    def test_entry_waits_for_normal_recent_turnover(self):
        feature = {
            "entry_setup": "trend", "distance_ma7": 0.01,
            "distance_ma13": 0.03, "distance_ma40": 0.10,
            "amount_ratio5": 3.0,
        }
        self.assertEqual(
            invoke("participation_wait_reason", feature), "VOLUME_WAIT"
        )

    def test_overextended_names_do_not_occupy_actionable_watch_slots(self):
        candidates = []
        for index in range(14):
            status = "OVEREXTENDED" if index < 8 else "WAIT"
            candidates.append({
                "code": "C%02d" % index, "style": "S1", "sector": "X",
                "score": 100.0 - index,
                "strength_score": 80.0 - index,
                "strength_fit_score": 70.0,
                "entry_score": 80.0 - index,
                "entry_status": status,
            })
        selected, spectators = invoke(
            "select_actionable_watch_candidates", candidates
        )
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(
            item["entry_status"] != "OVEREXTENDED" for item in selected
        ))
        self.assertTrue(all(
            item["entry_status"] == "OVEREXTENDED" for item in spectators
        ))

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

    def test_sector_ma40_break_exits_immediately(self):
        reason = invoke(
            "exit_reason", 104.0, 105.0, 100.0, 95.0, 3.0, 100.0,
            0, True, 0.25, sector_ma40_broken=True,
        )
        self.assertEqual(reason, "sector_ma40_break")

    def test_no_ma13_rebound_reduces_after_second_break_day(self):
        reason = invoke(
            "exit_reason", 99.0, 99.2, 100.0, 95.0, 3.0, 100.0,
            1, True, 0.25,
        )
        self.assertEqual(reason, "ma13_no_rebound_reduce")

    def test_ma13_break_exits_only_after_third_unrecovered_day(self):
        reason = invoke(
            "exit_reason", 99.0, 100.2, 100.0, 95.0, 3.0, 100.0,
            2, True, 0.25,
        )
        self.assertEqual(reason, "ma13_break")

    def test_target_shares_rounds_down_to_board_lot(self):
        shares = invoke(
            "target_shares", total_asset=1000000.0, exposure=0.80,
            position_count=6, price=20.0, max_weight=0.15,
        )
        self.assertEqual(shares, 6600)

    def test_style_budget_is_divided_only_inside_that_style(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {}
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
        strategy.A.entry_scales = {}
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

    def test_ma40_starter_uses_half_sized_initial_position(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {"A": 0.5}
        desired = invoke(
            "_desired_share_map", {"balance": 1000000.0}, {"S1": 0.25},
            [{"code": "A", "style": "S1", "feature": {"close": 10.0}}],
            {}, {"A": 10.0},
        )
        self.assertEqual(desired, {"A": 7500})

    def test_four_names_can_realize_sixty_percent_rotation_exposure(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {}
        candidates = [
            {"code": code, "style": "S1", "feature": {"close": 10.0}}
            for code in ("A", "B", "C", "D")
        ]
        desired = invoke(
            "_desired_share_map", {"balance": 1000000.0}, {"S1": 0.60},
            candidates, {}, {code: 10.0 for code in ("A", "B", "C", "D")},
        ) or {}
        self.assertEqual(
            desired, {"A": 15000, "B": 15000, "C": 15000, "D": 15000}
        )

    def test_unready_watch_name_is_not_bought_but_existing_holding_is_kept(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {}
        snapshot = {
            "balance": 1000000.0,
            "positions": {"HELD": {"volume": 10000}},
        }
        candidates = [
            {"code": "HELD", "style": "S1", "score": 70.0,
             "entry_ready": False, "feature": {"close": 10.0}},
            {"code": "WAIT", "style": "S1", "score": 90.0,
             "entry_ready": False, "feature": {"close": 10.0}},
            {"code": "READY", "style": "S1", "score": 80.0,
             "entry_ready": True, "feature": {"close": 10.0}},
        ]
        desired = invoke(
            "_desired_share_map", snapshot, {"S1": 0.30}, candidates, {},
            {"HELD": 10.0, "WAIT": 10.0, "READY": 10.0},
        ) or {}
        self.assertIn("HELD", desired)
        self.assertIn("READY", desired)
        self.assertNotIn("WAIT", desired)

    def test_sticky_sizing_does_not_resize_held_name_for_new_signal(self):
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {}
        snapshot = {
            "balance": 1000000.0,
            "positions": {"HELD": {"volume": 10000}},
        }
        candidates = [
            {"code": "HELD", "style": "S1", "score": 70.0,
             "entry_ready": False, "feature": {"close": 10.0}},
            {"code": "READY", "style": "S1", "score": 80.0,
             "entry_ready": True, "feature": {"close": 10.0}},
        ]
        desired = invoke(
            "_sticky_desired_share_map", snapshot, {"S1": 0.30},
            candidates, {}, {"HELD": 10.0, "READY": 10.0}, False,
        ) or {}
        self.assertEqual(desired["HELD"], 10000)
        self.assertGreater(desired.get("READY", 0), 0)

    def test_sticky_sizing_reduces_only_after_meaningful_risk_drop(self):
        self.assertFalse(invoke(
            "meaningful_style_reduction", {"S1": 0.25}, {"S1": 0.24}
        ))
        self.assertTrue(invoke(
            "meaningful_style_reduction", {"S1": 0.25}, {"S1": 0.20}
        ))
        reference = invoke(
            "updated_sizing_style_reference",
            {"S1": 0.25}, {"S1": 0.24}, False,
        )
        self.assertEqual(reference, {"S1": 0.25})
        self.assertTrue(invoke(
            "meaningful_style_reduction", reference, {"S1": 0.21}
        ))
        strategy.A.blocked_codes = set()
        strategy.A.intraday_scales = {}
        strategy.A.entry_scales = {}
        snapshot = {
            "balance": 1000000.0,
            "positions": {"HELD": {"volume": 10000}},
        }
        candidates = [{
            "code": "HELD", "style": "S1", "score": 70.0,
            "entry_ready": False, "feature": {"close": 10.0},
        }]
        desired = invoke(
            "_sticky_desired_share_map", snapshot, {"S1": 0.05},
            candidates, {}, {"HELD": 10.0}, True,
        ) or {}
        self.assertEqual(desired["HELD"], 5000)

    def test_new_entry_execution_price_must_remain_near_ma7(self):
        candidate = {"feature": {
            "entry_setup": "trend", "close": 103.0,
            "ma7": 100.0, "ma40": 92.0,
            "raw_signal_close": 103.0,
        }}
        self.assertTrue(invoke("buy_entry_price_allowed", 103.0, candidate))
        self.assertFalse(invoke("buy_entry_price_allowed", 103.5, candidate))
        self.assertFalse(invoke("buy_entry_price_allowed", 105.0, candidate))

    def test_starter_allows_wider_ma7_distance_but_rejects_large_gap(self):
        candidate = {"feature": {
            "entry_setup": "ma40_starter", "close": 106.0,
            "ma7": 100.0, "ma40": 94.0,
            "raw_signal_close": 106.0,
        }}
        self.assertTrue(invoke("buy_entry_price_allowed", 105.0, candidate))
        self.assertFalse(invoke("buy_entry_price_allowed", 107.0, candidate))
        self.assertFalse(invoke("buy_entry_price_allowed", 109.5, candidate))

    def test_shengtun_october_gap_open_is_not_a_valid_entry_price(self):
        candidate = {"feature": {
            "entry_setup": "trend", "close": 10.322,
            "ma7": 10.302, "ma40": 8.646,
            "raw_signal_close": 10.322,
        }}
        self.assertFalse(invoke("buy_entry_price_allowed", 11.0, candidate))

    def test_entry_guard_converts_adjusted_ma_to_raw_price_coordinate(self):
        candidate = {"feature": {
            "entry_setup": "trend", "close": 934.0,
            "ma7": 925.0, "ma40": 850.0,
            "raw_signal_close": 20.0,
        }}
        levels = invoke("entry_raw_price_levels", candidate) or {}
        self.assertAlmostEqual(levels["signal_close"], 20.0)
        self.assertAlmostEqual(levels["ma7"], 925.0 * 20.0 / 934.0)
        self.assertTrue(invoke("buy_entry_price_allowed", 20.3, candidate))
        self.assertFalse(invoke("buy_entry_price_allowed", 20.7, candidate))

    def test_entry_guard_rejects_candidate_without_raw_signal_close(self):
        candidate = {"feature": {
            "entry_setup": "trend", "close": 934.0,
            "ma7": 925.0, "ma40": 850.0,
        }}
        self.assertIsNone(invoke("entry_raw_price_levels", candidate))
        self.assertFalse(invoke(
            "buy_entry_price_allowed", 20.0, candidate
        ))


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

    def test_intraday_top_requires_profit_and_distance_from_daily_mas(self):
        metrics = {
            "ma7": 10.0, "ma13": 9.7, "ma40": 9.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
        }
        self.assertFalse(invoke(
            "intraday_reduce_ready", metrics, 11.0, 9.9, 10.0
        ))
        self.assertFalse(invoke(
            "intraday_reduce_ready", metrics, 10.3, 10.5, 10.0
        ))
        self.assertTrue(invoke(
            "intraday_reduce_ready", metrics, 11.0, 10.5, 10.0
        ))

    def test_30m_reversal_near_ma7_starts_staged_addback(self):
        frame = pd.DataFrame({
            "open": [10.1, 10.2],
            "high": [10.3, 10.6],
            "low": [9.95, 10.0],
            "close": [10.1, 10.5],
            "volume": [100.0, 120.0],
            "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        self.assertEqual(
            invoke("intraday_action", frame, 10.0, 9.7, True,
                   True, 0, 0, True),
            "add_ma7",
        )

    def test_30m_shallow_ma7_touch_waits_for_ma13(self):
        frame = pd.DataFrame({
            "open": [10.1, 10.2], "high": [10.3, 10.6],
            "low": [9.95, 10.0], "close": [10.1, 10.5],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        })
        self.assertIsNone(
            invoke("intraday_action", frame, 10.0, 9.7, True,
                   True, 0, 0, False)
        )

    def test_starter_add_uses_two_30m_bars_over_daily_ma13(self):
        frame = pd.DataFrame({
            "open": [9.9, 10.05], "high": [10.15, 10.3],
            "low": [9.82, 9.98], "close": [10.05, 10.2],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        daily_metrics = {
            "ma7": 10.4, "ma7_prev1": 10.3,
            "ma13": 9.9, "ma40": 9.2,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_peak_price": 11.0,
        }
        self.assertEqual(
            invoke(
                "intraday_build_add_signal", frame, daily_metrics,
                3, "ma40_starter",
            ),
            "ma13",
        )

    def test_starter_ma7_add_keeps_daily_smoothness_guard(self):
        frame = pd.DataFrame({
            "open": [9.98, 10.08], "high": [10.15, 10.3],
            "low": [9.95, 10.0], "close": [10.1, 10.2],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        daily_metrics = {
            "ma7": 10.0, "ma7_prev1": 9.99,
            "ma13": 9.5, "ma40": 9.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_peak_price": 11.0,
        }
        self.assertEqual(
            invoke("intraday_build_add_signal", frame, daily_metrics, 3),
            "ma7",
        )

    def test_starter_add_rejects_unstable_or_cross_day_30m_bars(self):
        daily_metrics = {
            "ma7": 10.4, "ma7_prev1": 10.3,
            "ma13": 9.9, "ma40": 9.2,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
            "recent_peak_price": 11.0,
        }
        unstable = pd.DataFrame({
            "open": [9.9, 9.95], "high": [10.1, 10.05],
            "low": [9.82, 9.8], "close": [9.85, 10.0],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        cross_day = unstable.copy()
        cross_day.index = pd.to_datetime([
            "2026-08-02 14:30", "2026-08-03 10:00",
        ])
        self.assertIsNone(invoke(
            "intraday_build_add_signal", unstable, daily_metrics, 3
        ))
        self.assertIsNone(invoke(
            "intraday_build_add_signal", cross_day, daily_metrics, 3
        ))

    def test_next_day_first_hour_confirms_daily_support(self):
        frame = pd.DataFrame({
            "open": [10.0, 10.1], "high": [10.2, 10.3],
            "low": [9.98, 10.02], "close": [10.1, 10.2],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-04 10:00", "2026-08-04 10:30"]))
        self.assertTrue(invoke(
            "first_hour_daily_support_confirmed",
            frame, "20260804", 10.0,
        ))

    def test_next_day_first_hour_rejects_lost_daily_support(self):
        frame = pd.DataFrame({
            "open": [10.0, 10.05], "high": [10.2, 10.1],
            "low": [9.98, 9.85], "close": [10.1, 9.9],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-04 10:00", "2026-08-04 10:30"]))
        self.assertFalse(invoke(
            "first_hour_daily_support_confirmed",
            frame, "20260804", 10.0,
        ))

    def test_failed_confirmation_only_removes_shares_above_starter_base(self):
        plan = {"base_volume": 1000, "added_volume": 1000}
        self.assertEqual(
            invoke("build_add_rollback_volume", 1400, 1400, plan), 400
        )
        self.assertEqual(
            invoke("build_add_rollback_volume", 1000, 1000, plan), 0
        )

    def test_ma7_pullback_requires_six_percent_and_non_turning_ma7(self):
        metrics = {
            "ma7": 10.0, "ma7_prev1": 9.99,
            "ma13": 9.5, "ma40": 9.0,
        }
        self.assertTrue(
            invoke("ma7_pullback_add_ready", metrics, 11.0, 10.3)
        )
        self.assertFalse(
            invoke("ma7_pullback_add_ready", metrics, 11.0, 10.5)
        )
        self.assertFalse(invoke(
            "ma7_pullback_add_ready",
            {"ma7": 9.95, "ma7_prev1": 10.0,
             "ma13": 9.5, "ma40": 9.0}, 11.0, 10.3,
        ))

    def test_ma7_add_requires_smooth_gap_ratio_and_not_high_above_ma40(self):
        smooth = {
            "ma7": 10.0, "ma7_prev1": 9.99,
            "ma13": 9.5, "ma40": 9.0,
            "recent_pullback": 0.08,
        }
        short_gap_too_small = dict(smooth, ma7=9.6)
        too_high = dict(smooth, ma40=8.0)
        self.assertTrue(invoke("ma7_pullback_add_ready", smooth))
        self.assertFalse(invoke(
            "ma7_pullback_add_ready", short_gap_too_small
        ))
        self.assertFalse(invoke("ma7_pullback_add_ready", too_high))

    def test_addback_resumes_remaining_tranche_after_ma7_rebound(self):
        frame = pd.DataFrame({
            "open": [10.1, 10.2], "high": [10.3, 10.7],
            "low": [9.95, 10.0], "close": [10.1, 10.6],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        }, index=pd.to_datetime(["2026-08-03 10:00", "2026-08-03 10:30"]))
        self.assertEqual(
            invoke("intraday_action", frame, 10.0, 9.7, True,
                   True, 1, 2),
            "add_resume",
        )

    def test_addback_is_disabled_after_three_trading_days(self):
        frame = pd.DataFrame({
            "open": [10.1, 10.2], "high": [10.3, 10.6],
            "low": [9.95, 10.0], "close": [10.1, 10.5],
            "volume": [100.0, 120.0], "amount": [1000.0, 1200.0],
        })
        self.assertIsNone(
            invoke("intraday_action", frame, 10.0, 9.7, True,
                   True, 0, 4)
        )

    def test_addback_requires_smooth_daily_ma7_and_ma13(self):
        smooth = {
            "ma7": 11.0, "ma13": 10.0, "ma40": 9.0,
            "ma7_slope3": 0.01, "ma13_slope3": 0.006,
        }
        flat = dict(smooth, ma7_slope3=0.0)
        self.assertTrue(invoke("addback_trend_ready", smooth, 11.6))
        self.assertFalse(invoke("addback_trend_ready", flat, 11.6))

    def test_addback_window_counts_trading_days_once(self):
        strategy.A.addback_plans = {
            "000001.SZ": {
                "start_date": "20260803", "last_age_date": "20260803",
                "age": 0,
            },
        }
        strategy.A.build_plans = {}
        invoke("_advance_position_plans", "20260804")
        invoke("_advance_position_plans", "20260804")
        invoke("_advance_position_plans", "20260805")
        invoke("_advance_position_plans", "20260806")
        self.assertEqual(
            strategy.A.addback_plans["000001.SZ"]["age"], 3
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
                "_submit_order_now", context, "buy", "000001.SZ", 1000,
                "20260805", "rebalance",
            ))
            self.assertTrue(invoke(
                "_submit_order_now", context, "sell", "600000.SH", 500,
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
            barpos = 12

            @staticmethod
            def get_history_data(*args):
                raise AssertionError("explicit price must avoid universe lookup")

            @staticmethod
            def get_bar_timetag(index):
                if index != 12:
                    raise AssertionError("unexpected bar index")
                return 20260806100500

        original = getattr(strategy, "order_shares", None)
        had_original = hasattr(strategy, "order_shares")
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_original_timetag = hasattr(strategy, "timetag_to_datetime")
        calls = []
        strategy.A.mode = "BACKTEST"
        strategy.A.sent_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.order_shares = lambda *args: calls.append(args)
        strategy.timetag_to_datetime = lambda *args: "20260806100500"
        context = FakeContext()
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                self.assertTrue(invoke(
                    "_submit_order_now", context, "buy", "002755.SZ", 1000,
                    "20260806", "rebalance", 13.25,
                ))
            self.assertEqual(calls, [
                ("002755.SZ", 1000, "fix", 13.25, context, "testS"),
            ])
            self.assertIn(
                "ORDER_SUBMITTED 20260806 100500 buy 002755.SZ 1000 "
                "price 13.25 rebalance",
                output.getvalue(),
            )
        finally:
            if had_original:
                strategy.order_shares = original
            else:
                delattr(strategy, "order_shares")
            if had_original_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_same_bar_same_side_order_is_not_submitted_twice(self):
        class FakeContext(object):
            accountID = "testS"
            barpos = 12

            @staticmethod
            def get_bar_timetag(index):
                return 20260806100500

        original = getattr(strategy, "order_shares", None)
        had_original = hasattr(strategy, "order_shares")
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_original_timetag = hasattr(strategy, "timetag_to_datetime")
        calls = []
        strategy.A.mode = "BACKTEST"
        strategy.A.sent_order_keys = set()
        strategy.A.pending_orders = []
        strategy.A.pending_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.A.desired_shares = {}
        strategy.A.blocked_codes = set()
        strategy.A.position_meta = {}
        strategy.A.build_plans = {}
        strategy.A.build_confirm_plans = {}
        strategy.A.trend_add_reasons = {}
        strategy.order_shares = lambda *args: calls.append(args)
        strategy.timetag_to_datetime = lambda *args: "20260806100500"
        context = FakeContext()
        try:
            self.assertTrue(invoke(
                "_send_order", context, "sell", "300620.SZ", 1000,
                "20260806", "sector_rotation", 93.66,
            ))
            self.assertFalse(invoke(
                "_send_order", context, "sell", "300620.SZ", 1000,
                "20260806", "rebalance", 93.66,
            ))
            self.assertEqual(len(calls), 0)
            self.assertEqual(len(strategy.A.pending_orders), 1)
        finally:
            if had_original:
                strategy.order_shares = original
            else:
                delattr(strategy, "order_shares")
            if had_original_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

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
                "_submit_order_now", context, "buy", "000001.SZ", 1000,
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

    def test_signal_executes_on_next_5m_open_with_backtest_slippage(self):
        class FakeContext(object):
            accountID = "testS"
            barpos = 0

            @staticmethod
            def get_bar_timetag(index):
                return [20260806100000, 20260806100500][index]

            @staticmethod
            def get_market_data_ex(fields, stocks, **kwargs):
                return {
                    code: pd.DataFrame({"open": [20.0], "close": [20.1]})
                    for code in stocks
                }

        original_order_shares = getattr(strategy, "order_shares", None)
        had_order_shares = hasattr(strategy, "order_shares")
        original_timetag = getattr(strategy, "timetag_to_datetime", None)
        had_timetag = hasattr(strategy, "timetag_to_datetime")
        calls = []
        strategy.A.mode = "BACKTEST"
        strategy.A.sent_order_keys = set()
        strategy.A.pending_orders = []
        strategy.A.pending_order_keys = set()
        strategy.A.owned_codes = set()
        strategy.A.desired_shares = {}
        strategy.A.blocked_codes = set()
        strategy.A.position_meta = {}
        strategy.A.build_plans = {}
        strategy.A.build_confirm_plans = {}
        strategy.A.trend_add_reasons = {}
        strategy.order_shares = lambda *args: calls.append(args)
        strategy.timetag_to_datetime = lambda value, *args: str(value)
        context = FakeContext()
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                self.assertTrue(invoke(
                    "_send_order", context, "buy", "000001.SZ", 1000,
                    "20260806", "rebalance", 19.80, 21.0,
                ))
                self.assertTrue(invoke(
                    "_send_order", context, "buy", "000002.SZ", 1000,
                    "20260806", "rebalance", 19.80, 19.99,
                ))
                self.assertEqual(calls, [])
                context.barpos = 1
                invoke(
                    "_flush_pending_orders", context,
                    datetime.datetime(2026, 8, 6, 10, 5),
                )
            self.assertEqual(calls, [
                ("000001.SZ", 1000, "fix", 20.02, context, "testS"),
            ])
            self.assertIn(
                "ORDER_QUEUED 20260806 100000 buy 000001.SZ 1000",
                output.getvalue(),
            )
            self.assertIn(
                "ORDER_SUBMITTED 20260806 100500 buy 000001.SZ 1000 "
                "price 20.02 rebalance signal_time 100000 slippage_bps 10.0",
                output.getvalue(),
            )
            self.assertIn(
                "ORDER_CANCELLED 20260806 100500 buy 000002.SZ 1000 "
                "next_bar_entry_gap",
                output.getvalue(),
            )
        finally:
            if had_order_shares:
                strategy.order_shares = original_order_shares
            else:
                delattr(strategy, "order_shares")
            if had_timetag:
                strategy.timetag_to_datetime = original_timetag
            else:
                delattr(strategy, "timetag_to_datetime")

    def test_backtest_slippage_penalizes_buys_and_sells(self):
        self.assertEqual(invoke(
            "backtest_slippage_price", 20.0, "buy", 10.0
        ), 20.02)
        self.assertEqual(invoke(
            "backtest_slippage_price", 20.0, "sell", 10.0
        ), 19.98)
        self.assertEqual(invoke(
            "backtest_slippage_price", 20.0, "buy", 10.0, 19.90, 20.01
        ), 20.01)
        self.assertEqual(invoke(
            "backtest_slippage_price", 20.0, "sell", 10.0, 19.99, 20.10
        ), 19.99)

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

    def test_backtest_deal_records_are_logged_once_as_confirmed_deals(self):
        class FakeDeal(object):
            market = "SZ"
            stockcode = "300620"
            trade_date = "20260806100500"
            open_close = 1
            position = 1000
            trade_price = 66.10

        class FakeContext(object):
            barpos = 20

        original = getattr(strategy, "get_result_records", None)
        had_original = hasattr(strategy, "get_result_records")
        strategy.A.logged_deal_keys = set()
        strategy.get_result_records = lambda *args: [FakeDeal()]
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                invoke("_log_backtest_deals", FakeContext())
                invoke("_log_backtest_deals", FakeContext())
            self.assertEqual(output.getvalue().count("DEAL "), 1)
            self.assertIn(
                "DEAL 20260806 100500 buy 300620.SZ 1000 price 66.1",
                output.getvalue(),
            )
        finally:
            if had_original:
                strategy.get_result_records = original
            else:
                delattr(strategy, "get_result_records")

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
