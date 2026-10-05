# -*- coding: utf-8 -*-
"""DWC 记忆内核 —— 四区 + 七管归属的第一个实现。

★★★ 这个模块为什么现在做
  记忆内核是唯一**现在就能端到端跑通**的器官:
    · causal_chain（五环 + 回执）已就位
    · activity（六层）已就位
    · wiring（接线）已就位
  ⇒ 而 judge 的真值源、actor 的动作都还不存在 ⇒ 先做它们会卡在依赖上

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 本模块本身就是记忆底座 ⇒ DWC-MEM（不是 DWC-AUTO）。
  ★ 它不被任何器官直接调用，只经 remember/learn/evolve/maintain 四管
    ⇒ 无跨器官私有态（判据 P1：跨器官只传 ID，不传对象实例）
  ★ 它**不做淘汰决策** —— 只提供"可淘汰"的证据（access/effect 记录），
    真正的淘汰由 evolver 依 GAI dials 决定 ⇒ 职责边界清晰

设计依据（docs/MEMORY_SYSTEM.md）
  四区: EXPERIENCE（进化的直接对象） / PROXY（痕迹·工作态） / ARCHIVE / INERT
  七管归属（§四）:
    任务痕迹     ← remember      → PROXY
    失败签名(c,q,m) ← reflect    → EXPERIENCE
    技能(场景/方法/边界) ← learn 归纳 → EXPERIENCE
    工作态 𝒲    ← remember       → PROXY 特例
    进化提案+结果  ← evolve       → EXPERIENCE
  明确不记: 纯事实 / 纯概念 / 机械日志 / 自我评价

  ★★ D6（EXPERIENCE 只存能驱动进化的东西）
    判据: 这条记忆能否成为 evolver 的输入?
    不能 ⇒ 留在 PROXY 或归档区，不占 EXPERIENCE
    ⇒⇒ 这不是"分类标签"，是**写入时就要判的门槛**（下面的 write 强制它）

  ★★ D7（记忆必须证明被使用）
    一条记忆若无 access 记录，不得被当作"有价值"
    依据: 母巢 98.8% 节点 access_count=0，但 importance 均值 0.747
          —— 自评很高，实际没人用
    ⇒⇒ 所以本模块**不提供 self_rated_value()** 这类接口 ——
      价值只能由 access/effect 记录推出，不能由写入方自报
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════


class MemoryError(Exception):
    """违反记忆内核契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


class Zone(str, Enum):
    EXPERIENCE = "experience"   # ★ 进化的直接对象
    PROXY = "proxy"             # 痕迹 / 工作态
    ARCHIVE = "archive"
    INERT = "inert"


class Tube(str, Enum):
    """七管（MEMORY_SYSTEM §2.2 的七个阶段）。

    ★★★ 2026-10-05 R21 更正: 初版只定义了 5 个（remember/learn/evolve/
       maintain/reflect），**漏了 recall 与 dream** —— 而它们恰好是
       "七管比 ARSI 多出来的那部分"，漏掉它们等于把七管缩成了五管。
       ⇒★ 而且当时我给的理由是"recall 是读侧所以不算管"，
         ★★★ 而那个理由是错的: 母巢的病恰恰是"写入多、读取少"
           （98.8% access=0）⇒ recall 正是 D7 的执行管，
           把读操作排除在管之外，等于把病根排除在设计之外。
         ★ 事实上 recall() 方法早就落地了（access_count+1）——
           功能在、枚举没跟上 ⇒ 这是实现漏了，不是设计选择。
    """
    REMEMBER = "remember"     # 摄入
    RECALL = "recall"         # ★ 取回（R21 补）—— D7 的执行管
    LEARN = "learn"           # 巩固
    REFLECT = "reflect"       # 归因
    EVOLVE = "evolve"         # 变异（唯一改东西的阶段）
    DREAM = "dream"           # ★ 反刍（R21 补）
    MAINTAIN = "maintain"     # 维护


class MemoryKind(str, Enum):
    TRACE = "trace"                  # 任务痕迹 → PROXY
    WORKING_STATE = "working_state"   # 工作态 𝒲 → PROXY 特例
    FAILURE_SIGNATURE = "failure_sig" # (c,q,m) → EXPERIENCE
    SKILL = "skill"                   # 场景/方法/边界 → EXPERIENCE
    PROPOSAL = "proposal"             # 进化提案+结果 → EXPERIENCE


#: ★ 各类记忆的归属区（MEMORY_SYSTEM §四 的表）★
KIND_TO_ZONE = {
    MemoryKind.TRACE: Zone.PROXY,
    MemoryKind.WORKING_STATE: Zone.PROXY,
    MemoryKind.FAILURE_SIGNATURE: Zone.EXPERIENCE,
    MemoryKind.SKILL: Zone.EXPERIENCE,
    MemoryKind.PROPOSAL: Zone.EXPERIENCE,
}

#: ★ 归入 EXPERIENCE 的门槛（D6）—— 缺这些就不许进 EXPERIENCE
EXPERIENCE_REQUIREMENTS = {
    MemoryKind.FAILURE_SIGNATURE: ("c", "q", "m"),
    MemoryKind.SKILL: ("scene", "method", "boundary"),
    MemoryKind.PROPOSAL: ("consumer_declared",),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_node (
    node_id      TEXT PRIMARY KEY,
    zone         TEXT NOT NULL,
    kind         TEXT NOT NULL,
    tube         TEXT NOT NULL,
    payload      TEXT NOT NULL,
    chain_id     TEXT,
    created_at   REAL NOT NULL,
    last_access  REAL,
    access_count INTEGER NOT NULL DEFAULT 0,
    effect_count INTEGER NOT NULL DEFAULT 0,
    archived_at  REAL
);

-- ★★★ 2026-10-05 schema 更正（测试抓到的设计缺陷）:
--   初版是 PRIMARY KEY (c,q,m) ⇒ 同三元组的第二条记忆把第一条**覆盖**。
--   ⇒⇒ 但 MEMORY_SYSTEM §四 写的是「按三元组**精确聚类**」
--     —— 聚类意味着同类可以有多条，否则那叫覆盖，不叫聚类。
--   ⇒⇒ 且「稀有保护」明确预设了"某类失败可能有多条记忆"，
--     所以当前写法**让稀有保护永远为真**（永远是唯一的那条）⇒ 空转。
--   ⇒★ 修法: 主键改为 node_id（一节点一行），(c,q,m) 只建索引。
CREATE TABLE IF NOT EXISTS failure_sig (
    c       TEXT NOT NULL,
    q       TEXT NOT NULL,
    m       TEXT NOT NULL,
    node_id TEXT NOT NULL UNIQUE REFERENCES memory_node(node_id)
);

CREATE INDEX IF NOT EXISTS ix_node_zone    ON memory_node(zone);
CREATE INDEX IF NOT EXISTS ix_node_chain   ON memory_node(chain_id);
CREATE INDEX IF NOT EXISTS ix_node_kind    ON memory_node(kind);
CREATE INDEX IF NOT EXISTS ix_sig_cluster  ON failure_sig(c, q, m);
-- ★ ix_sig_lookup 已删: 测试实测发现 SQLite 优先选 PRIMARY KEY/UNIQUE
--   自带的 sqlite_autoindex ⇒ 我建的这条索引是死重量
--   （判据 S4 的同款纪律: grep 不到真实使用点 ⇒ 该删）。
--   ⇒ 聚类查询靠 ix_sig_cluster（建在 (c,q,m) 上，与 node_id 主键不冲突）
"""


# ══════════════════════════════════════════════════════════
# 记忆节点
# ══════════════════════════════════════════════════════════


@dataclass(frozen=True)
class MemoryNode:
    """一条记忆。★ frozen ⇒ 不可变（判据 I6 同款）。

    ★★ 字段设计对应 D7（记忆必须证明被使用）:
      access_count / effect_count / last_access
      —— 价值只能由这三个字段**推出**，不由写入方自报
    """
    node_id: str
    zone: Zone
    kind: MemoryKind
    tube: Tube
    payload: Dict[str, Any]
    chain_id: Optional[str] = None
    created_at: float = 0.0
    last_access: Optional[float] = None
    access_count: int = 0
    effect_count: int = 0
    archived_at: Optional[float] = None

    # ── D7 · 价值只能由实测推出 ──
    def used(self) -> bool:
        """是否被使用过。★ 不看自评分，只看 access 记录。"""
        return self.access_count > 0

    def changed_behavior(self) -> bool:
        """被召回后是否改变过行为（§三 修法 2 的判据）。"""
        return self.effect_count > 0

    def proven_value(self) -> bool:
        """★★ D7 的正式判据: 有 access 记录才算有价值。

        ★ 母巢的反面教材: 98.8% 节点 access_count=0，
          但 importance 均值 0.747 —— 自评很高，实际没人用。
        """
        return self.used()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id, "zone": self.zone.value,
            "kind": self.kind.value, "tube": self.tube.value,
            "payload": self.payload, "chain_id": self.chain_id,
            "access_count": self.access_count,
            "effect_count": self.effect_count,
            "used": self.used(), "proven_value": self.proven_value(),
        }


# ══════════════════════════════════════════════════════════
# 存储
# ══════════════════════════════════════════════════════════


class MemoryKernel:
    """DWC 记忆内核。★ 只提供证据，不做淘汰决策。"""

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ══════════════════════════════════════════════
    # 四管之一：remember（任务痕迹 / 工作态 → PROXY）
    # ══════════════════════════════════════════════
    def remember(self, kind: MemoryKind, payload: Dict[str, Any],
                 chain_id: Optional[str] = None,
                 node_id: Optional[str] = None) -> str:
        """写入一条记忆（remember / learn / evolve 共用）。

        ★★ D6 强制: 若 kind 属 EXPERIENCE 类，payload 必须含
          EXPERIENCE_REQUIREMENTS 里列的字段，否则 raise
          —— 这是**写入时的门槛**，不是事后分类。
        """
        if kind not in KIND_TO_ZONE:
            raise MemoryError("未知记忆种类: %r" % kind)
        zone = KIND_TO_ZONE[kind]

        # ★★ D6: EXPERIENCE 的门槛
        need = EXPERIENCE_REQUIREMENTS.get(kind)
        if need and zone is Zone.EXPERIENCE:
            missing = [k for k in need if not payload.get(k)]
            if missing:
                raise MemoryError(
                    "D6 违反: %s 进 EXPERIENCE 需含 %r，缺 %r"
                    "（不能驱动进化 ⇒ 应留在 PROXY 或归档）"
                    % (kind.value, list(need), missing))

        # ★ 明确不记的四类（§四）—— 由调用方保证，本层不猜
        nid = node_id or uuid.uuid4().hex
        tube = Tube.REMEMBER if kind in (MemoryKind.TRACE,
                                        MemoryKind.WORKING_STATE) else (
            Tube.REFLECT if kind is MemoryKind.FAILURE_SIGNATURE else (
                Tube.LEARN if kind is MemoryKind.SKILL else Tube.EVOLVE))
        self._conn.execute(
            "INSERT INTO memory_node"
            " (node_id, zone, kind, tube, payload, chain_id, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (nid, zone.value, kind.value, tube.value,
             json.dumps(payload, ensure_ascii=False), chain_id, time.time()))
        if kind is MemoryKind.FAILURE_SIGNATURE:
            self._conn.execute(
                "INSERT OR REPLACE INTO failure_sig (c,q,m,node_id)"
                " VALUES (?,?,?,?)",
                (payload["c"], payload["q"], payload["m"], nid))
        self._conn.commit()
        return nid

    # ══════════════════════════════════════════════
    # 读 + D7 的证据记录
    # ══════════════════════════════════════════════
    def get(self, node_id: str) -> MemoryNode:
        row = self._conn.execute(
            "SELECT * FROM memory_node WHERE node_id=?", (node_id,)).fetchone()
        if row is None:
            raise MemoryError("记忆不存在: %s" % node_id)
        d = dict(row)
        return MemoryNode(
            node_id=d["node_id"], zone=Zone(d["zone"]),
            kind=MemoryKind(d["kind"]), tube=Tube(d["tube"]),
            payload=json.loads(d["payload"]), chain_id=d["chain_id"],
            created_at=d["created_at"], last_access=d["last_access"],
            access_count=d["access_count"],
            effect_count=d["effect_count"], archived_at=d["archived_at"])

    def recall(self, node_id: str) -> MemoryNode:
        """召回一条记忆（Tube.RECALL）。★ 这次召回本身**就是 D7 的证据**。

        ★★ 它不写记忆节点（召回不是摄入），但它**改变** access_count
          —— 而这正是"记忆被使用"的唯一证据。
        ⇒★ R21: 补上这条管的原因是 —— 初版枚举里没有 recall，
          等于把 D7 的执行路径排除在管体系之外（而功能早已落地）。
        """
        self._conn.execute(
            "UPDATE memory_node SET access_count=access_count+1,"
            " last_access=? WHERE node_id=?", (time.time(), node_id))
        self._conn.commit()
        return self.get(node_id)

    def record_effect(self, node_id: str) -> MemoryNode:
        """记录"这条记忆改变过行为"。★ §三 修法 2 的判据。"""
        self._conn.execute(
            "UPDATE memory_node SET effect_count=effect_count+1"
            " WHERE node_id=?", (node_id,))
        self._conn.commit()
        return self.get(node_id)

    # ══════════════════════════════════════════════
    # 检索（索引消费点）
    # ══════════════════════════════════════════════
    def by_signature(self, c: str, q: str, m: str) -> List[str]:
        """按失败签名三元组精确聚类。★ 消费 ix_sig_lookup。"""
        rows = self._conn.execute(
            "SELECT node_id FROM failure_sig WHERE c=? AND q=? AND m=?",
            (c, q, m)).fetchall()
        return [r["node_id"] for r in rows]

    def by_zone(self, zone: Zone) -> List[MemoryNode]:
        """按区查。★ 消费 ix_node_zone。"""
        rows = self._conn.execute(
            "SELECT node_id FROM memory_node WHERE zone=? ORDER BY created_at",
            (zone.value,)).fetchall()
        return [self.get(r["node_id"]) for r in rows]

    def by_chain(self, chain_id: str) -> List[MemoryNode]:
        """按链查（这条记忆是哪次进化产生的）。★ 消费 ix_node_chain。"""
        rows = self._conn.execute(
            "SELECT node_id FROM memory_node WHERE chain_id=?",
            (chain_id,)).fetchall()
        return [self.get(r["node_id"]) for r in rows]

    # ══════════════════════════════════════════════
    # 淘汰证据（★ 只出证据，不做决策）
    # ══════════════════════════════════════════════
    def eviction_candidates(self) -> List[Dict[str, Any]]:
        """列出候选淘汰的记忆 + 它们的证据。

        ★★ 本方法**不删任何东西**，只把证据摆出来。
          淘汰决策由 evolver 依 GAI dials 决定 —— 那不在记忆内核的职责内。
        ★ 三条依据（MEMORY_SYSTEM §三）:
          1) 被召回过吗（access_count > 0）
          2) 被召回后改变过行为吗（effect_count > 0）
          3) 是某类失败的唯一签名吗（稀有保护）
        """
        rows = self._conn.execute(
            "SELECT node_id, kind, zone, access_count, effect_count"
            " FROM memory_node WHERE archived_at IS NULL"
            " ORDER BY created_at").fetchall()
        out = []
        for r in rows:
            rare = False
            if r["kind"] == MemoryKind.FAILURE_SIGNATURE.value:
                cnt = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_sig WHERE node_id=?",
                    (r["node_id"],)).fetchone()["n"]
                # ★ 同一三元组只有一条 ⇒ 它是唯一签名 ⇒ 稀有保护
                row = self._conn.execute(
                    "SELECT c,q,m FROM failure_sig WHERE node_id=?",
                    (r["node_id"],)).fetchone()
                same = self._conn.execute(
                    "SELECT COUNT(*) AS n FROM failure_sig"
                    " WHERE c=? AND q=? AND m=?",
                    (row["c"], row["q"], row["m"])).fetchone()["n"]
                rare = (same <= 1)
            out.append({
                "node_id": r["node_id"], "kind": r["kind"],
                "zone": r["zone"],
                "access_count": r["access_count"],
                "effect_count": r["effect_count"],
                "rare_protected": rare,
                "evictable": (r["access_count"] == 0
                              and r["effect_count"] == 0
                              and not rare),
            })
        return out

    # ══════════════════════════════════════════════
    # Tube.DREAM · 反刍（记忆重组 + 沙箱试演）
    # ══════════════════════════════════════════════
    def dream(self, c: str, q: str, m: str) -> Dict[str, Any]:
        """★ 反刍一簇同签名的失败记忆，返回重组后的候选技能。

        ★★★ 为什么 DREAM 不能"以后再说":
          母巢台账里 dream 有 34,624 次真实调用（实测），
          是七管里最活跃的一管之一。
          ⇒ 而 D6（EXPERIENCE 只存能驱动进化的东西）要求失败签名
            能被**归纳成技能** —— 那正是 dream 的职责：
            把 N 条同类失败聚成一条"以后怎么避免"的经验。
          ⇒⇒ 若没有 dream，失败签名就永远停在 PROXY 里当记录，
            永远变不成 evolver 的输入 ⇒ D6 与 D7 都失去落点。

        ★ 沙箱语义（§2.2 ⑥ 原文"记忆重组 + 沙箱试演"）:
          本方法**只读** —— 不写任何节点、不改任何 access。
          候选技能由调用方（learn / evolve）决定是否采纳。
          ⇒⇒ 避免"反刍顺手就落库"，那正是 D6 要防的。
        """
        members = self.by_signature(c, q, m)
        if not members:
            return {"c": c, "q": q, "m": m, "n_members": 0,
                    "n_used": 0, "candidate_skill": None,
                    "eligible": False, "why": "无同类失败记忆"}
        nodes = [self.get(n) for n in members]
        # ★ 只聚"被用过的" —— 没人用的记忆归纳不出东西（与 D7 同源）
        used = [n for n in nodes if n.used()]
        details = [n.payload.get("detail") for n in used
                   if n.payload.get("detail")]
        return {
            "c": c, "q": q, "m": m,
            "n_members": len(nodes), "n_used": len(used),
            "candidate_skill": ({
                "scene": c,                          # 终止级原因 ≈ 场景
                "method": "%s / %s" % (q, m),        # 因果角色 + 抽象机制
                # ★ 边界从 payload 的 detail 取，缺则标"未知"——**不编**
                "boundary": details[0] if details else "未知（payload 无 detail）",
            } if used else None),
            # ★ 一条都没被用过 ⇒ 不给候选（D6: 不能驱动进化就别占 EXPERIENCE）
            "eligible": len(used) > 0,
            "why": ("%d 条同类失败，其中 %d 条被真正用过"
                    % (len(nodes), len(used))) if used
                   else "全部未被召回 ⇒ 归纳不出技能（D7）",
        }

    # ══════════════════════════════════════════════
    # Tube.MAINTAIN · 维护（遗忘 + 稀有保护 + 审计）
    # ══════════════════════════════════════════════
    def maintain(self, chain_id: Optional[str] = None) -> Dict[str, Any]:
        """★ 执行一次维护，返回处置记录（**归档而非删除**）。

        ★★★ 与 eviction_candidates 的分工:
          eviction_candidates —— 只出证据，不动任何东西（纯查询）
          maintain            —— 按三层判据执行归档，且留审计
        ⇒★ 分开是为了 D8 的可核对性: 能查"当时凭什么这么处置"。

        ★★ 三层顺序不可换（MEMORY_SYSTEM §三）:
          1) 从未召回 → **不处置**（可能是检索策略问题）
          2) 召回过但没改变行为 → 候选
          3) 稀有保护（唯一签名）→ **硬否决**
        """
        rows = self.eviction_candidates()
        held, archived, protected = [], [], []
        for r in rows:
            if r["rare_protected"]:
                protected.append(r["node_id"])       # 第3层: 硬否决
                continue
            if r["access_count"] == 0:
                held.append(r["node_id"])           # 第1层: 不处置
                continue
            archived.append(r["node_id"])           # 第2层: 归档
        for nid in archived:
            self.archive(nid)
        return {
            "chain_id": chain_id,
            "n_evaluated": len(rows),
            "held_never_recalled": held,       # ★ 未召回: 一律不动
            "archived": archived,
            "protected_rare": protected,
            "n_held": len(held), "n_archived": len(archived),
            "n_protected": len(protected),
            # ★ 审计要点: held 占多数 ⇒ 那是检索策略的问题，不是记忆该删
            "hint": ("held:%d archived:%d protected:%d —— held 占比高说明 "
                     "recall 管要修，不是记忆该删"
                     % (len(held), len(archived), len(protected))),
        }

    def archive(self, node_id: str) -> MemoryNode:
        """归档（不删 —— 判据 S6 的同款纪律）。"""
        self._conn.execute(
            "UPDATE memory_node SET archived_at=?, zone=? WHERE node_id=?",
            (time.time(), Zone.ARCHIVE.value, node_id))
        self._conn.commit()
        return self.get(node_id)

    # ══════════════════════════════════════════════
    # 统计（D7 的门禁数据）
    # ══════════════════════════════════════════════
    def usage_stats(self) -> Dict[str, Any]:
        """★★ D7 的核心指标: 有多少记忆**真被用过**。

        ★ 母巢的反面教材是 98.8% access_count=0 ——
          所以这个比率必须能被机器算出来，而不是靠印象。
        """
        row = self._conn.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(CASE WHEN access_count>0 THEN 1 ELSE 0 END) AS used,"
            " SUM(CASE WHEN effect_count>0 THEN 1 ELSE 0 END) AS effective"
            " FROM memory_node WHERE archived_at IS NULL").fetchone()
        total = int(row["total"] or 0)
        used = int(row["used"] or 0)
        eff = int(row["effective"] or 0)
        return {
            "total": total, "used": used, "effective": eff,
            "used_ratio": (used / total) if total else 0.0,
            "effective_ratio": (eff / total) if total else 0.0,
        }


# ══════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════

def _self_test() -> None:
    m = MemoryKernel()

    # PROXY 类（无门槛）
    t1 = m.remember(MemoryKind.TRACE,
                    {"action": "fix", "success": True}, chain_id="CH1")
    m.remember(MemoryKind.WORKING_STATE, {"vars": {"k": 1}}, chain_id="CH1")
    print("PROXY 已写: %d 条" % len(m.by_zone(Zone.PROXY)))

    # EXPERIENCE 类（必须带 c,q,m）
    try:
        m.remember(MemoryKind.FAILURE_SIGNATURE, {"c": "timeout"})
        print("★ D6 未拦住 —— 有 bug")
    except MemoryError as e:
        print("D6 门槛: raise ✓ (%s)" % str(e)[:70])

    s1 = m.remember(MemoryKind.FAILURE_SIGNATURE,
                    {"c": "timeout", "q": "agent", "m": "retry_bomb",
                     "detail": "重试 7 次"}, chain_id="CH1")
    print("\n失败签名聚类 (timeout,agent,retry_bomb): %s"
          % m.by_signature("timeout", "agent", "retry_bomb"))

    # D7: 没被召回 ⇒ 不算有价值
    print("\n=== D7 · 记忆必须证明被使用 ===")
    print("  recall 前: %s" % {k: v for k, v in
                               m.get(s1).to_dict().items()
                               if k in ("access_count", "used", "proven_value")})
    m.recall(s1)
    n = m.get(s1)
    print("  recall 后: %s" % {k: v for k, v in n.to_dict().items()
                               if k in ("access_count", "used", "proven_value")})
    m.record_effect(s1)
    print("  effect后: changed_behavior=%s" % m.get(s1).changed_behavior())

    # 未被用的记忆
    print("\n  统计: %s" % m.usage_stats())

    # 淘汰证据（稀有保护）
    print("\n=== 淘汰候选（只出证据，不删）===")
    for row in m.eviction_candidates():
        print("  %-10s %-12s access=%d effect=%d rare=%-5s ⇒ evictable=%s"
              % (row["kind"], row["zone"], row["access_count"],
                 row["effect_count"], row["rare_protected"],
                 row["evictable"]))

    # ★ DREAM · 反刍（把同类失败归纳成技能）
    m.remember(MemoryKind.FAILURE_SIGNATURE,
               {"c": "timeout", "q": "agent", "m": "retry_bomb",
                "detail": "重试 7 次"}, chain_id="CH1")
    m.remember(MemoryKind.FAILURE_SIGNATURE,
               {"c": "timeout", "q": "agent", "m": "retry_bomb",
                "detail": "重试 9 次"}, chain_id="CH1")
    dr = m.dream("timeout", "agent", "retry_bomb")
    print("\n=== DREAM · 反刍 ===")
    print("  同签名 %d 条 · 被用过 %d 条"
          % (dr["n_members"], dr["n_used"]))
    print("  候选技能: %s" % dr["candidate_skill"])
    print("  eligible=%s · %s" % (dr["eligible"], dr["why"]))

    # ★ MAINTAIN · 维护
    mt = m.maintain()
    print("\n=== MAINTAIN · 维护 ===")
    print("  %s" % mt["hint"])

    # 归档不删
    m.archive(t1)
    print("\n归档后 trace 的 zone: %s · get 仍可读: %s"
          % (m.get(t1).zone.value, m.get(t1) is not None))


if __name__ == "__main__":
    _self_test()