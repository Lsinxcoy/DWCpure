"""DWC 编排层（harness）· 定位声明（DWC-MEM · 记忆底座）

★ 三入口（ERROR_AND_TERM §六 的 T1 判据要求 run_term 完整）
  · run_term.py —— 一次 term 的六步（当前唯一已实现的入口）
  · step.py     —— 内层：一次决策 + 一次执行 + 一条痕迹  ★ 待实现
  · ingest.py   —— 摄入入口                            ★ 待实现

★ 判据 T1 要求 run_term 内必含:
  before 快照 / n×step / after 快照 / 五元盘点 / 下一轮任务源
"""
