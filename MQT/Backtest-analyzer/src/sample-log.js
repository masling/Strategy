export const sampleLog = `ENGINE period 5m start 20250701 end 20250805
FIRST_BAR 2025-07-01 09:35:00
DESIRED 20250801 {'002755.SZ': 2000, '600036.SH': 1500}
ALLOCATION 20250801 planned_exposure 0.8 target_exposure 0.62 fill_rate 0.775 unallocated_cash 180000
ORDER 20250801 buy 002755.SZ 2000 rebalance
PORTFOLIO source virtual_account balance 996162.36 cash 872879.36 positions 6
STATE 20250801 exposure 0.8 style_exposures {'large': 0.4, 'growth': 0.4} scores {'000300.SH': {'score': 82}, '399006.SZ': {'score': 88}, '000905.SH': {'score': 76}}
SECTORS [('growth', 'SW1_汽车', 86.5), ('growth', 'SW1_电子', 84.2), ('large', 'SW1_银行', 80)]
TARGETS [('growth', '002755.SZ', '奥赛康', 91.2), ('large', '600036.SH', '招商银行', 86.4)]
INTRADAY 20250801 002755.SZ reduce 600
DESIRED 20250804 {'002755.SZ': 1400, '600036.SH': 1500}
ORDER 20250804 sell 002755.SZ 600 intraday_top
STATE 20250804 exposure 0.7 style_exposures {'large': 0.35, 'growth': 0.35} scores {'000300.SH': {'score': 78}, '399006.SZ': {'score': 81}}
SECTORS [('growth', 'SW1_汽车', 83.5), ('large', 'SW1_银行', 78)]
TARGETS [('growth', '002755.SZ', '奥赛康', 88.2), ('large', '600036.SH', '招商银行', 84.1)]`;
