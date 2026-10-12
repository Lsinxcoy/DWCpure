# -*- coding: utf-8 -*-
"""R217 · bench 常态化（no_agent cron: health=silence 契约）。

每日跑一轮任务基准, 结果落 var/dwc_bench_results.json + 台账 bench 事件
（曲线自动积累 — 质量回路的长期观测面）。健康=静默退出 0 + 空 stdout;
任何异常 rc1 + stderr（给监控判 RED）。固定 repo ROOT（cron 副本在
hermes/scripts 下, __file__ 相对会找错 var/ — R208 教训）。
"""
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
PY = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "venv", "Scripts", "python.exe")
if not os.path.exists(PY):                     # cron 副本场景: venv 固定路径
    PY = r"C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"


def main() -> int:
    try:
        r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_bench.py")],
                           capture_output=True, text=True, timeout=1800,
                           cwd=ROOT, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            sys.stderr.write("bench rc=%d %s\n"
                             % (r.returncode, (r.stderr or "")[-400:]))
            return 1
        # 健康=静默（详细结果已在 var/dwc_bench_results.json + 台账）
        return 0
    except Exception as exc:                   # noqa: BLE001 — 异常必须响
        sys.stderr.write("bench 异常: %s: %s\n" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
