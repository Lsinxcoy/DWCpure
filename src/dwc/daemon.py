"""daemon · 常驻循环引擎（R164 — DWC 的"活着"那一面）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ e2e_loop 证明了**单轮**闭环全通（pytest/e2e 全绿）; 本模块把单轮
    包成**可轮转**的循环 — 不重造引擎（propose/gate/judge/accept/pipeline
    全在既有器官里）, 只做四件事:
      ① 轮转（round ← round+1, 跨轮状态经 score_history.jsonl 续接）
      ② 记账（RoundLog 每轮一档 — 崩溃可查, checkpoint 可续）
      ③ 熔断（四条纪律 — 见 _FUSE_RULES; 超时跳过 ≠ 中断, 连空转 ⇒ 停）
      ④ 停机（SIGINT/停止文件 ⇒ 当前轮收尾后退出 — 不半轮死）
  ★ 不抢位: 不判分（judge）· 不提案（evolver/candidates）· 不落地
    （applier/landing）; 本模块只驱动 + 观察 + 记账。
  ★★ 形态裁决（深度思考 4 — 有据不扩权）:
      CLI 前台循环（--rounds N / --budget-minutes M / --once）, **不做
      HTTP 服务** — 无需求证据（G4: 不发明没有据的面）; 常驻形态由
      cron 包装（母巢既有 5min 监控面可复用）, 不在 DWC 内造第二套守护。

★★★ TRUTH_SOURCE（判据 G2）
  · 跨轮分数序列 ← score_history.jsonl（e2e 已在写的同一文件 — 不另立）
  · 每轮结果 ← 现有器官返回值（本模块不重算任何判据）
  · 停机/熔断状态 ← 本模块自查簿（stop 文件 + 连续空转计数）
"""
from __future__ import annotations

import json
import os
import signal
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

#: ★ 熔断四律（母巢教训直搬 — 每条都有出处, 不是拍脑袋）
_FUSE_RULES: dict[str, str] = {
    "llm_timeout": "单轮 LLM 超时 ⇒ 跳过并记录（熔断≠失败 — 循环继续）",
    "consecutive_idle": "连续 N 轮无可判动作 ⇒ 自动停机（防空转死循环烧 quota）",
    "stop_file": "stop 文件在场 ⇒ 当前轮收尾后退出（不半轮死）",
    "sigint": "SIGINT ⇒ 置停机标志（同 stop 文件 — 收尾后退出）",
}

#: 默认熔断参数（管理参数 — 调用方可覆盖）
DEFAULT_MAX_IDLE_ROUNDS = 3
DEFAULT_STOP_FILENAME = "STOP"


@dataclass
class RoundLog:
    """一轮的台账（进 rounds.jsonl — 崩溃可查, checkpoint 可续）。"""

    round_no: int
    started_at: float
    finished_at: float = 0.0
    n_candidates: int = 0
    chain_verdict: str | None = None
    blocked: list[str] = field(default_factory=list)
    landed: bool = False
    score: float | None = None
    sigma: int | None = None
    skipped_reason: str | None = None
    error: str | None = None


@dataclass
class DaemonState:
    """常驻状态（落盘 daemon_state.json — 崩溃后续轮的锚）。"""

    round_no: int = 0
    n_landed: int = 0
    n_skipped: int = 0
    n_error: int = 0
    consecutive_idle: int = 0
    stop_requested: bool = False


class DaemonError(Exception):
    """引擎的显式拒绝（round_fn 缺/log 路径不可写 / stop 文件语法坏）。"""


class Daemon:
    """★ 常驻循环（驱动 round_fn — 单轮逻辑由调用方注入, 不内建引擎）。

    ★ round_fn(round_no, daemon) → dict（至少含 chain_verdict; 可选
      n_candidates/landed/score/sigma/skipped_reason）。
    ★ 返回 None 或 raise ⇒ 本模块按熔断规则记账继续（不中断 —
      除非连续空转超限）。
    """

    def __init__(self, round_fn: Callable[[int, Daemon], dict | None],
                 *, state_dir: str,
                 max_idle_rounds: int = DEFAULT_MAX_IDLE_ROUNDS,
                 on_round: Callable[[RoundLog], None] | None = None):
        if not callable(round_fn):
            raise DaemonError("round_fn 须 callable(round_no, daemon) -> dict")
        self.round_fn = round_fn
        self.state_dir = state_dir
        self.max_idle = int(max_idle_rounds)
        self.on_round = on_round
        os.makedirs(state_dir, exist_ok=True)
        self._state_path = os.path.join(state_dir, "daemon_state.json")
        self._log_path = os.path.join(state_dir, "rounds.jsonl")
        self._stop_path = os.path.join(state_dir, DEFAULT_STOP_FILENAME)
        self.state = self._load_state()
        self._sig_prev: dict[int, Any] = {}
        #: ★ 留痕面（G7 — 静默 except 的记账位, 不是吞异常）
        self._stop_unlink_error: str | None = None
        self._sig_errors: list[str] = []

    # ── 持久化（checkpoint — 崩溃后续轮的锚）──
    def _load_state(self) -> DaemonState:
        if os.path.exists(self._state_path):
            try:
                raw = json.load(open(self._state_path, encoding="utf-8"))
                return DaemonState(**{k: v for k, v in raw.items()
                                      if k in DaemonState().__dict__})
            except Exception:                        # noqa: BLE001 — 坏档显式重建
                return DaemonState()
        return DaemonState()

    def _save_state(self) -> None:
        tmp = self._state_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(asdict(self.state), f, ensure_ascii=False)
        os.replace(tmp, self._state_path)        # 原子替换（半写文件不作数）

    def _append_log(self, rl: RoundLog) -> None:
        with open(self._log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(rl), ensure_ascii=False) + "\n")

    # ── 熔断原语 ──
    def _stop_file_present(self) -> bool:
        if os.path.exists(self._stop_path):
            # ★ 停止文件**消费一次即删**（否则下一轮又被判停 — 语义: 一次性请求）
            try:
                os.remove(self._stop_path)
            except OSError as exc:
                # ★ G7 静默门: 删失败也留痕（ consumed 失败 = 下次还会见到
                #   ⇒ 循环会再次以此原因停 — 可接受, 但不可无声）
                self.state.n_skipped += 0        # 不改业务计数
                self._stop_unlink_error = "%s: %s" % (type(exc).__name__, exc)
            return True
        return False

    # ── 停机信号（SIGINT ⇒ 收尾后退出 — 不半轮死）──
    def install_signal_handlers(self) -> None:
        def _handler(signum, frame):
            self.state.stop_requested = True
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                self._sig_prev[sig] = signal.getsignal(sig)
                signal.signal(sig, _handler)
            except (ValueError, OSError) as exc:
                # ★ G7: 非主线程/平台缺 ⇒ 该信号不可用, **显式记账**
                #   （静默 pass 会被 G7 静默门抓 — 且丢了"为什么没熔断"的线索）
                self._sig_errors = getattr(self, "_sig_errors", [])
                self._sig_errors.append("%s: %s" % (sig, exc))

    def restore_signal_handlers(self) -> None:
        for sig, prev in self._sig_prev.items():
            try:
                signal.signal(sig, prev)
            except (ValueError, OSError) as exc:
                self._sig_errors.append("restore %s: %s" % (sig, exc))

    # ── 单轮（带熔断记账 — 异常不中断循环）──
    def run_one_round(self) -> RoundLog:
        n = self.state.round_no + 1
        rl = RoundLog(round_no=n, started_at=time.time())
        try:
            out = self.round_fn(n, self)
        except Exception as exc:                     # noqa: BLE001 — 留痕不中断
            rl.finished_at = time.time()
            rl.error = "%s: %s" % (type(exc).__name__, exc)
            self.state.n_error += 1
            self.state.consecutive_idle += 1
            # ★★★ R164 实测抓的真 bug: 异常轮**必须推进 round_no**
            #   — 否则下一轮 n 不变 ⇒ 同一轮无限重试直到空转熔断
            #     （实测: r=2 连炸 3 次, rounds_run 卡在 1）
            self.state.round_no = n
            self._append_log(rl)
            self._save_state()
            return rl
        rl.finished_at = time.time()
        if out is None:
            rl.skipped_reason = "round_fn 返回 None（本轮无动作）"
        else:
            rl.n_candidates = int(out.get("n_candidates", 0) or 0)
            rl.chain_verdict = out.get("chain_verdict")
            rl.blocked = list(out.get("blocked") or [])
            rl.landed = bool(out.get("landed", False))
            rl.score = out.get("score")
            rl.sigma = out.get("sigma")
            rl.skipped_reason = out.get("skipped_reason")
        # ── 计数（落地/跳过/空转 — 熔断判据的三源）──
        if rl.landed:
            self.state.n_landed += 1
            self.state.consecutive_idle = 0
        elif rl.skipped_reason or rl.error:
            self.state.n_skipped += 1
            self.state.consecutive_idle = 0        # 跳过≠空转（有原因）
        elif rl.chain_verdict in (None, "blocked"):
            self.state.consecutive_idle += 1       # 无可落地动作 ⇒ 空转计数
        else:
            self.state.consecutive_idle = 0
        self.state.round_no = n
        self._append_log(rl)
        self._save_state()
        if self.on_round:
            self.on_round(rl)
        return rl

    # ── 主循环（四条熔断纪律的执行点）──
    def run(self, *, rounds: int | None = None,
            budget_seconds: float | None = None) -> dict[str, Any]:
        """★ 跑到停机条件（rounds 数到 / 预算尽 / stop / 连空转超限）。"""
        self.install_signal_handlers()
        t0 = time.time()
        stop_reason = "rounds_exhausted"
        try:
            while True:
                if self.state.stop_requested:
                    stop_reason = "signal"
                    break
                if self._stop_file_present():
                    stop_reason = "stop_file"
                    break
                if rounds is not None and self.state.round_no >= rounds:
                    break
                if budget_seconds is not None and (time.time() - t0) > budget_seconds:
                    stop_reason = "budget_exhausted"
                    break
                if self.state.consecutive_idle >= self.max_idle:
                    stop_reason = "consecutive_idle_fuse"
                    break
                self.run_one_round()
        finally:
            self._save_state()
            self.restore_signal_handlers()
        return {"stop_reason": stop_reason,
                "rounds_run": self.state.round_no,
                "n_landed": self.state.n_landed,
                "n_skipped": self.state.n_skipped,
                "n_error": self.state.n_error,
                "elapsed_s": round(time.time() - t0, 3),
                "state_file": self._state_path,
                "log_file": self._log_path}


DAEMON_MECHANICS: dict[str, str] = {
    "not_engine": "round_fn 注入（单轮逻辑用现有器官）; 本模块只驱动+记账+熔断",
    "four_fuses": "llm_timeout(跳过≠中断)/consecutive_idle(连空转停机)/stop_file/SIGINT(收尾后退出)",
    "checkpoint": "每轮 daemon_state.json 原子写 + rounds.jsonl 追加 ⇒ 崩溃可查可续",
    "cross_round": "跨轮分数序列沿用 e2e 的 score_history.jsonl（不另立第二账本）",
    "no_http": "前台 CLI 循环, 不做 HTTP 服务（无需求证据 — G4 不扩权）; 常驻由 cron 包装",
    "skip_not_idle": "跳过（有原因）≠空转（无可落地动作）— 熔断计数分开",
}


def main(argv: list[str] | None = None) -> int:
    """CLI 入口（--rounds/--budget-seconds/--state-dir/--once）。"""
    import argparse

    ap = argparse.ArgumentParser(prog="dwc.daemon",
                                 description="DWC 常驻循环（R164）")
    ap.add_argument("--rounds", type=int, default=None)
    ap.add_argument("--budget-seconds", type=float, default=None)
    ap.add_argument("--state-dir", default="runtime/daemon")
    ap.add_argument("--once", action="store_true", help="单轮（= e2e 形态）")
    ap.add_argument("--demo", action="store_true",
                    help="演示 round_fn（无引擎依赖 — 验证循环本身）")
    args = ap.parse_args(argv)

    if not args.demo:
        print("★ 未给 --demo: 生产 round_fn 由调用方注入（本 CLI 不含引擎）")
        print("  用法示例见 DAEMON_MECHANICS.not_engine")
        return 2

    def _demo_round(n: int, d: Daemon) -> dict[str, Any]:
        # ★ 演示面: 只证明循环/记账/熔断跑得起来（不碰真引擎）
        return {"n_candidates": 0,
                "chain_verdict": "blocked",
                "blocked": ["demo:no-op"],
                "skipped_reason": "demo round（无引擎）"}

    d = Daemon(_demo_round, state_dir=args.state_dir)
    out = d.run(rounds=(1 if args.once else args.rounds),
                budget_seconds=args.budget_seconds)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
