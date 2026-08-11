export const sampleLog = `start back test mode
INIT QMT_MC_ROTATION_V2_3_0 BACKTEST testS STOCK
ENGINE period 5m start 20250801 end 20250811
FIRST_BAR 2025-08-01 09:35:00
PORTFOLIO source virtual_account capital 1000000 balance 1000000 cash 1000000 positions 0
STATE 20250801 exposure 0.3 style_exposures {'000905.SH': 0.3} scores {'000300.SH': 62.0, '000905.SH': 72.0, '000852.SH': 58.0, '399006.SZ': 55.0} regimes {'000300.SH': 'OFF', '000905.SH': 'WATCH', '000852.SH': 'OFF', '399006.SZ': 'OFF'} risk_caps {'000905.SH': 0.3} reserve 12 watchlist 5 spectators 2 entry_ready 0
SECTORS [('000905.SH', 'SW1电子', 76.0), ('000905.SH', 'SW1通信', 64.0), ('000905.SH', 'SW1基础化工', 52.0)]
WATCHLIST [('000905.SH', '600183.SH', '生益科技', 69.2, 74.0, 66.5, 62.0, 'WAIT'), ('000905.SH', '002463.SZ', '沪电股份', 65.0, 84.0, 48.0, 55.0, 'OVEREXTENDED')]
SPECTATORS [('000905.SH', '300476.SZ', '胜宏科技', 92.0, 35.0, 41.0, 'OVEREXTENDED')]
PORTFOLIO source virtual_account capital 1000000 balance 1000000 cash 1000000 positions 0
STATE 20250804 exposure 0.3 style_exposures {'000905.SH': 0.3} scores {'000300.SH': 64.0, '000905.SH': 74.0, '000852.SH': 61.0, '399006.SZ': 58.0} regimes {'000300.SH': 'OFF', '000905.SH': 'WATCH', '000852.SH': 'OFF', '399006.SZ': 'OFF'} risk_caps {'000905.SH': 0.3} reserve 12 watchlist 5 spectators 2 entry_ready 1
ENTRY_READY 20250804 added [('600183.SH', 'trend', 72.1, 78.2, 69.5, 73.4)] removed []
DESIRED 20250804 {'600183.SH': 2500}
ALLOCATION 20250804 planned_exposure 0.3 target_exposure 0.18 fill_rate 0.6 unallocated_cash 120000
ORDER_SUBMITTED 20250804 103000 buy 600183.SH 2500 price 40.12 rebalance
DEAL 20250804 103001 buy 600183.SH 2500 price 40.14
PORTFOLIO source virtual_account capital 1000000 balance 1008200 cash 899650 positions 1
SECTOR_FOCUS 20250811 SW1电子 style 000905.SH leader 79.0 runner 57.0 base_exposure 0.6
STATE 20250811 exposure 0.6 style_exposures {'000905.SH': 0.6} scores {'000300.SH': 65.0, '000905.SH': 79.0, '000852.SH': 63.0, '399006.SZ': 60.0} regimes {'000300.SH': 'WATCH', '000905.SH': 'STRONG', '000852.SH': 'OFF', '399006.SZ': 'OFF'} risk_caps {'000905.SH': 0.6} reserve 16 watchlist 6 spectators 3 entry_ready 1
SECTORS [('000905.SH', 'SW1电子', 84.0), ('000905.SH', 'SW1通信', 67.0), ('000905.SH', 'SW1基础化工', 55.0)]
WATCHLIST [('000905.SH', '600183.SH', '生益科技', 74.0, 80.0, 70.0, 75.0, 'HELD'), ('000905.SH', '002463.SZ', '沪电股份', 68.0, 82.0, 52.0, 58.0, 'OVEREXTENDED')]
TARGETS [('000905.SH', '600183.SH', '生益科技', 74.0, 80.0, 70.0, 75.0, 'trend')]
ORDER_SUBMITTED 20250811 140000 sell 600183.SH 800 price 43.20 intraday_top
DEAL 20250811 140001 sell 600183.SH 800 price 43.18`;
