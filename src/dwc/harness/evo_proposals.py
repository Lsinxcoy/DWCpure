# -*- coding: utf-8 -*-
"""DWC-AUTO · 进化提案落盘（B3）

定位声明（DWC-AUTO · 进化系统）
  本模块是「live term 产出的提案 / 未映射签名」的持久层。
  它不生成提案、不判分、不做门 —— 只负责把 `evolver.diagnose()` 的
  产物**带上下文地**写下来，再原样读回去交给 `dwc_evo_round.py` 起草。

★★ 为什么需要这个模块（B2 留下的洞）
  B2 让 `DWC.run_term` 每轮把失败签名喂进 `evolver.diagnose`，但产物只在
  内存里返回一次：`Evolver._seen` 会按 proposal key 去重，**下一轮同样的
  提案不再返回** ⇒ 没人消费就等于丢掉。

★★ 为什么不直接用 DB 里的 failure_sig 表
  `failure_sig` 表只有 (c, q, m, node_id) —— **没有 fn，也没有 task 列**。
  `dwc_evo_round.py` 因此只能用 `--fn/--task` 硬编码参数
  （R279 自陈："多任务泛化等 node_id→task 映射落地后再做"）。
  而 live 路径（judge 的 sig）**天然带 fn 与 task_id** ⇒ 落盘比读库更准。

★★ 记录形态（append-only jsonl，一行一条）

  {"kind": "proposal",  "ts": ..., "term_id": ..., "chain_id": ...,
   "key": "c:q:fn", "sig": {...}, "proposal": {proposal_id, component,
   target, patch, rationale, operator}}

  {"kind": "unmapped",  "ts": ..., "term_id": ..., "chain_id": ...,
   "key": "c:q:fn", "sig": {...}}

  {"kind": "consumed",  "ts": ..., "keys": ["c:q:fn", ...]}

  消费语义：`consumed` 里出现过的 key ⇒ 后续 `pending_unmapped` 不再返回
  （避免 evo_round 每天重复起草同一簇）。
"""
from __future__ import annotations

import io
import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional, Set

from dwc.foundation.paths import find_root

ROOT = find_root()
DEFAULT_PATH = os.path.join(ROOT, "var", "evo_proposals.jsonl")

#: 读盘时坏行计数（G7: 坏数据不静默吞掉）
_READ_ERRORS = {"n": 0, "last": ""}


def note_read_error(why: str) -> None:
    _READ_ERRORS["n"] += 1
    _READ_ERRORS["last"] = why


def read_error_count() -> int:
    return _READ_ERRORS["n"]


def read_error_last() -> str:
    return _READ_ERRORS["last"]


def append_records(path: str, records: Iterable[Dict[str, Any]]) -> int:
    """append-only 写盘，返回写入行数。

    ★ 目录不存在就建（var/ 常被清空）；写失败 raise —— 静默丢提案
      等于让进化系统重新失明，属 G7 同族病。
    """
    rows = [r for r in records if isinstance(r, dict)]
    if not rows:
        return 0
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def read_records(path: str) -> List[Dict[str, Any]]:
    """读全量记录；坏行跳过并计数（不 raise —— 一行坏不该废掉整份账）。"""
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with io.open(path, "r", encoding="utf-8") as fh:
        for i, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, TypeError) as exc:
                note_read_error("line %d: %s" % (i, exc))
                continue
            if isinstance(obj, dict):
                out.append(obj)
            else:
                note_read_error("line %d: 非 dict (%r)" % (i, type(obj)))
    return out


def consumed_keys(records: List[Dict[str, Any]]) -> Set[str]:
    keys: Set[str] = set()
    for r in records:
        if r.get("kind") == "consumed":
            for k in (r.get("keys") or []):
                keys.add(str(k))
    return keys


def pending_unmapped(path: str,
                     exclude: Optional[Set[str]] = None) -> List[Dict[str, Any]]:
    """未映射签名中**尚未被消费**的那些（保持出现顺序，**不按 key 去重**）。

    ★ 不去重的理由：同 key 出现多次 = 该簇的频次，`run_round` 的
      `item["n"]` 靠它排序/判断"50 次失败同任务"这类深挖信号。
      需要每键一条时用 `group_by_key()`。
    """
    recs = read_records(path)
    done = consumed_keys(recs)
    if exclude:
        done |= {str(k) for k in exclude}
    out: List[Dict[str, Any]] = []
    for r in recs:
        if r.get("kind") != "unmapped":
            continue
        k = str(r.get("key") or "")
        if not k or k in done:
            continue
        sig = r.get("sig")
        if not isinstance(sig, dict):
            note_read_error("unmapped 缺 sig: key=%s" % k)
            continue
        if not all(sig.get(x) for x in ("c", "q", "fn")):
            note_read_error("unmapped sig 缺 c/q/fn: %r" % (sig,))
            continue
        out.append({"key": k, "sig": dict(sig)})
    return out


def group_by_key(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把 pending_unmapped 的条目聚成 `run_round` 认的簇形态。

    返回 `[{"key": k, "sigs": [sig, ...]}, ...]`，顺序 = 首次出现顺序。
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for it in items or []:
        k = str(it.get("key") or "")
        sig = it.get("sig")
        if not k or not isinstance(sig, dict):
            continue
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(dict(sig))
    return [{"key": k, "sigs": groups[k]} for k in order]


def mark_consumed(path: str, keys: Iterable[str]) -> int:
    """把已起草的簇 key 标记为消费（append 一条 consumed 记录）。"""
    ks = [str(k) for k in (keys or []) if k]
    if not ks:
        return 0
    return append_records(path, [{"kind": "consumed", "ts": time.time(),
                                  "keys": ks}])


def proposal_record(rep_meta: Dict[str, Any], sig: Dict[str, Any],
                    proposal: Any) -> Dict[str, Any]:
    """把 Proposal 对象转成可落盘记录（只取可审计字段，不搬私有态）。"""
    def _g(name, default=""):
        v = getattr(proposal, name, default)
        return v if v is not None else default

    return {
        "kind": "proposal",
        "ts": time.time(),
        "term_id": rep_meta.get("term_id", ""),
        "chain_id": rep_meta.get("chain_id", ""),
        "key": "%s:%s:%s" % (sig.get("c"), sig.get("q"), sig.get("fn")),
        "sig": dict(sig),
        "proposal": {
            "proposal_id": _g("proposal_id"),
            "component": _g("component"),
            "target": _g("target"),
            "patch": _g("patch"),
            "rationale": _g("rationale"),
            "operator": _g("operator", "improve"),
            "target_layer": _g("target_layer"),
        },
    }


def unmapped_record(rep_meta: Dict[str, Any],
                    sig: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": "unmapped",
        "ts": time.time(),
        "term_id": rep_meta.get("term_id", ""),
        "chain_id": rep_meta.get("chain_id", ""),
        "key": "%s:%s:%s" % (sig.get("c"), sig.get("q"), sig.get("fn")),
        "sig": dict(sig),
    }
