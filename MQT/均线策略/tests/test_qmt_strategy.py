import importlib.util
import unittest
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
    def test_rising_daily_weekly_monthly_series_scores_100(self):
        daily = np.arange(1.0, 131.0)
        weekly = np.arange(1.0, 27.0)
        monthly = np.arange(1.0, 25.0)
        self.assertEqual(invoke("market_leg_score", daily, weekly, monthly), 100.0)

    def test_falling_daily_weekly_monthly_series_scores_zero(self):
        daily = np.arange(131.0, 0.0, -1.0)
        weekly = np.arange(27.0, 1.0, -1.0)
        monthly = np.arange(25.0, 1.0, -1.0)
        self.assertEqual(invoke("market_leg_score", daily, weekly, monthly), 0.0)

    def test_exposure_boundaries_are_conservative(self):
        cases = [(49.9, 0.0), (50.0, 0.25), (60.0, 0.45),
                 (70.0, 0.65), (80.0, 0.80)]
        actual = [invoke("exposure_from_score", score) for score, _ in cases]
        self.assertEqual(actual, [expected for _, expected in cases])


class SectorRankingTests(unittest.TestCase):
    def test_sector_index_name_maps_to_member_sector(self):
        self.assertEqual(
            invoke("sector_member_name", "SW1电子加权"), "SW1电子"
        )

    def test_sector_feature_uses_relative_strength_to_benchmark(self):
        close = np.linspace(100.0, 140.0, 70)
        amount = np.linspace(100000000.0, 130000000.0, 70)
        frame = pd.DataFrame({"close": close, "amount": amount})
        benchmark = np.linspace(100.0, 115.0, 70)
        feature = invoke("sector_feature", frame, benchmark)
        self.assertIsInstance(feature, dict)
        self.assertTrue(feature["eligible"])
        self.assertGreater(feature["rel20"], 0.0)
        self.assertEqual(feature["trend"], 1.0)

    def test_sector_ranking_rejects_weak_trends_and_penalizes_overheat(self):
        features = {
            "strong": {
                "rel20": 0.08, "rel60": 0.15, "trend": 1.0,
                "amount_ratio": 1.20, "distance_ma20": 0.05,
                "eligible": True,
            },
            "overheated": {
                "rel20": 0.12, "rel60": 0.18, "trend": 1.0,
                "amount_ratio": 1.30, "distance_ma20": 0.22,
                "eligible": True,
            },
            "weak": {
                "rel20": -0.05, "rel60": -0.10, "trend": 0.2,
                "amount_ratio": 0.80, "distance_ma20": -0.04,
                "eligible": False,
            },
        }
        ranked = invoke("rank_sectors", features, 3) or []
        self.assertEqual([item[0] for item in ranked], ["strong", "overheated"])
        self.assertGreater(ranked[0][1], ranked[1][1])


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
            "stock_feature", self.make_frame(), 0.05, 0.10, 50000000.0
        )
        self.assertIsNotNone(feature)
        self.assertGreater(feature["rs20"], 0.0)

    def test_stock_feature_rejects_illiquid_stock(self):
        feature = invoke(
            "stock_feature", self.make_frame(amount=1000000.0),
            0.05, 0.10, 50000000.0
        )
        self.assertIsNone(feature)

    def test_position_metrics_remain_available_after_trend_break(self):
        frame = self.make_frame(last_close=130.0)
        frame.loc[frame.index[-1], "close"] = 100.0
        metrics = invoke("position_metrics", frame)
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["close"], 100.0)
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
                "rs20": 0.10, "rs60": 0.20, "r20": 0.15,
                "high_proximity": 0.98, "average_amount": 200000000.0,
                "volatility": 0.01,
            }},
            {"code": "B", "sector": "S2", "feature": {
                "rs20": 0.02, "rs60": 0.04, "r20": 0.05,
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
            "exit_reason", close=90.0, ma20=95.0, atr=4.0,
            entry_price=100.0, peak_price=104.0, holding_days=2,
            still_selected=True, exposure=0.80,
        )
        self.assertEqual(reason, "initial_stop")

    def test_rotation_exit_has_no_minimum_holding_period(self):
        reason = invoke(
            "exit_reason", 105.0, 100.0, 3.0, 100.0, 106.0,
            1, False, 0.80,
        )
        self.assertEqual(reason, "sector_rotation")

    def test_take_profit_can_exit_on_first_holding_day(self):
        reason = invoke(
            "exit_reason", 112.0, 108.0, 3.0, 100.0, 112.0,
            1, True, 0.80,
        )
        self.assertEqual(reason, "take_profit")

    def test_twenty_day_maximum_holding_exit(self):
        reason = invoke(
            "exit_reason", 110.0, 100.0, 3.0, 100.0, 112.0,
            20, True, 0.80,
        )
        self.assertEqual(reason, "max_holding")

    def test_target_shares_rounds_down_to_board_lot(self):
        shares = invoke(
            "target_shares", total_asset=1000000.0, exposure=0.80,
            position_count=6, price=20.0, max_weight=0.15,
        )
        self.assertEqual(shares, 6600)


class QmtAdapterTests(unittest.TestCase):
    def test_backtest_snapshot_uses_backtest_records_without_logged_in_account(self):
        class FakeHolding(object):
            market = "SZ"
            stockcode = "000001"
            trade_price = 9.50
            current_price = 10.00
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

        def reject_trade_detail(*args):
            raise AssertionError("backtest must not query a logged-in account")

        def fake_result_records(record_type, index, context):
            self.assertEqual((record_type, index), ("holdings", 20))
            self.assertIsInstance(context, FakeContext)
            return [FakeHolding()]

        strategy.get_trade_detail_data = reject_trade_detail
        strategy.get_result_records = fake_result_records
        try:
            snapshot = invoke("_account_snapshot", FakeContext())
            self.assertEqual(snapshot["balance"], 1050000.0)
            self.assertEqual(snapshot["available_cash"], 1040000.0)
            self.assertEqual(
                snapshot["positions"],
                {"000001.SZ": {
                    "volume": 1000,
                    "available": 1000,
                    "open_price": 9.50,
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
            "feature": {"close": 10.0},
        }]
        desired = invoke(
            "_desired_share_map", snapshot, 0.80, candidates, {}
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
