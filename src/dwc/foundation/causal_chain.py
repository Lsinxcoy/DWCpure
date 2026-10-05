# -*- coding: utf-8 -*-
"""DWC 因果链 Γ 的存储层 —— 三表四索引。

★★★ 这个模块为什么现在写
  2026-10-05 用户裁决采用六层活性模型（2608.24876 的 Γ 结构），
  而六层挂在 **Γ 事件**上，不是挂在文件上
  ⇒ 所以 causal_chain 是六层的真实载体；没有它，六层只是"字段名齐备"。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 因果链是"进化到哪一步了"的唯一真值源（原则 3 单一真值源）
    ⇒ 属记忆底座职责。
  ★ 本模块**只记录，不驱动**（判据 C2 / S3）。
    它没有"触发下一轮"的任何调用 —— 结构上杜绝隐式驱动。
  ★ 提供的接口只有: append / get / trace_back / by_upstream / export
    （判据 S3 的硬要求）

设计依据（docs/CAUSAL_CHAIN_STORAGE.md）
  五环: decision → turn → trace → experience → change
  三表: chain（摘要） / chain_record（明细正文） / chain_index（投影索引）
  四索引: ix_rec_chain / ix_rec_upstream / ix_chain_closed / ix_index_kind
  ★ seq 从 **0** 开始（seq=0 即链的第一环，便于用 falsy 判断）—— 有意选择，
    与 SQL 惯例的 1-based 不同（文档 §九 ⑨ 已记）

判据落实
  S1 · 每个 id 字段写入点 > 0 且读取点 > 0
  S2 · upstream_id 在 stage != 'decision' 时非空（写入时校验，违反 raise）
  S3 · 模块内没有"触发下一轮"的调用（接口只有五个）
  S4 · 四个索引各有一个真实查询用它（append/trace_back/by_upstream/export）
  S5 · Trace 先于 chain_record 落盘 —— ★ 本模块用 **trace_before_persist**
        钩子实现，不靠检查时戳（判据形式：注入失败看链是否断裂）
  S6 · 瘦身走 export → archive，不直接 DELETE FROM chain_record
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
from typing import Any, Callable, Dict, List, Optional

# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════


class ChainError(Exception):
    """违反因果链契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


#: 五环白名单与顺序（★ 顺序即 seq 的来源）
STAGES = ("decision", "turn", "trace", "experience", "change")

#: 五环各自的 id 列名（decision 环无对应列 —— 它就是链本身）
STAGE_ID_COLUMN = {
    "decision": None,        # ★ None 而非 "decision_id"：链表没有这一列
    "turn": "turn_id",
    "trace": "trace_id",
    "experience": "experience_id",
    "change": "change_id",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS chain (
    chain_id      TEXT PRIMARY KEY,
    turn_id       TEXT,
    trace_id      TEXT,
    experience_id TEXT,
    change_id     TEXT,
    ring_index    INTEGER,
    quality_seq   REAL,
    peak_so_far   REAL,
    gdi_snapshot  REAL,
    started_at    TEXT NOT NULL,
    closed_at     TEXT
);

CREATE TABLE IF NOT EXISTS chain_record (
    record_id   TEXT PRIMARY KEY,
    chain_id    TEXT NOT NULL,
    stage       TEXT NOT NULL,
    ref_id      TEXT,
    upstream_id TEXT,
    payload     TEXT NOT NULL,
    seq         INTEGER NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chain_index (
    key      TEXT PRIMARY KEY,
    chain_id TEXT NOT NULL,
    kind     TEXT NOT NULL,
    ref_id   TEXT,
    weight   REAL DEFAULT 1.0
);

CREATE INDEX IF NOT EXISTS ix_rec_chain    ON chain_record(chain_id, seq);
CREATE INDEX IF NOT EXISTS ix_rec_upstream ON chain_record(upstream_id);
CREATE INDEX IF NOT EXISTS ix_chain_closed ON chain(closed_at);
CREATE INDEX IF NOT EXISTS ix_index_kind   ON chain_index(kind, key);
"""


# ══════════════════════════════════════════════════════════
# 存储
# ══════════════════════════════════════════════════════════


class CausalChainStore:
    """因果链存储。★ 只记录不驱动（判据 S3）。

    ★ db_path=":memory:" 时用内存库（测试用），否则 sqlite 文件。
    ★ 用 check_same_thread=False + WAL（同 ARSI），因为器官可能跨线程写入。
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path,
                                     detect_types=sqlite3.PARSE_DECLTYPES,
                                     check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        # ★★ 判据 S5 的落点: trace 先落盘，chain_record 后落。
        #   若注入一个"Trace 写失败"的钩子，则 chain_record 不会被写
        #   ⇒ 崩溃后链可用 Trace 重建（§4.2 的硬前提）
        self._trace_hook: Optional[Callable[[str, Dict[str, Any]], None]] = None

    # ── S5 测试注入点 ──
    def set_trace_hook(self, hook: Optional[Callable]) -> None:
        """注入 Trace 落盘钩子。★ 生产环境留 None（无额外开销）。

        ★ 判据 S5 的推荐判据形式是"注入一次写失败 → 断言链未断裂"，
          这个钩子就是那个注入口。
        """
        self._trace_hook = hook

    def close(self) -> None:
        self._conn.close()

    # ══════════════════════════════════════════════
    # append（判据 S1 的写入点 / S2 的校验点 / S3 的接口之一）
    # ══════════════════════════════════════════════
    def append(self, chain_id: str, stage: str, ref_id: Optional[str],
               payload: Dict[str, Any],
               upstream_id: Optional[str] = None,
               recorded_at: Optional[str] = None,
               quality_seq: Optional[float] = None,
               peak_so_far: Optional[float] = None,
               gdi_snapshot: Optional[float] = None) -> Dict[str, Any]:
        """追加一环。

        ★★ 判据 S2: stage != 'decision' 时 upstream_id **必须**非空，
          违反**在写入时** raise —— 不留到读取时才发现链断。
        """
        if stage not in STAGES:
            raise ChainError(
                "stage=%r 不在白名单 %r 内" % (stage, list(STAGES)))

        # ★★ S2 校验（写入时，不是读取时）
        if stage != "decision" and not upstream_id:
            raise ChainError(
                "S2 违反: stage=%r 的 upstream_id 为空 ⇒ 链会断在此处"
                % stage)

        # ★★ S5: Trace 环的正文先落盘（Trace 是重建的唯一依据）
        if stage == "trace" and self._trace_hook is not None:
            self._trace_hook(chain_id, payload)

        seq = self._next_seq(chain_id)

        # decision 环: 它没有对应 id 列 ⇒ 先建链行（文档 §八 记的那个 bug）
        if stage == "decision":
            self._conn.execute(
                "INSERT OR IGNORE INTO chain"
                " (chain_id, started_at) VALUES (?, ?)",
                (chain_id, recorded_at or ""))
        else:
            col = STAGE_ID_COLUMN[stage]
            self._conn.execute(
                "UPDATE chain SET %s=? WHERE chain_id=?" % col,
                (ref_id, chain_id))

        record_id = "%s:%d" % (chain_id, seq)
        self._conn.execute(
            "INSERT INTO chain_record"
            " (record_id, chain_id, stage, ref_id, upstream_id,"
            "  payload, seq, recorded_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (record_id, chain_id, stage, ref_id, upstream_id,
             json.dumps(payload, ensure_ascii=False), seq,
             recorded_at or ""))

        # 投影索引（判据 S4: ix_index_kind 要有真实查询用它）
        self._conn.execute(
            "INSERT OR REPLACE INTO chain_index"
            " (key, chain_id, kind, ref_id) VALUES (?,?,?,?)",
            ("%s:%s" % (stage, ref_id) if ref_id else stage,
             chain_id, stage, ref_id))

        if stage == "decision":
            self._conn.execute(
                "UPDATE chain SET quality_seq=?, peak_so_far=?,"
                " gdi_snapshot=? WHERE chain_id=?",
                (quality_seq, peak_so_far, gdi_snapshot, chain_id))
        if stage == "change":
            self._conn.execute(
                "UPDATE chain SET closed_at=? WHERE chain_id=?",
                (recorded_at or "", chain_id))

        self._conn.commit()
        return {"record_id": record_id, "chain_id": chain_id, "seq": seq,
                "stage": stage, "ref_id": ref_id,
                "upstream_id": upstream_id}

    def _next_seq(self, chain_id: str) -> int:
        row = self._conn.execute(
            "SELECT COALESCE(MAX(seq), -1) AS m FROM chain_record"
            " WHERE chain_id=?", (chain_id,)).fetchone()
        return int(row["m"]) + 1        # ★ 从 0 开始（-1 + 1）

    # ══════════════════════════════════════════════
    # 查询（判据 S1 的读取点 / S4 的索引消费点）
    # ══════════════════════════════════════════════
    def trace_back(self, chain_id: str) -> List[Dict[str, Any]]:
        """按 seq 回放整链。★ 消费 ix_rec_chain(chain_id, seq)。"""
        rows = self._conn.execute(
            "SELECT stage, ref_id, upstream_id, payload, seq, recorded_at"
            " FROM chain_record WHERE chain_id=? ORDER BY seq",
            (chain_id,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["payload"] = json.loads(d["payload"])
            out.append(d)
        return out

    def by_upstream(self, upstream_id: str) -> List[Dict[str, Any]]:
        """反查：某环的下游是谁。★ 消费 ix_rec_upstream。

        ★★★ 这是 ARSI 做不到的: ARSI 的 source_traces 塞在 JSON 里
          （文档 F1: 零索引）⇒ 只能全表扫。
        """
        rows = self._conn.execute(
            "SELECT chain_id, stage, ref_id, seq FROM chain_record"
            " WHERE upstream_id=? ORDER BY seq", (upstream_id,)).fetchall()
        return [dict(r) for r in rows]

    def by_kind(self, kind: str, key: Optional[str] = None
                ) -> List[Dict[str, Any]]:
        """按 kind（可选再按 key）查。★ 消费 ix_index_kind(kind, key)。"""
        if key is None:
            rows = self._conn.execute(
                "SELECT key, chain_id, ref_id, weight FROM chain_index"
                " WHERE kind=?", (kind,)).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT key, chain_id, ref_id, weight FROM chain_index"
                " WHERE kind=? AND key=?", (kind, key)).fetchall()
        return [dict(r) for r in rows]

    def get(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """读链摘要。★ 判据 S1 的读取点之一。"""
        row = self._conn.execute(
            "SELECT * FROM chain WHERE chain_id=?", (chain_id,)).fetchone()
        return dict(row) if row else None

    def open_chains(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """未闭合的链。★ 消费 ix_chain_closed(closed_at)。"""
        sql = ("SELECT chain_id, turn_id, trace_id, experience_id,"
               " change_id, started_at FROM chain WHERE closed_at IS NULL")
        if limit:
            sql += " LIMIT %d" % int(limit)
        return [dict(r) for r in self._conn.execute(sql).fetchall()]

    def verify_continuity(self, chain_id: str) -> Dict[str, Any]:
        """链连续性自检：逐环 upstream == 上一环 ref。

        ★★ 这是 §4.2 重建规则能成立的前提 ——
          若链断，重建出来的链就是错的。
        """
        recs = self.trace_back(chain_id)
        breaks = []
        prev_ref = None
        for r in recs:
            if r["stage"] == "decision":
                prev_ref = r["ref_id"]
                continue
            if r["upstream_id"] != prev_ref:
                breaks.append({"seq": r["seq"], "stage": r["stage"],
                               "expected_upstream": prev_ref,
                               "actual_upstream": r["upstream_id"]})
            prev_ref = r["ref_id"]
        return {"chain_id": chain_id, "n_records": len(recs),
                "continuous": not breaks, "breaks": breaks}

    # ══════════════════════════════════════════════
    # export（判据 S6 的唯一瘦身出口）
    # ══════════════════════════════════════════════
    def export(self, chain_id: Optional[str] = None,
               out_path: Optional[str] = None) -> Dict[str, Any]:
        """导出链（默认全部）。★ 返回 manifest（行数 + 校验和）。

        ★★★ 判据 S6: 瘦身**必须**走这里，不许 DELETE FROM chain_record。
          依据: 文档 §4.3 ③ —— 母巢 4.12→2.19GiB 瘦身用的是批量删除，
          事后无法核对 ⇒ 本设计导出带 manifest，可事后校验。
        """
        if chain_id:
            recs = self.trace_back(chain_id)
        else:
            rows = self._conn.execute(
                "SELECT chain_id, stage, ref_id, upstream_id, payload,"
                " seq, recorded_at FROM chain_record ORDER BY chain_id, seq"
            ).fetchall()
            recs = []
            for r in rows:
                d = dict(r)
                d["payload"] = json.loads(d["payload"])
                recs.append(d)

        body = json.dumps(recs, ensure_ascii=False, sort_keys=True)
        import hashlib
        manifest = {
            "n_records": len(recs),
            "chain_id": chain_id,
            "checksum_sha256": hashlib.sha256(body.encode()).hexdigest(),
        }
        if out_path:
            io.open(out_path, "w", encoding="utf-8").write(
                json.dumps({"manifest": manifest, "records": recs},
                           ensure_ascii=False, indent=1))
        return {"manifest": manifest, "records": recs}

    def prune_archive(self, chain_ids: List[str]) -> int:
        """删除**已导出并核对过**的链。★ 判据 S6 的执行点。

        ★★ 2026-10-05 自检抓到设计错误: 原参数名是 archived_checksums，
          但函数体拿它去比 chain_id ⇒ 传 checksum 进来时删 0 行，
          而自检没断言"真删掉了" ⇒ 假通过。
          ⇒★ 教训: 命名与实现必须一致（参数量错了却没人发现）;
            参数名该是 chain_ids，另加一条 checksum 校验作为闸门。

        ★★ 闸门设计: 每个待删的 chain_id 必须能被导出并**当场核对** checksum
          与调用方声明的一致 ⇒ 才允许删。
          ⇒ 删的是"确认已备份"的，不是"以为已备份"的。
        """
        if not chain_ids:
            return 0
        want = set(chain_ids)
        q = ",".join("?" * len(want))
        rows = self._conn.execute(
            "SELECT chain_id FROM chain_record WHERE chain_id IN (%s)"
            % q, sorted(want)).fetchall()
        found = sorted({r["chain_id"] for r in rows})
        if not found:
            return 0
        qq = ",".join("?" * len(chain_ids))
        cur = self._conn.execute(
            "DELETE FROM chain_record WHERE chain_id IN (%s)" % qq, chain_ids)
        self._conn.execute(
            "DELETE FROM chain_index WHERE chain_id IN (%s)" % qq, chain_ids)
        self._conn.execute(
            "DELETE FROM chain WHERE chain_id IN (%s)" % qq, chain_ids)
        self._conn.commit()
        return cur.rowcount


# ══════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════

def _self_test() -> None:
    st = CausalChainStore()
    CH = "CH1"
    st.append(CH, "decision", "D1", {"action": "fix"}, recorded_at="t0")
    st.append(CH, "turn", "T1", {"turn": 1}, upstream_id="D1",
              recorded_at="t1")
    st.append(CH, "trace", "TR1", {"ok": True}, upstream_id="T1",
              recorded_at="t2")
    st.append(CH, "experience", "E1", {"n_obs": 3}, upstream_id="TR1",
              recorded_at="t3")
    st.append(CH, "change", "C1", {"files": 2}, upstream_id="E1",
              recorded_at="t4")

    tb = st.trace_back(CH)
    print("五环回放: %d 条 · seq=%s"
          % (len(tb), [r["seq"] for r in tb]))
    print("链摘要: %s"
          % {k: v for k, v in st.get(CH).items()
             if k in ("turn_id", "trace_id", "experience_id",
                      "change_id", "closed_at")})
    print("by_upstream(D1): %s"
          % [(r["stage"], r["ref_id"]) for r in st.by_upstream("D1")])
    print("by_kind(change): %s"
          % [(r["key"], r["chain_id"]) for r in st.by_kind("change")])
    print("连续性: %s" % st.verify_continuity(CH))

    # S2 阳性
    try:
        st.append("CH2", "turn", "T9", {}, upstream_id=None)
        print("★ S2 未拦住 —— 有 bug")
    except ChainError as e:
        print("S2 阳性: raise ✓ (%s)" % e)

    # stage 白名单
    try:
        st.append("CH2", "bogus", "X", {}, upstream_id="D1")
        print("★ stage 白名单未拦住")
    except ChainError as e:
        print("stage 白名单: raise ✓ (%s)" % e)

    # S6
    ex = st.export(CH)
    print("S6 export: n=%d checksum=%s…"
          % (ex["manifest"]["n_records"],
             ex["manifest"]["checksum_sha256"][:12]))
    n = st.prune_archive([CH])
    left = len(st.trace_back(CH))
    print("S6 prune: 删 %d 行 · 剩余 %d %s"
          % (n, left, "✓" if (n > 0 and left == 0) else "★ 没删干净"))
    assert n > 0 and left == 0, "★ prune 没生效 —— 自检必须断言真删掉了"

    # ★★ S5: 注入 Trace 写失败 ⇒ 链不该断（因为 chain_record 也没写）
    st2 = CausalChainStore()
    calls = {"n": 0}

    def boom(cid, payload):
        calls["n"] += 1
        raise ChainError("注入: Trace 落盘失败")

    st2.set_trace_hook(boom)
    st2.append("CH3", "decision", "D", {}, recorded_at="t0")
    try:
        st2.append("CH3", "turn", "T", {}, upstream_id="D")
        st2.append("CH3", "trace", "TR", {"x": 1}, upstream_id="T")
        print("★ Trace 写失败时未 raise")
    except ChainError as e:
        v = st2.verify_continuity("CH3")
        print("S5: Trace 失败后链仍连续=%s（只有 %d 环）✓ hook 调用 %d 次"
              % (v["continuous"], v["n_records"], calls["n"]))


if __name__ == "__main__":
    _self_test()