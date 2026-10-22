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


def _ensure_runtime():
    """★★★ R428 · cron 用的是 hermes 内置 python（**没有 pyyaml**）——
    本脚本依赖 dwc（需要 yaml）⇒ 启动时自我切换到带依赖的解释器。

    现场：`DWC bench daily` / `DWC anchor drift watch` 连续 9/19 次
    `ModuleNotFoundError: No module named 'yaml'`，两个 cron 一直是 error。
    根因不是脚本坏了，是**跑它的解释器不是装依赖的那个**。

    ★ 不写死盘符/用户名：从本文件位置上溯到 hermes 根，再找 venv。
    """
    try:
        import yaml  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _la = os.environ.get("LOCALAPPDATA", "")
    _cands = [
        os.path.join(_root, "hermes-agent", "venv", "Scripts", "python.exe"),
        os.path.join(_root, "hermes-agent", "venv", "bin", "python"),
        os.path.join(_root, "venv", "Scripts", "python.exe"),
        os.path.join(_root, ".venv", "Scripts", "python.exe"),
    ]
    if _la:   # 仓库副本场景：venv 在 hermes 根下，不在仓库里
        _cands.insert(0, os.path.join(
            _la, "hermes", "hermes-agent", "venv", "Scripts", "python.exe"))
    for _cand in _cands:
        if (os.path.isfile(_cand)
                and os.path.abspath(sys.executable) != os.path.abspath(_cand)):
            # ★ Windows 的 os.execv **不引号化参数** —— 路径含空格
            #   （`E:\Divine Wisdom Core`）会被拆成 `E:\Divine` ⇒ 报
            #   `can't open file 'E:\Divine'`。subprocess 的列表形式才会
            #   正确加引号（现场：R428 自测）。
            import subprocess as _sp
            raise SystemExit(_sp.call(
                [_cand, os.path.abspath(__file__)] + sys.argv[1:]))
    sys.stderr.write("缺少 pyyaml 且找不到带依赖的解释器\n")
    raise SystemExit(2)


_ensure_runtime()

ROOT = _dwc_root()
# ★ R428: `_ensure_runtime()` 之后 sys.executable 就是**带依赖的解释器**
#   （已在 venv 里就是它自己；否则已 execv 过去）—— 不用再猜路径，
#   也就没有第二份"硬编码 venv 路径"。
PY = sys.executable


def main() -> int:
    try:
        # ★ R232 A/B 对照: select_mode 拨盘; auto ⇒ 按日奇偶交替
        #   （偶数日 predictor 预测式选择, 奇数日 full 原序 — 增益走 7 天实测）
        import time as _t
        import yaml as _y
        _drift = _y.safe_load(open(os.path.join(ROOT, "config", "drift.yaml"),
                                   encoding="utf-8"))["drift"]
        _mode = _drift["bench"].get("select_mode", "full")
        if _mode == "auto":
            _mode = "predictor" if int(_t.strftime("%d")) % 2 == 0 else "full"
        r = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "dwc_bench.py"),
             "--select", _mode],
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
