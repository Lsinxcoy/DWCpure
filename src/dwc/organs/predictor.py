# -*- coding: utf-8 -*-
"""R231 · 行为结果预测器（视图层）—— RSI-Anything「预测引导选择」的 DWC 落地。

★★★ 定位（G1）: **DWC-AUTO** —— agent 对自己动作/任务结果的成功率预测。
★★★ TRUTH_SOURCE: **无独立判定面** —— 观测全部来自既有事实源:
  · 树族键 "tree:{tree_id}/{node_id}" → 读 world_model 谱系 (n_obs,n_pass)
    —— 树=事实层, predictor 单向读, **绝不回写树**（REPORT ⑤b 边界）
  · 台账族键 (op:/rung:/fail:) → 自记 var/dwc_predictor.jsonl（append-only）
★★★ W4 同族纪律: 只吃布尔观测 —— 不读任何 confidence 字段。

★ 数学同源声明（调整A的依据）:
  树的收束判据 Laplace 平滑 (n_pass+1)/(n_obs+2) **就是** Beta(1,1) 后验均值;
  台账族用显式 Beta(α,β) 计数（先验 Beta(1,1) ⇒ α=1+成功数, β=1+失败数）。
  两族 predict() 输出同一口径: p̂ = 后验均值, uncertainty = 1/(α+β)。

★ 版本化: checkpoint 只持久化**台账族**计数（树族读树即得, 不复制）;
  sha 校验 + VERSION 匹配, 不符拒载（rsi.py:36-39 同款身份校验）。
  replay: 台账族从 jsonl 全量重放重建（append-only 即 replay 源 — RSI 防遗忘）。
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from dwc.foundation.paths import find_root

ROOT = find_root()
#: 台账族观测日志（append-only — 即 replay 源）
PRED_LOG = os.path.join(ROOT, "var", "dwc_predictor.jsonl")
#: 台账族计数 checkpoint（视图层产物 — 可随时从日志重建）
PRED_CKPT = os.path.join(ROOT, "var", "dwc_predictor_ckpt.json")

VERSION = "pred-v1"


class PredictorError(Exception):
    pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


class OutcomePredictor:
    """行为结果预测器 — Beta 共轭后验（台账族）+ 树谱系直读（树族）。

    ★★★ 定位: **视图层** —— 不是事实源。树族统计永远以树为准;
      台账族以 jsonl 为准（checkpoint 只是加速视图）。
    """

    VERSION = VERSION

    def __init__(self, log_path: str = PRED_LOG,
                 world_model: Any = None) -> None:
        self.log_path = log_path
        self.world_model = world_model          # 树族读取源（可后注入/每 term 换代）
        self._counts: Dict[str, List[int]] = {}  # 台账族: key -> [α, β]（先验 1,1）
        self._recent: List[Tuple[str, bool]] = []  # 校准窗口（近 N 观测）
        self._lock = threading.Lock()
        self._replay()

    # ── 事实读取 ──────────────────────────────────────────────
    def _replay(self) -> None:
        """★ replay 防遗忘: 台账族计数 = 重放 append-only 日志（不是增量补丁）。"""
        if not os.path.exists(self.log_path):
            return
        for ln in io.open(self.log_path, encoding="utf-8").read().splitlines():
            if not ln.strip():
                continue
            try:
                row = json.loads(ln)
            except ValueError:
                continue                       # 单行坏不毁全量（台账现实）
            key, ok = str(row.get("key", "")), bool(row.get("success"))
            if key:
                self._bump(key, ok)

    def _bump(self, key: str, ok: bool) -> None:
        a, b = self._counts.get(key, [1, 1])
        self._counts[key] = [a + (1 if ok else 0), b + (0 if ok else 1)]
        self._recent.append((key, ok))
        if len(self._recent) > 500:
            self._recent = self._recent[-500:]

    def set_world_model(self, world_model: Any) -> None:
        """★ 每 term 注入活体世界模型（agent 循环里树随构造换代 — 见 iwm 教训）。"""
        self.world_model = world_model

    # ── 观测（仅台账族; 树族绝不写）────────────────────────────
    def observe(self, key: str, success: bool, evidence_ref: str = "") -> None:
        """台账族观测: 追加日志 + 更新计数。★ key 以 "tree:" 开头即拒
        （结构上禁止双写 — 树族只许读）。"""
        if key.startswith("tree:"):
            raise PredictorError(
                "树族键不许 observe（树=事实层, 双写即不一致风险）: %r" % key)
        row = {"key": key, "success": bool(success),
               "evidence": evidence_ref,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with self._lock:
            with io.open(self.log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            self._bump(key, bool(success))

    # ── 预测（两族同口径）──────────────────────────────────────
    def _tree_obs(self, key: str) -> Optional[Tuple[int, int]]:
        """"tree:{tree_id}/{node_id}" → 谱系 (n_obs, n_pass); 不可用返回 None。"""
        if self.world_model is None:
            return None
        try:
            tree_id, node_id = key[len("tree:"):].split("/", 1)
            tree = self.world_model.trees.get(tree_id)
            if tree is None:
                return None
            return tree.lineage_obs(node_id)
        except (ValueError, AttributeError, KeyError):
            return None

    def predict(self, key: str) -> Dict[str, Any]:
        """★ 统一口径: p̂ = Beta(1,1) 后验均值; uncertainty = 1/(α+β)。
        树族: α=1+n_pass, β=1+(n_obs-n_pass)（与收束 Laplace 同式）。
        树不可用 ⇒ 先验 p=0.5 且 source 标记（诚实缺失, 不装有）。"""
        if key.startswith("tree:"):
            obs = self._tree_obs(key)
            if obs is None:
                return {"p": 0.5, "uncertainty": 1.0, "n": 0,
                        "source": "tree_unavailable", "version": self.VERSION}
            n_obs, n_pass = obs
            alpha, beta = 1 + n_pass, 1 + (n_obs - n_pass)
            return {"p": alpha / (alpha + beta), "uncertainty": 1.0 / (alpha + beta),
                    "n": n_obs, "source": "tree", "version": self.VERSION}
        with self._lock:
            a, b = self._counts.get(key, [1, 1])
        return {"p": a / (a + b), "uncertainty": 1.0 / (a + b),
                "n": a + b - 2, "source": "ledger", "version": self.VERSION}

    def predict_batch(self, keys: List[str]) -> Dict[str, Dict[str, Any]]:
        return {k: self.predict(k) for k in keys}

    # ── 校准（声称=实测的落点）─────────────────────────────────
    def calibrate(self, recent: int = 200) -> Dict[str, Any]:
        """Brier 分数 + 五桶 reliability — 校准度是实测的, 不是自我声称。"""
        rows = self._recent[-recent:]
        if not rows:
            return {"n": 0, "brier": None, "note": "无观测"}
        se = []
        ps = []
        for key, ok in rows:
            pr = self.predict(key)["p"]
            ps.append(pr)
            se.append((pr - (1.0 if ok else 0.0)) ** 2)
        buckets = [[0, 0, 0] for _ in range(5)]      # [Σp, Σy, n]
        for (key, ok), pr in zip(rows, ps):
            idx = min(4, max(0, int(pr * 5)))
            buckets[idx][0] += pr
            buckets[idx][1] += 1.0 if ok else 0.0
            buckets[idx][2] += 1
        return {"n": len(rows), "brier": sum(se) / len(se),
                "reliability": [
                    {"bin": "%d-%d" % (i * 20, (i + 1) * 20),
                     "p_mean": (b[0] / b[2]) if b[2] else None,
                     "y_mean": (b[1] / b[2]) if b[2] else None,
                     "n": b[2]} for i, b in enumerate(buckets)],
                "version": self.VERSION}

    # ── 持久化（台账族视图; 树族不复制）────────────────────────
    def checkpoint(self) -> Dict[str, Any]:
        payload = {"version": self.VERSION,
                   "counts": {k: v for k, v in sorted(self._counts.items())}}
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        doc = {"sha": _sha(body), "doc": payload,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        os.makedirs(os.path.dirname(PRED_CKPT), exist_ok=True)
        with io.open(PRED_CKPT, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, ensure_ascii=False, indent=1)
        return {"path": PRED_CKPT, "sha": doc["sha"], "keys": len(self._counts)}

    @classmethod
    def load(cls, path: str = PRED_CKPT, log_path: str = PRED_LOG,
             world_model: Any = None) -> "OutcomePredictor":
        """★ 身份校验: sha 不符 / version 不符 ⇒ 拒载（rsi.py 同款）。"""
        if not os.path.exists(path):
            raise PredictorError("checkpoint 不存在: %s" % path)
        doc = json.load(io.open(path, encoding="utf-8"))
        body = json.dumps(doc.get("doc"), ensure_ascii=False, sort_keys=True)
        if doc.get("sha") != _sha(body):
            raise PredictorError("checkpoint sha 不符 — 拒载（可能损坏/被改）")
        if doc.get("doc", {}).get("version") != VERSION:
            raise PredictorError("version 不符: %s ≠ %s — 拒载"
                                 % (doc.get("doc", {}).get("version"), VERSION))
        p = cls(log_path=log_path, world_model=world_model)
        return p                            # 日志 replay 为准 — ckpt 是校验视图
