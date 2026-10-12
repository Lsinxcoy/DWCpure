# -*- coding: utf-8 -*-

import os as _os
def _dwc_root():
    """R228: 仓库根发现（env DWC_ROOT > 本文件上溯 — 不写死盘符/用户名）。"""
    _e = _os.environ.get("DWC_ROOT", "").strip()
    if _e and _os.path.isdir(_e):
        return _os.path.abspath(_e)
    _c = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    while not (_os.path.isdir(_os.path.join(_c, "src", "dwc"))
               and _os.path.isdir(_os.path.join(_c, "config"))):
        _p = _os.path.dirname(_c)
        if _p == _c:
            break
        _c = _p
    else:
        return _c
    # ③ 副本场景（cron 跑 hermes/scripts 拷贝 — 上溯找不到仓库）:
    #    同目录 .dwc_repo 标记（同步时写入一行仓库路径）
    _mk = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                        ".dwc_repo")
    if _os.path.isfile(_mk):
        with open(_mk, encoding="utf-8") as _f:
            _r = _f.readline().strip()
        if _r and _os.path.isdir(_r):
            return _r
    raise RuntimeError("找不到 DWC 根 — 设 DWC_ROOT 或同步副本(写 .dwc_repo)")

"""R217 · bench 常态化（no_agent cron: health=silence 契约）。

每日跑一轮任务基准, 结果落 var/dwc_bench_results.json + 台账 bench 事件
（曲线自动积累 — 质量回路的长期观测面）。健康=静默退出 0 + 空 stdout;
任何异常 rc1 + stderr（给监控判 RED）。固定 repo ROOT（cron 副本在
hermes/scripts 下, __file__ 相对会找错 var/ — R208 教训）。
"""
import os
import subprocess
import sys

ROOT = _dwc_root()
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
