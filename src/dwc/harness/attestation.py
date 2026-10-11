# -*- coding: utf-8 -*-
"""attestation · 声称 vs 实测双账（R196 · Z 类落地 乙类 B3）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只登记声称 + 挂实测证据 + 列未挂者; **不拦合入、不自动生成声称**。

★★★★★ **无论文依据**（R196 记账 — 诚实条款, 违反即作废）
  R193 把 dual 记成"2606.06350 的 public/private" ⇒ **出处错**: 该论文
  `privacy` 指 **Private-Science 数据集许可**, 不是双动作空间机制; 57 篇
  落档全文 grep `public[- ]private` = 0 命中。
  ⇒ 本模块是 **DWC 自定义能力**（把 DWC 自己的核心纪律"声称=实测"变成
    可机的双账面）, 不是任何论文机制的搬运。docstring 不许出现「论文说」字样。

★★★ TRUTH_SOURCE（判据 G2）
  ★ **不是门**: `unattested()` 只**列出**未挂实测的声称, 不抛异常不返回 False。
    拦合入是 gate 的活 — 再造一道门 = 第三口径（R183 禁）。
  ★ **不许自动生成声称**: 声称只能由人或轮次流程显式写。自动造声称再自己
    认证 = 自证预言（R188 已记的坑）。
  ★ **只对 DWC 自身**: 不是给外部系统用的审计框架（无通用化野心）。

★★★ 为什么这是真缺口（R196 机器证据）
  "声称=实测"是 DWC 的核心纪律, 但它现在**散在注释和记忆里** — memory 里
  写着"声称vs实测"铁律, repo 里却**没有一处机器账面**能回答"这条声称挂没挂
  实测"。本模块把它变成 jsonl 双账 ⇒ G5 有观察面可查。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

#: ★ 声称行 schema 版本
ATTESTATION_SCHEMA_VERSION = 1


def claim(archive_path: str, round_gen: int, subsystem: str,
          text: str, by: str = "human") -> str:
    """登记一条声称 ⇒ 返回 claim_id（`c<gen>-<seq>` — 同 gen 内自增）。

    ★ `by` 记来源（人/轮次流程）; **不提供 `by="auto"` 的自动入口** —
      自动声称必须显式写 by 值并担责（防自证预言）。
    ★ 同 (gen, subsystem, text) 已存在 ⇒ **不重复登记**, 返既有 id
      （幂等 — 重复调用不造重复账）。
    """
    os.makedirs(os.path.dirname(os.path.abspath(archive_path)),
                exist_ok=True)
    rows = _read(archive_path)
    for r in rows:
        if (r.get("kind") == "claim" and r.get("gen") == round_gen
                and r.get("subsystem") == subsystem
                and r.get("text") == text):
            return r["claim_id"]
    seq = 1 + sum(1 for r in rows if r.get("kind") == "claim"
                  and r.get("gen") == round_gen)
    cid = "c%d-%d" % (round_gen, seq)
    rows.append({"kind": "claim", "schema": ATTESTATION_SCHEMA_VERSION,
                 "claim_id": cid, "gen": round_gen, "subsystem": subsystem,
                 "text": text, "by": by, "ts": round(time.time(), 3),
                 "attested": False, "measured": None, "evidence_ref": None})
    _write(archive_path, rows)
    return cid


def attest(archive_path: str, claim_id: str, evidence_ref: str,
           measured: Any) -> None:
    """给声称挂实测证据（measured 任意可 JSON 化的实测值）。

    ★ claim_id 不存在 ⇒ raise（挂到不存在的声称上 = 造孤儿证据, G7 同族）。
    ★ 已挂 ⇒ 覆盖（实测可复跑修正; 但旧值不留 — 双账是"当前最好认知"不是档案）。
    """
    rows = _read(archive_path)
    hit = [r for r in rows if r.get("kind") == "claim"
           and r.get("claim_id") == claim_id]
    if not hit:
        raise KeyError("attest: claim_id=%r 不在账里 ⇒ 拒绝挂孤儿证据"
                       % claim_id)
    hit[0].update({"attested": True, "measured": measured,
                   "evidence_ref": evidence_ref,
                   "attested_ts": round(time.time(), 3)})
    _write(archive_path, rows)


def unattested(archive_path: str,
               round_gen: Optional[int] = None) -> List[Dict[str, Any]]:
    """声称了但没挂实测的（**观察面 — 不抛不拦**）。

    ★ gen=None ⇒ 全部轮次; gen=给定 ⇒ 只该轮。
    ★ 返回的是**声称行的投影副本**（id/subsystem/text/by/gen）— 不把 measured
      等已挂字段塞进结果（未挂者这些字段全是 None, 塞进去是噪声）。
    ★ 文件不存在 ⇒ []（从未声称 = 无未挂, 合法一等输出）。
    """
    rows = _read(archive_path)
    out: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("kind") != "claim" or r.get("attested"):
            continue
        if round_gen is not None and r.get("gen") != round_gen:
            continue
        out.append({k: r.get(k) for k in
                    ("claim_id", "subsystem", "text", "by", "gen")})
    return out


def _read(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _write(path: str, rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)          # 原子替换 ⇒ 半截写入不致坏账


ATTESTATION_MECHANICS = {
    "not_a_gate": "unattested 只列出不拦合入; 拦是 gate 的活（第三口径禁）",
    "no_auto_claims": "claim 无 auto 入口; 自动声称须显式 by 并担责（自证预言防）",
    "no_paper_basis": "R193 把 dual 引到 2606.06350 属出处错（privacy=数据许可）⇒ DWC 自定义能力",
}
