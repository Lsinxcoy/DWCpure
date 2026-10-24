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

import json
import math
import re
import sqlite3
import time
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

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
    # ★ R104 · 技能卡双字段（PRACTICE/2608.30760 明文: v=(pattern, usage_spec)
    #   的 spec 含失效条件与恢复策略 — 报告 2 行「没有这两个字段」的落点）:
    #   invalid_conditions = 什么情况下这技能不适用
    #   recovery_strategies = 失效时怎么办（不带恢复策略的技能=只知道成功路径）
    MemoryKind.SKILL: ("scene", "method", "boundary",
                       "invalid_conditions", "recovery_strategies"),
    MemoryKind.PROPOSAL: ("consumer_declared",),
}

#: ★ R104 · 写入三步的第三步（PAHF salience→摘要→τ 近重复合并）——
#:   DWC 落点 = **去重语义**（同经验域同 kind 近重复 ⇒ 不新增, 防膨胀;
#:   PAHF 明文机制）。★ 内容级摘要重写无明文算法 ⇒ 列留位（不发明）。
#:   ★ 数值: PAHF 有 τ 机制、值未核 ⇒ 初值 0.90 待校准（β 同款纪律）。
MERGE_TAU = 0.90

# ══════════════════════════════════════════════════════════
# ★ R审计-P2 · P1-6 · Weibull 保留度（只做排序权重，**不做淘汰**）
# ══════════════════════════════════════════════════════════
#: CJK 检测（recall 路1 分流: 含中文 ⇒ LIKE；纯 ASCII ⇒ FTS5 trigram）
_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
#: 按记忆种类的 Weibull 参数 (λ 天, k 形状) — 借鉴 Prometheus-X/MnemosyneV3
#:   working 快忘 / episodic 中 / semantic 慢 / procedural 几乎不忘
#: ★ 为什么只做权重不做淘汰: MEMORY_SYSTEM §三 修法3 明确「淘汰规则必须基于
#:   价值而非年龄」—— 母巢的 weibull_expired 空转（淘汰对象 98.8% access=0）
#:   正是年龄淘汰的反面教材。这里只让"旧记忆排序靠后"，不删任何东西。
WEIBULL_BY_KIND: dict[MemoryKind, tuple[float, float]] = {
    MemoryKind.TRACE: (7.0, 1.5),            # working: 痕迹快忘
    MemoryKind.WORKING_STATE: (7.0, 1.5),    # working
    MemoryKind.FAILURE_SIGNATURE: (30.0, 1.2),   # episodic: 失败经验中速
    MemoryKind.SKILL: (365.0, 0.5),          # procedural: 技能几乎不忘
    MemoryKind.PROPOSAL: (180.0, 0.8),       # semantic: 提案慢忘
}


def retention_of(node: "MemoryNode", now: float | None = None) -> float:
    """Weibull 保留度 P = exp(-(t/λ)^k)，t = 距创建的**天数**。

    ★ 返回值 ∈ (0,1]: 1.0=刚写, 0=极旧。只用于 recall 排序权重。
    ★ 未知 kind ⇒ 保守取 semantic 参数（不发明新档）。
    """
    lam, k = WEIBULL_BY_KIND.get(node.kind, (180.0, 0.8))
    if lam <= 0:
        return 1.0
    age_days = max(0.0, ((now if now is not None else time.time())
                         - (node.created_at or 0.0)) / 86400.0)
    try:
        return math.exp(-((age_days / lam) ** k))
    except (OverflowError, ValueError):
        return 0.0


#: ★ R审计-P2 · P2-8 · 4-tier 语义名（working/episodic/semantic/procedural）
#:   ★ 不存列: tier 完全由 kind 决定，存列 = 与 WEIBULL_BY_KIND 冗余
#:     （判据 S4: 冗余字段迟早飘 —— 用纯函数，单一真值源）
_TIER_OF: dict[MemoryKind, str] = {
    MemoryKind.TRACE: "working",
    MemoryKind.WORKING_STATE: "working",
    MemoryKind.FAILURE_SIGNATURE: "episodic",
    MemoryKind.PROPOSAL: "semantic",
    MemoryKind.SKILL: "procedural",
}


def tier_of(kind: MemoryKind) -> str:
    """记忆种类的 4-tier 语义档位（与 WEIBULL_BY_KIND 同源）。"""
    return _TIER_OF.get(kind, "semantic")

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
    archived_at  REAL,
    -- ★ R审计-P2 · P2-7 · learn 管回写的"巩固权重"
    --   ★ 不是自评分: 由 learn() 从实测 access/effect 推出（D7 同源）
    importance   REAL NOT NULL DEFAULT 0.5
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

-- ★★★ R审计-P2 · P1-5 · FTS5 全文索引（trigram 分词 — 中文子串友好）
--   现场: recall 路1 是**全表 in 子串扫**（O(n×len)），209 条时无感，
--   上千条后每步 term 都扫会拖垮。FTS5 是 SQLite 原生（零依赖）。
--   ★ external content 模式: 索引不复制正文，靠 trigger 同步（省一半空间）
--   ★ trigram: 中文按三字窗口切 ⇒ "函数中"/"off-by-one" 都能子串命中
--     （unicode61 按词切，中文会退化成单字，不适合）
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    payload,
    content='memory_node',
    content_rowid='rowid',
    tokenize='trigram'
);

-- 同步 trigger（INSERT / DELETE / UPDATE 三路 — 漏一路索引就飘）
CREATE TRIGGER IF NOT EXISTS memory_fts_ai AFTER INSERT ON memory_node BEGIN
    INSERT INTO memory_fts(rowid, payload) VALUES (new.rowid, new.payload);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_ad AFTER DELETE ON memory_node BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, payload)
    VALUES ('delete', old.rowid, old.payload);
END;

CREATE TRIGGER IF NOT EXISTS memory_fts_au AFTER UPDATE ON memory_node BEGIN
    INSERT INTO memory_fts(memory_fts, rowid, payload)
    VALUES ('delete', old.rowid, old.payload);
    INSERT INTO memory_fts(rowid, payload) VALUES (new.rowid, new.payload);
END;
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
    payload: dict[str, Any]
    chain_id: str | None = None
    created_at: float = 0.0
    last_access: float | None = None
    access_count: int = 0
    effect_count: int = 0
    archived_at: float | None = None
    #: ★ R审计-P2 · P2-7 · learn 管回写的巩固权重（0.5=未学）
    #:   ★ 不是自评分 — 由 learn() 从实测 access/effect 推出
    importance: float = 0.5

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

    def to_dict(self) -> dict[str, Any]:
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
        # ★ R审计-P2 · P2-7 · 老库迁移: memory_node 补 importance 列
        #   （CREATE TABLE IF NOT EXISTS 不会改已有表 ⇒ 显式 ALTER）
        _cols = [r[1] for r in self._conn.execute(
            "PRAGMA table_info(memory_node)").fetchall()]
        if "importance" not in _cols:
            self._conn.execute(
                "ALTER TABLE memory_node ADD COLUMN importance REAL"
                " NOT NULL DEFAULT 0.5")
        # ★ R审计-P2 · P1-5 · FTS5 external-content 索引补齐:
        #   已有行（老库）不会自动进 FTS ⇒ 启动时 rebuild 一次（幂等）。
        #   ★ 209 条 <10ms；万级库首次会慢一次，之后靠 trigger 增量同步。
        try:
            self._conn.execute(
                "INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
        except sqlite3.OperationalError as exc:
            # ★ G7: 不许静默 —— FTS 不可用必须留痕（检索会退回全表扫）
            import sys as _sys
            _sys.stderr.write("memory_fts rebuild 失败（检索将退化）: %s\n"
                              % exc)
        self._conn.commit()
        self._retrieved: list[str] = []   # ★ R258 检索留痕（修订候选集）

    def close(self) -> None:
        self._conn.close()

    # ══════════════════════════════════════════════
    # 四管之一：remember（任务痕迹 / 工作态 → PROXY）
    # ══════════════════════════════════════════════
    def remember(self, kind: MemoryKind, payload: dict[str, Any],
                 chain_id: str | None = None,
                 node_id: str | None = None) -> str:
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

        # ★ R104 · 近重复合并（PAHF 第三步; 仅**文档性经验**=SKILL）:
        #   FAILURE_SIGNATURE 是事件流（同签名重复=真实独立失败, 聚簇要 N 条）——
        #   合并它会破坏聚簇（test_signature_clustering 抓到的误伤）; TRACE 不参与。
        if kind is MemoryKind.SKILL:
            dup = self._near_duplicate(kind, payload)
            if dup is not None:
                return dup              # 去重: 返回现节点（调用方 str 语义不变）

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
            effect_count=d["effect_count"], archived_at=d["archived_at"],
            importance=float(d.get("importance") or 0.5))

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

    def record_effect(self, node_id: str, source: str = "") -> MemoryNode:
        """记录"这条记忆改变过行为"。★ §三 修法 2 的判据。

        ★★★ R审计-P2 · 边界3 · source 参数（诚实标注来源）:
          · "" / "explicit" — 调用方明确知道"这条记忆导致了行为改变"（最强）
          · "inferred_by_step_success" — **推断**: 本 term 召回了这条历史记忆
            且 term 判分通过 ⇒ 推断它参与了成功（不是因果证明）。
          ★ 两者都计入 effect_count（maintain 第 2 层需要它），但 source
            落进 node payload 的 `_effect_sources`，可审计、可撤回。
        """
        self._conn.execute(
            "UPDATE memory_node SET effect_count=effect_count+1"
            " WHERE node_id=?", (node_id,))
        if source:
            # ★ 来源留痕（不改变 effect 语义，只让"推断的"可区分）
            try:
                _row = self._conn.execute(
                    "SELECT payload FROM memory_node WHERE node_id=?",
                    (node_id,)).fetchone()
                if _row is not None:
                    _pl = json.loads(_row["payload"] or "{}")
                    _srcs = list(_pl.get("_effect_sources") or [])
                    _srcs.append(source)
                    _pl["_effect_sources"] = _srcs[-5:]   # 只留最近 5 条
                    self._conn.execute(
                        "UPDATE memory_node SET payload=? WHERE node_id=?",
                        (json.dumps(_pl, ensure_ascii=False), node_id))
            except (ValueError, sqlite3.Error) as exc:
                # ★ G7: 来源留痕失败不静默（effect 本身已记，不丢账）
                import sys as _sys
                _sys.stderr.write("record_effect 来源留痕失败: %s\n" % exc)
        self._conn.commit()
        return self.get(node_id)

    # ══════════════════════════════════════════════
    # 检索（索引消费点）
    # ══════════════════════════════════════════════
    def by_signature(self, c: str, q: str, m: str) -> list[str]:
        """按失败签名三元组精确聚类。★ 消费 ix_sig_lookup。"""
        rows = self._conn.execute(
            "SELECT node_id FROM failure_sig WHERE c=? AND q=? AND m=?",
            (c, q, m)).fetchall()
        return [r["node_id"] for r in rows]

    def by_zone(self, zone: Zone) -> list[MemoryNode]:
        """按区查。★ 消费 ix_node_zone。"""
        rows = self._conn.execute(
            "SELECT node_id FROM memory_node WHERE zone=? ORDER BY created_at",
            (zone.value,)).fetchall()
        return [self.get(r["node_id"]) for r in rows]

    def by_chain(self, chain_id: str) -> list[MemoryNode]:
        """按链查（这条记忆是哪次进化产生的）。★ 消费 ix_node_chain。"""
        rows = self._conn.execute(
            "SELECT node_id FROM memory_node WHERE chain_id=?",
            (chain_id,)).fetchall()
        return [self.get(r["node_id"]) for r in rows]

    # ══════════════════════════════════════════════
    # 淘汰证据（★ 只出证据，不做决策）
    # ══════════════════════════════════════════════
    def eviction_candidates(self) -> list[dict[str, Any]]:
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
                _cnt = self._conn.execute(
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
    # Tube.RECALL · 取回（四路融合 + RRF + 重力排序）
    # ══════════════════════════════════════════════
    def recall_search(self, scene: str, terms: list[str] | None = None,
                      k: int = 5) -> list[MemoryNode]:
        """★ 按**场景词**检索，返回节点（未记 access）。

        ★★★ R22 这个方法是为了解一个实测出来的死结:
          dream 要求"至少一条被 used()"，而 used() 要 access_count>0，
          access_count 只由 recall() 增加
          ⇒ 但 recall() 需要先知道**查什么**，而旧代码只有
            by_signature(c,q,m) —— 它要求三元组**已知**
          ⇒⇒ ★★★ 而三元组只有失败现场才知道（reflect 管从失败生成它）
          ⇒⇒ ⇒★ 于是"没失败过 ⇒ 查不到 ⇒ 永远没 access ⇒
                 永远没技能"的闭环成立了
          ⇒⇒ ★ 破法: 检索的入口不是三元组，而是**场景词**——
            失败发生前就有场景（要修什么 bug），三元组是事后归因的产物。

        ★ 四路（依 MEMORY_SYSTEM §2.2②「多路融合」与母巢四路RRF）:
          路1 · 场景词匹配（scene 字段 / payload 里的场景词）
          路2 · 失败签名同 q/m（同一机制、同一因果角色的失败）
          路3 · 链匹配（同一次进化产生的记忆）
          路4 · 双时间轴（新建优先，其次高 access）
        ⇒ 融合用 **RRF**（Reciprocal Rank Fusion）—— 不用加权求和，
          免得各路量纲不可比（这正是母巢「多路融合」的做法）
        """
        terms = [t for t in (terms or []) if t]
        pool: dict[str, MemoryNode] = {}
        for n in self._all_nodes():
            pool[n.node_id] = n

        # ── 路1 · 场景词（FTS5 trigram 全文 — 替代全表子串扫）──
        # ★★★ R审计-P2 · P1-5: 原实现是 O(n×len) 全表 `in` 扫（209 条无感，
        #   上千条后每步 term 都扫会拖垮）。FTS5 是 SQLite 原生索引。
        #   trigram 分词 ⇒ 中文子串（"函数中"）与英文（"off-by-one"）都命中。
        #   ★ 查询串 <3 字符 trigram 不索引 ⇒ 自动跳过（不报错）。
        scene_norm = (scene or "").strip()
        route1: list[str] = []
        _qs = ([scene_norm] if scene_norm else []) + list(terms)
        # ★ 分流（语义与旧实现一致，只是把 ASCII 部分交给索引）:
        #   · 纯 ASCII 且 ≥3 字符 ⇒ FTS5 trigram（sum_first_n / off-by-one 快查）
        #   · 含 CJK 或 <3 字符 ⇒ SQL LIKE（中文无分词，trigram 短语要求
        #     连续子串 ⇒ 中文概括词与原文不连续，只能子串匹配）
        #   ★ 两者都是"连续子串"语义 —— 与旧 `scene in blob` 等价，不改变召回集合
        _phr = []
        _short = []
        for _q in _qs:
            _s = str(_q)
            if not _s:
                continue
            if len(_s) >= 3 and not _CJK.search(_s):
                _phr.append('"%s"' % _s.replace('"', '""'))
            else:
                _short.append(_s)
        if _phr:
            try:
                rows = self._conn.execute(
                    "SELECT m.node_id FROM memory_fts f"
                    " JOIN memory_node m ON m.rowid = f.rowid"
                    " WHERE memory_fts MATCH ? AND m.archived_at IS NULL"
                    " ORDER BY rank LIMIT 200",
                    (" OR ".join(_phr),)).fetchall()
                route1 = [r["node_id"] for r in rows]
            except sqlite3.OperationalError as exc:
                # ★ G7: FTS 查询失败不许静默（会退化成无路1）
                import sys as _sys
                _sys.stderr.write("FTS 路1 查询失败（退化为空）: %s\n" % exc)
                route1 = []
        for _q in _short:
            _rows = self._conn.execute(
                "SELECT node_id FROM memory_node"
                " WHERE payload LIKE ? AND archived_at IS NULL LIMIT 200",
                ("%" + _q + "%",)).fetchall()
            for _r in _rows:
                if _r["node_id"] not in route1:
                    route1.append(_r["node_id"])

        # ── 路2 · 同机制/同因果角色的失败签名 ──
        route2 = [n.node_id for n in pool.values()
                  if n.kind is MemoryKind.FAILURE_SIGNATURE
                  and (n.payload.get("m") in terms
                       or n.payload.get("q") in terms)]

        # ── 路3 · 同链 ──
        chain_ids = set()
        for n in pool.values():
            if scene_norm and scene_norm in json.dumps(
                    n.payload, ensure_ascii=False):
                if n.chain_id:
                    chain_ids.add(n.chain_id)
        route3 = [n.node_id for n in pool.values() if n.chain_id in chain_ids]

        # ── 路4 · 双时间轴 ──
        # ★★★ R22 修正: 路4 原实现是"取最新的 N 条无条件返回"，
        #   于是**查不到也会返回东西**（自检实测抓到）
        #   ⇒★ 那会让 recall 变成"总能返回点东西"的空转检索
        #     —— 而母巢的病正是"淘汰/检索反复触发却无对象"
        #   ⇒★ 修法: 路4 只在**已有匹配**时参与重排（它是时间轴排序，
        #     不是召回源）⇒ 若路1~3 全空，则返回空
        matched = set(route1) | set(route2) | set(route3)
        route4 = sorted(
            (n for n in pool.values() if n.node_id in matched),
            key=lambda x: (x.created_at, x.access_count),
            reverse=True)
        route4_ids = [n.node_id for n in route4]

        # ── RRF 融合 ──
        # score = Σ 1/(60 + rank) —— 60 是 RRF 的标准常数
        score: dict[str, float] = {}
        for route in (route1, route2, route3, route4_ids):
            for rank, nid in enumerate(route):
                score[nid] = score.get(nid, 0.0) + 1.0 / (60 + rank + 1)

        if not score:
            return []
        # ★ 重力排序 = RRF 分 × Weibull 保留度 × importance 权重，access_count 次键
        #   ★ P1-6: retention ∈ (0,1] 做乘性权重（0.5~1.0 区间），
        #     让"旧且未被使用"的记忆排后面 —— 只影响排序，不删任何东西
        #   ★ P2-7: importance（learn 回写）同样乘性（0.75~1.25 温和区间）
        _now = time.time()
        ordered = sorted(
            score.items(),
            key=lambda kv: (kv[1] * (0.5 + 0.5 * retention_of(
                pool[kv[0]], _now)) * (0.75 + 0.5 * float(
                    pool[kv[0]].importance)), pool[kv[0]].access_count),
            reverse=True)
        # ★ P2-8 · MMR 多样性重排（同任务多条 trace 不再占满 top-k）
        _top = self._mmr_rerank(ordered, pool, k)
        self._note_retrieved([nid for nid, _ in _top])
        return [pool[nid] for nid, _ in _top]

    # ══════════════════════════════════════════════
    # ★ R审计-P2 · P2-8 · MMR 多样性重排（无 embedding 的诚实近似）
    # ══════════════════════════════════════════════
    @staticmethod
    def _token_set(node: MemoryNode) -> set[str]:
        """payload 文本的 2-gram 字符集（中文友好；替代 embedding）。"""
        txt = json.dumps(node.payload, ensure_ascii=False)
        return {txt[i:i + 2] for i in range(max(0, len(txt) - 1))}

    def _mmr_rerank(self, ordered: list[tuple[str, float]],
                    pool: dict[str, MemoryNode], k: int,
                    lambda_param: float = 0.7) -> list[tuple[str, float]]:
        """★ MMR（Maximal Marginal Relevance）多样性重排。

        ★★★ 为什么需要:
          RRF 只按相关性排 ⇒ 同任务的多条 trace（step_0 反复出现）会占满
          top-k ⇒ 召回变成"同一件事说三遍"（实测 trace 80 条里 step_0 最多）。
        ★ 相似度 = 2-gram Jaccard（无 embedding — 诚实近似，不引模型依赖）
        ★ λ=0.7: 相关性为主、多样性为辅（MMR 论文标准取值，标为初值）
        """
        if len(ordered) <= 1 or k <= 0:
            return ordered
        _mx = max((s for _, s in ordered), default=0.0) or 1.0
        norm = {nid: s / _mx for nid, s in ordered}
        cand = [nid for nid, _ in ordered]
        toks = {nid: self._token_set(pool[nid]) for nid in cand}
        picked: list[str] = []
        while cand and len(picked) < k:
            best, best_v = None, -1e9
            for nid in cand:
                sim = 0.0
                for p in picked:
                    a, b = toks[nid], toks[p]
                    u = len(a | b)
                    if u:
                        sim = max(sim, len(a & b) / u)
                v = lambda_param * norm[nid] - (1 - lambda_param) * sim
                if v > best_v:
                    best, best_v = nid, v
            picked.append(best)
            cand.remove(best)
        smap = dict(ordered)
        return [(nid, smap[nid]) for nid in picked]

    def recall_many(self, scene: str, terms: list[str] | None = None,
                   k: int = 5) -> list[MemoryNode]:
        """★ 检索**并**记 access（Tube.RECALL 的完整语义）。

        ★★★ 判据 D7/MEMORY_SYSTEM §2.2②: 「取回后 access_count 必须 +1」
          ★★ recall_search **不记** access（它是纯查询，可被反复调用做检索实验）；
            recall_many 才记 —— 两者分开是为了让"检索"可被审阅而不污染证据。
        """
        hits = self.recall_search(scene, terms, k)
        out = []
        for n in hits:
            self._conn.execute(
                "UPDATE memory_node SET access_count=access_count+1,"
                " last_access=? WHERE node_id=?", (time.time(), n.node_id))
            out.append(n.node_id)
        self._conn.commit()
        return [self.get(i) for i in out]

    def _all_nodes(self) -> list[MemoryNode]:
        """全部未归档节点。★ 检索的候选池（内部用）。"""
        rows = self._conn.execute(
            "SELECT node_id FROM memory_node WHERE archived_at IS NULL"
        ).fetchall()
        return [self.get(r["node_id"]) for r in rows]

    def _near_duplicate(self, kind: MemoryKind,
                        payload: dict[str, Any]) -> str | None:
        """★ R104 · 同 kind 经验的近重复节点（ratio ≥ MERGE_TAU ⇒ 合并去重）。

        ★ 全表扫限经验域未归档行（小库量级 — 库大了要建索引, 现标边界）。
        ★ payload 归一后比（sort_keys ⇒ 键序无关）。
        """
        import difflib
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        rows = self._conn.execute(
            "SELECT node_id, payload FROM memory_node"
            " WHERE zone=? AND kind=? AND archived_at IS NULL",
            (Zone.EXPERIENCE.value, kind.value)).fetchall()
        for r in rows:
            other = json.dumps(json.loads(r["payload"]),
                               ensure_ascii=False, sort_keys=True)
            if difflib.SequenceMatcher(None, blob, other).ratio() >= MERGE_TAU:
                return r["node_id"]
        return None

    def contribution_report(self) -> dict[str, Any]:
        """★ R104 · 库治理观测层（Library Drift 四件套①的报表先行版）。

        ★ 只报**事实**: 访问数/效果数/最近访问 + 「访问过但零效果」标记
          （access>0 ∧ effect==0 是事实不是阈值 — 不发明退役判据）。
        ★ 退役触发/活跃封顶/meta-skill 引导 = **行为级变更, 留裁决**
          （Library Drift 自陈「退役过激比无引导更差」⇒ 行为须配对照, 不默认开）。
        """
        rows = self._conn.execute(
            "SELECT node_id, kind, zone, access_count, effect_count,"
            " last_access, archived_at FROM memory_node").fetchall()
        items, flagged = [], 0
        n_archived = 0
        for r in rows:
            arc = r["archived_at"] is not None
            n_archived += 1 if arc else 0
            hi = (not arc and int(r["access_count"]) > 0
                  and int(r["effect_count"]) == 0)
            if hi:
                flagged += 1
            items.append({"node_id": r["node_id"], "kind": r["kind"],
                          "zone": r["zone"],
                          "access": int(r["access_count"]),
                          "effect": int(r["effect_count"]),
                          "last_access": r["last_access"],
                          "archived": arc, "no_effect_flag": hi})
        return {"n_nodes": len(rows), "n_archived": n_archived,
                "n_accessed_no_effect": flagged,
                "items": items,
                "behavioral_changes": "left_for_verdict",
                "why_behavioral_left": (
                    "退役/封顶/meta-skill 是行为级 — Library Drift 自陈退役"
                    "过激更差 ⇒ 须配对照实验, 不默认开（SYNTHESIS T3 留位）")}

    def _signature_is_globally_unique(self, c: str, q: str, m: str) -> bool:
        """★ 该失败签名在**整个库**里是否只有这一处（R22.1）。

        ★★★ 为什么必须看全局而不是看簇内（自检抓到的真缺陷）:
          簇内唯一（len(nodes)==1）几乎恒真 —— 大多数簇只有一条
          ⇒ 豁免会普遍触发 ⇒ waiver 变成万能借口
          ⇒⇒ ⇒★★ 那比原来的饿死更坏: 原来至少"太严"，
            现在变成 D7 判据形同虚设。
          ⇒★ 正确判据: 同一个 m 在全库只出现一次 ⇒ 这知识别处找不到
            ⇒ 稀缺 ⇒ 放它出去（哪怕没人用过）
          ⇒ 而同一 m 在多处出现 ⇒ 不稀缺 ⇒ 该等它被真正用到
        ★ 与稀有保护互为镜像:
          稀有保护（淘汰侧）: 唯一签名 ⇒ 不淘汰
          本豁免（归纳侧）:   唯一签名 ⇒ 允许归纳
          ⇒ 两边看的是同一个量，方向相反
        """
        #★★★ R22.2 修正（自检第二次抓到）:
        #   初版数的是「同一 (c,q,m) 出现几次」—— 而它恒等于 1
        #   （那就是"这个簇"本身的定义）⇒ 判据恒真 ⇒ 豁免普遍触发
        #   ⇒⇒ ★★★ 真正该问的是: **抽象机制 m 在别处有没有第二份**
        #     因为技能是按 m 归纳的（method = "q / m"）
        #     ⇒ 若 m 在别的因果角色下也出现过 ⇒ 这不是稀缺知识
        n_m = self._conn.execute(
            "SELECT COUNT(*) AS n FROM failure_sig WHERE m=?", (m,)
        ).fetchone()["n"]
        # ★ 跨簇唯一 = 这个抽象机制在全库只出现这一次
        return int(n_m) == 1

    # ══════════════════════════════════════════════
    # Tube.DREAM · 反刍（记忆重组 + 沙箱试演）
    # ══════════════════════════════════════════════
    def dream(self, c: str, q: str, m: str) -> dict[str, Any]:
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
                    "eligible": False, "waiver": None,
                    "why": "无同类失败记忆"}
        nodes = [self.get(n) for n in members]
        #★★★ R22 修正: 原实现只聚 used() 的记忆，而那条路走不通 ——
        #   used() 要 access_count>0，access 只由 recall 增加，
        #   recall 要先知道查什么，而 by_signature 要求三元组已知
        #   ⇒⇒ "没失败过就查不到 → 查不到就永远没 access → 永远没技能"
        #   ⇒★ 现在改成**两级门槛**（详见方法 docstring 的设计说明）:
        #     一级: 被召回过（access>0）⇒ 常规路径
        #     二级: 稀有保护同款 —— **唯一签名豁免** access 门槛
        #   ⇒ 二级是"稀有保护的镜像"：淘汰时唯一签名受保护，
        #     归纳时唯一签名也不该被"没人用"卡住
        used = [n for n in nodes if n.used()]
        #★★★ R22.1 修正（自检抓到的真缺陷）:
        #   初版用 `len(nodes) == 1`（**簇内**唯一）作豁免条件
        #   ⇒ 但大多数簇都只有 1 条 ⇒ 豁免**普遍触发**
        #   ⇒⇒ ⇒★★ waiver 变成万能借口 —— D7 判据被我自己的代码废掉了
        #   ⇒★ 正确判据是「**跨簇唯一**」:
        #     这个 (c,q,m) 在整个库里只有这一处（m 唯一出现一次）⇒
        #     它承载的知识在别处找不到 ⇒ 稀缺 ⇒ 该让它出去
        #     而若同一 m 在多处出现 ⇒ 那不是稀缺，是常见模式 ⇒ 该等它被用
        #   ⇒ 这与稀有保护是同一个量（signature 的全局频次），互为镜像
        unique_waiver = False
        if not used and nodes:
            unique_waiver = self._signature_is_globally_unique(c, q, m)
        pool = used if used else ([nodes[0]] if unique_waiver else [])
        details = [n.payload.get("detail") for n in pool
                   if n.payload.get("detail")]
        return {
            "c": c, "q": q, "m": m,
            "n_members": len(nodes), "n_used": len(used),
            "candidate_skill": ({
                "scene": c,                          # 终止级原因 ≈ 场景
                "method": "%s / %s" % (q, m),        # 因果角色 + 抽象机制
                # ★ 边界从 payload 的 detail 取，缺则标"未知"——**不编**
                "boundary": details[0] if details else "未知（payload 无 detail）",
            } if pool else None),
            "eligible": bool(pool),
            # ★ 门槛来源必须可审计（否则"D7 例外"会变成万能借口）
            "waiver": "unique_signature" if unique_waiver else None,
            "why": self._dream_reason(len(nodes), len(used), unique_waiver),
        }

    @staticmethod
    def _dream_reason(n_members: int, n_used: int, waiver) -> str:
        """dream 的门槛说明。★ 单独一个函数，保证理由可测。"""
        if n_used:
            return "%d 条同类失败，其中 %d 条被真正用过" % (n_members, n_used)
        if waiver:
            return ("跨簇唯一签名 ⇒ 豁免 access 门槛（稀有保护的镜像）"
                    "：该知识在别处没有第二份，稀缺信息不该被『没人用』埋掉")
        return ("%d 条同类失败但无一被召回 ⇒ 归纳不出技能"
                "（先修 recall 检索管）" % n_members)

    # ══════════════════════════════════════════════
    # Tube.MAINTAIN · 维护（遗忘 + 稀有保护 + 审计）
    # ══════════════════════════════════════════════
    def maintain(self, chain_id: str | None = None) -> dict[str, Any]:
        """★ 执行一次维护，返回处置记录（**归档而非删除**）。

        ★★★ 与 eviction_candidates 的分工:
          eviction_candidates —— 只出证据，不动任何东西（纯查询）
          maintain            —— 按三层判据执行归档，且留审计
        ⇒★ 分开是为了 D8 的可核对性: 能查"当时凭什么这么处置"。

        ★★ 三层顺序不可换（MEMORY_SYSTEM §三）:
          1) 从未召回 → **不处置**（可能是检索策略问题）
          2) 召回过但没改变行为 → 候选
          3) 稀有保护（唯一签名）→ **硬否决**

        ★★★ R审计-P2 · 护栏（现场抓到的真风险）:
          第 2 层依赖 effect_count>0，但 `record_effect` **零生产调用**
          （inheritance.py 自陈"recall/record_effect 生产喂数未接线"）
          ⇒ effect_count 全库为 0 ⇒ 判据把**所有被召回的节点**都判成
            "召回过但零效果" ⇒ 误归档 79 条被使用的 trace（实测）。
          ⇒★ 修法: effect 未喂数 ⇒ 第 2 层判据**不可用** ⇒ 一律 held
            （不处置），并显式标注 effect_unfed（G7 不许静默）。
          ⇒ 等 record_effect 真接线、effect_count 有真数据后，本护栏自动失效。
        """
        rows = self.eviction_candidates()
        # ★ 护栏: 全库 effect 从未被记录 ⇒ 第 2 层不可用
        _n_eff = self._conn.execute(
            "SELECT COUNT(*) AS n FROM memory_node"
            " WHERE effect_count > 0").fetchone()["n"]
        _effect_unfed = (_n_eff == 0)
        held, archived, protected = [], [], []
        for r in rows:
            if r["rare_protected"]:
                protected.append(r["node_id"])       # 第3层: 硬否决
                continue
            if r["access_count"] == 0:
                held.append(r["node_id"])           # 第1层: 不处置
                continue
            if _effect_unfed:
                # ★ 第2层判据不可用 ⇒ 不处置（宁可不淘汰，不许误伤）
                held.append(r["node_id"])
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
            # ★ 诚实标注: effect 未喂数 ⇒ 归档层被护栏挡住
            "effect_unfed": _effect_unfed,
            "why_no_archive": ("effect_count 全库为 0（record_effect 未接线）"
                               "⇒ 第2层判据不可用 ⇒ 不归档" if _effect_unfed
                               else ""),
            # ★ 审计要点: held 占多数 ⇒ 那是检索策略的问题，不是记忆该删
            "hint": (("held:%d archived:%d protected:%d"
                      "（effect 未喂数 ⇒ 归档层未启用）"
                      if _effect_unfed else
                      "held:%d archived:%d protected:%d —— held 占比高说明 "
                      "recall 管要修，不是记忆该删")
                     % (len(held), len(archived), len(protected))),
        }

    # ══════════════════════════════════════════════
    # ★ R审计-P2 · P2-7 · learn 管（乘法门控巩固 → 回写 importance）
    # ══════════════════════════════════════════════
    #: learn 的门控参数（★ 待校准 — 借鉴 Prometheus-X DopamineWriteGate，
    #:   数值没有 DWC 自己的实测支撑，标为初值；改它只需改这里）
    LEARN_BETA = 0.1
    LEARN_UTILITY_TAU = 0.3

    def learn(self, node_ids: list[str] | None = None,
              beta: float | None = None) -> dict[str, Any]:
        """★ learn 管: 把「被使用」的实测事实巩固成 importance 权重。

        ★★★ 为什么需要它:
          七管里 learn 是唯一"巩固"管 —— 母巢原文: 「对每条记忆做
          effect×surprise 巩固, 回写 store 的 importance（记忆真的变
          '更重要'）, 而非返回常量」。DWC 此前 learn 不存在（core.py
          自认 not_dispatched）⇒ 记忆价值只停留在 access 计数。

        ★ 公式（乘法门控 — 零效用 ⇒ 零巩固）:
            utility  = min(1, 0.3×access + 0.7×effect)   # 效果权重更高
            surprise = 1/(1+同签名簇大小-1)              # 越稀有越意外
            score    = indicator(utility≥τ) × (utility × (surprise+β))
            importance = 0.5 + 0.5×score                 # 基线 0.5
        ★ LongMINT 教训（Prometheus-X 引）: 76.8% insert bias ⇒ 必须门控。
        ★ 只回写 importance 列；importance 变化才 UPDATE（少触发 FTS 重写）。
        """
        beta = self.LEARN_BETA if beta is None else float(beta)
        tau = self.LEARN_UTILITY_TAU
        if node_ids is None:
            rows = self._conn.execute(
                "SELECT node_id FROM memory_node"
                " WHERE archived_at IS NULL").fetchall()
            node_ids = [r["node_id"] for r in rows]
        n_updated = 0
        n_gated = 0
        items = []
        for nid in node_ids:
            try:
                n = self.get(nid)
            except MemoryError:
                continue
            utility = min(1.0, 0.3 * n.access_count + 0.7 * n.effect_count)
            # surprise: 失败签名按簇大小；其他 kind 无簇概念 ⇒ 0.5 中性
            surprise = 0.5
            if n.kind is MemoryKind.FAILURE_SIGNATURE:
                _c, _q, _m = (n.payload.get("c"), n.payload.get("q"),
                              n.payload.get("m"))
                if _c and _q and _m:
                    _same = self._conn.execute(
                        "SELECT COUNT(*) AS n FROM failure_sig"
                        " WHERE c=? AND q=? AND m=?",
                        (_c, _q, _m)).fetchone()["n"]
                    surprise = 1.0 / (1.0 + max(0, int(_same) - 1))
            gated = utility < tau
            if gated:
                imp = 0.5
                n_gated += 1
            else:
                score = min(1.0, utility * (surprise + beta))
                imp = round(0.5 + 0.5 * score, 4)
                n_updated += 1
            if abs(float(n.importance) - imp) > 1e-9:
                self._conn.execute(
                    "UPDATE memory_node SET importance=? WHERE node_id=?",
                    (imp, nid))
            items.append({"node_id": nid, "utility": round(utility, 3),
                          "surprise": round(surprise, 3),
                          "importance": imp, "gated": gated})
        self._conn.commit()
        return {"n_total": len(node_ids), "n_updated": n_updated,
                "n_gated": n_gated,
                "beta": beta, "tau": tau,
                # ★ 诚实标注: 参数是初值，未经 DWC 实测校准
                "params_status": "initial_uncalibrated",
                "items": items}

    # ══════════════════════════════════════════════
    # ★ R258 · 后向修订（ReHarness 2610.12668 §3.2）
    # ══════════════════════════════════════════════
    def revise(self, node_id: str, payload_new: dict[str, Any], *,
               source_traj: str, why: str) -> MemoryNode:
        """★ 版本链式修订一条 SKILL（reflection 等价物）。

        ★★ G2 grounding: source_traj 必填 —— 新内容必须可回溯到**源轨迹**
          （ReHarness: 当前实例只作反馈, 不作信息源 — 防泄漏）。
        ★ 守门单调性（2606.14249 同族）: 旧节点**内容字段原样**, 只加
          _revised_to 指针; 新节点 _rev_prev 链回 —— 双向版本链, 可回滚。
        ★ FAILURE_SIGNATURE 是事件流不修订（R104 同族: 事件是事实,
          经验才是可修订的解读）—— 只对 SKILL。
        """
        if not source_traj:
            raise MemoryError("修订必须引源轨迹（G2 grounding — 无源不修订）")
        old = self.get(node_id)
        if old is None:
            raise MemoryError("修订目标不存在: %s" % node_id)
        if old.kind is not MemoryKind.SKILL:
            raise MemoryError("修订只对 SKILL（事件流/工作态是事实, 不修订）")
        payload = dict(payload_new)
        payload["_rev_prev"] = node_id
        payload["_rev_why"] = str(why)[:300]
        payload["_rev_src"] = str(source_traj)[:400]
        new_id = self.remember(MemoryKind.SKILL, payload,
                               chain_id=old.chain_id)
        # 旧节点: 只加指针, 内容字段不动（审计可读原版）
        old_p = dict(old.payload)
        old_p["_revised_to"] = new_id
        self._conn.execute(
            "UPDATE memory_node SET payload=? WHERE node_id=?",
            (json.dumps(old_p, ensure_ascii=False), node_id))
        self._conn.commit()
        return self.get(new_id)

    def _note_retrieved(self, node_ids) -> None:
        """★ R258 检索留痕（修订候选集 — 只记 id, 环形上限 64）。"""
        for nid in node_ids:
            if nid not in self._retrieved[-8:]:
                self._retrieved.append(nid)
        del self._retrieved[:-64]

    def last_retrieved(self, n: int = 8) -> list[MemoryNode]:
        """★ 最近一次检索用过的节点（修订的候选集 — 检索留痕）。"""
        out = []
        for nid in list(reversed(self._retrieved))[:n]:
            node = self.get(nid)
            if node is not None:
                out.append(node)
        return out

    def revision_demo(self, n: int = 2) -> str:
        """★ R258 ③ 修订条目做 forward-write 的 demo（ReHarness 消融 0.217→0.191）。"""
        rows = self._conn.execute(
            "SELECT payload FROM memory_node WHERE kind=? "
            "AND payload LIKE '%_rev_prev%' ORDER BY created_at DESC LIMIT ?",
            (MemoryKind.SKILL.value, n)).fetchall()
        lines = []
        for r in rows:
            try:
                p = json.loads(r["payload"])
            except ValueError:
                continue
            lines.append("修订示例（旧: %s… → 新方法: %s…; 修订理由: %s）"
                         % (str(p.get("_rev_prev", ""))[:12],
                            str(p.get("method", p.get("scene", "")))[:120],
                            p.get("_rev_why", "")[:100]))
        return "\n".join(lines)

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
    def usage_stats(self) -> dict[str, Any]:
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