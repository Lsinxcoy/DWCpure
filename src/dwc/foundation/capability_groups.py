"""config/capability_groups.yaml 的加载器 + 校验器。

★★★ 存在理由（R9/A11 教训的直接应用）
  判据 G1–G6 之前只是文档里的一段话，谁也没跑过。
  本模块把它们变成**可执行**的校验：
    · 重算派生字段（lambda_floor_ratio = 1 / n_assertions_median）
      —— config 里刻意不手填（derived_fields.reason 记了为什么）
    · 重新解析 sealed_tasks.yaml，与 config 逐项比对
      —— 这是 G3 的可执行形式：防止 yaml 里的中位数与任务集脱节
    · 空集合不许报"通过"（沿用 gate.py 的 n_a 契约）
      —— 否则 config 写错组名时会静默通过

  ★ 但本模块**不改任何文件**，只报告。它是只读校验器。

定位声明（DWC-MEM · 记忆底座）
  ★ 本模块是 config/ 的加载器与校验器，属记忆底座（判据 G1 定位门要求）：
    能力组定义 = "进化对象清单"，它决定 DWC 能改什么 ⇒ 属 DWC-MEM
  ★ 它不被任何器官直接调用，只被 evolver/gate 读 ⇒ 无跨器官私有态（判据 P1）
  ★ 它**只读不写**：任何校验失败都 raise ConfigError，绝不静默降级
    （依据：原则 6「器官之间只经接口」+ 判据 E3「except: pass 命中数 == 0」）

关于 G3 六层活性门（本文件不提供六层字段，故会报红）
  ★★★ 这是**有意留红**，不是遗漏:
    QUALITY_GATE.md §门3 自己写着「六层模型是**候选，不是必然**」
    「DWC 可能用别的分层，也可能根本不需要分层」
  ⇒ 而 gate.py 把六层字段当成硬要求，对任何不含这些字段的文件报红
  ⇒ 本模块是配置加载器，不需要"活性分层"语义
  ⇒ ★ 该冲突已登记，待裁（见 PROGRESS 的下一步）

坐标：
  ROOT = 仓库根（dwc.foundation.paths.find_root() 发现）
  cfg  = config/capability_groups.yaml
  src  = E:/ARSI/config/sealed_tasks.yaml   ← 源数据（不在本仓）
"""
from __future__ import annotations

import os
import statistics
from dataclasses import dataclass, field
from typing import Any

import yaml

#: ROOT 内联上溯（本模块保持可独立直跑 — 不 import dwc 自身, 零依赖:
#:   foundation/ → dwc/ → src/ → 仓库根; env DWC_ROOT 仍可覆盖）
_ROOT_ENV = os.environ.get("DWC_ROOT", "").strip()
ROOT = (_ROOT_ENV if _ROOT_ENV and os.path.isdir(_ROOT_ENV) else
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))))
CFG_PATH = os.path.join(ROOT, "config", "capability_groups.yaml")
#: ★ R审计-P0 · sealed_tasks 判据文件路径可配置化（不再写死 E:/ARSI 开发机路径）:
#:   env DWC_SEALED_TASKS 优先 → 缺省仓库内 config/sealed_tasks.yaml →
#:   两处都没有时保持 ConfigError（「无法判定不是通过」语义不变）。
_SEALED_ENV = os.environ.get("DWC_SEALED_TASKS", "").strip()
SEALED_PATH = (_SEALED_ENV if _SEALED_ENV else
               os.path.join(ROOT, "config", "sealed_tasks.yaml"))


# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════

class ConfigError(Exception):
    """config 违反硬约束。★ 承重代码不许吞异常（判据 E2/E3）。"""


@dataclass(frozen=True)
class AssertionStats:
    """一条 sealed 任务的断言统计。★ frozen ⇒ 不可变（判据 I6 同款）。"""
    task_id: str
    category: str
    verifier_rung: int
    kind: str                    # behavior / keywords / values
    n_assertions: int


@dataclass(frozen=True)
class Group:
    group_id: str
    sealed_task_ids: tuple[str, ...]
    scoring: str
    verifier_rung: int
    n_assertions_per_task: tuple[int, ...]
    n_assertions_total: int
    n_assertions_median: float
    lambda_assert: int
    epsilon: int
    measurable: bool
    has_history_scores: bool
    disjoint_basis: str
    # ★ 派生字段：由 loader 从 n_assertions_median 重算，不从 config 读
    lambda_floor_ratio: float = field(default=0.0)


# ══════════════════════════════════════════════════════════
# 源数据解析
# ══════════════════════════════════════════════════════════

def _count_assertions(task: dict[str, Any]) -> tuple[str, int]:
    """★ 口径必须先声明再统计（原则 13 纪律②）

    口径声明：
      behavior → expected_behavior 按 " and " 切分数段
      keywords → len(expected_keywords)
      values   → len(expected_values) 的键数
    ⇒ 三种口径的"一个断言"含义不同，这是已知遗留（诚实边界②）。
    """
    if task.get("expected_behavior"):
        return "behavior", str(task["expected_behavior"]).count(" and ") + 1
    if task.get("expected_keywords"):
        return "keywords", len(task["expected_keywords"])
    if task.get("expected_values"):
        return "values", len(task["expected_values"])
    raise ConfigError(
        "任务 %r 三种断言字段全缺 ⇒ 无法计断言数（不许默认为 1）"
        % task.get("id"))


def load_sealed(path: str = SEALED_PATH) -> list[AssertionStats]:
    """解析 sealed_tasks.yaml。★ 路径不存在必须 raise，不许静默返回空。"""
    if not os.path.exists(path):
        raise ConfigError("sealed_tasks 不存在: %s" % path)
    obj = yaml.safe_load(open(path, encoding="utf-8").read())
    tasks = obj.get("tasks") if isinstance(obj, dict) else obj
    if not tasks:
        raise ConfigError("sealed_tasks 里没有 tasks ⇒ 无可检对象（不是『通过』）")
    out = []
    for t in tasks:
        kind, n = _count_assertions(t)
        out.append(AssertionStats(
            task_id=t["id"], category=t["category"],
            verifier_rung=int(t["verifier_rung"]),
            kind=kind, n_assertions=n))
    return out


# ══════════════════════════════════════════════════════════
# config 解析 + 校验
# ══════════════════════════════════════════════════════════

def load_config(path: str = CFG_PATH) -> dict[str, Any]:
    if not os.path.exists(path):
        raise ConfigError("config 不存在: %s" % path)
    return yaml.safe_load(open(path, encoding="utf-8").read())


def build_groups(cfg: dict[str, Any],
                 sealed: list[AssertionStats]) -> list[Group]:
    """构造 Group 列表，重算派生字段，并执行 G1–G6。"""
    cons = cfg.get("constraints") or {}
    n_min = int(cons.get("n_min_per_group", 3))

    by_id = {s.task_id: s for s in sealed}
    all_ids = [s.task_id for s in sealed]

    groups: list[Group] = []
    for raw in cfg["groups"]:
        gid = raw["group_id"]
        ids = tuple(raw["sealed_task_ids"])

        # ── G1: 组内引用的任务必须真实存在 ──
        for tid in ids:
            if tid not in by_id:
                raise ConfigError("G1: 组 %s 引用了不存在的任务 %r" % (gid, tid))

        src = [by_id[t] for t in ids]
        per = tuple(s.n_assertions for s in src)
        total = sum(per)
        median = float(statistics.median(per))
        rungs = {s.verifier_rung for s in src}

        g = Group(
            group_id=gid, sealed_task_ids=ids,
            scoring=raw["scoring"],
            verifier_rung=int(raw["verifier_rung"]),
            n_assertions_per_task=per, n_assertions_total=total,
            n_assertions_median=median,
            lambda_assert=int(raw["lambda_assert"]),
            epsilon=int(raw["epsilon"]),
            measurable=bool(raw["measurable"]),
            has_history_scores=bool(raw["has_history_scores"]),
            disjoint_basis=raw["disjoint_basis"],
            # ★ 派生字段：重算，不读 config（derived_fields.reason 的要求）
            lambda_floor_ratio=1.0 / median,
        )

        # ── G3: config 声称的统计量必须与源数据一致 ──
        if list(raw["n_assertions_per_task"]) != list(per):
            raise ConfigError(
                "G3: 组 %s 的 n_assertions_per_task 声称 %r, 源数据实为 %r"
                % (gid, list(raw["n_assertions_per_task"]), list(per)))
        if int(raw["n_assertions_total"]) != total:
            raise ConfigError("G3: 组 %s 的 total 声称 %r, 实为 %d"
                              % (gid, raw["n_assertions_total"], total))
        if float(raw["n_assertions_median"]) != median:
            raise ConfigError("G3: 组 %s 的 median 声称 %r, 实为 %r"
                              % (gid, raw["n_assertions_median"], median))
        if len(rungs) != 1:
            raise ConfigError("组 %s 的 verifier_rung 不唯一: %r" % (gid, sorted(rungs)))
        if g.verifier_rung != rungs.pop():
            raise ConfigError("组 %s 声称 rung=%d, 源数据是 %d"
                              % (gid, g.verifier_rung, int(raw["verifier_rung"])))

        # ── G2: 每组至少 n_min 条 ──
        if len(ids) < n_min:
            raise ConfigError("G2: 组 %s 只有 %d 条 (< n_min=%d)" % (gid, len(ids), n_min))

        # ── G4: lambda_assert >= 1/median，否则第⑦步是死判据 ──
        if g.lambda_assert < g.lambda_floor_ratio:
            raise ConfigError(
                "G4: 组 %s 的 lambda_assert=%d < 1/median=%.4f ⇒ 第⑦步是死判据"
                % (gid, g.lambda_assert, g.lambda_floor_ratio))

        groups.append(g)

    # ── G1 全局: 覆盖率（无遗漏无重复）──
    covered = [t for g in groups for t in g.sealed_task_ids]
    missing = set(all_ids) - set(covered)
    dup = sorted({t for t in covered if covered.count(t) > 1})
    if missing:
        raise ConfigError("G1: 有 sealed 任务未被任何组覆盖: %r" % sorted(missing))
    if dup:
        raise ConfigError("G1: 有任务被多个组覆盖: %r" % dup)

    # ── G6: 组数上限 ──
    cap = len(all_ids) // n_min
    if len(groups) > cap:
        raise ConfigError("G6: 组数 %d > 上限 %d/%d=%d"
                          % (len(groups), len(all_ids), n_min, cap))

    # ── G5: 至少两处消费点 ──
    if len(cfg.get("consumers") or []) < 2:
        raise ConfigError("G5: consumers 不足两处 ⇒ 能力组只是标签")

    return groups


def validate_all(cfg_path: str = CFG_PATH,
                 sealed_path: str = SEALED_PATH) -> list[Group]:
    """一步到位。★ 任何违反都 raise，不返回『部分通过』。"""
    return build_groups(load_config(cfg_path), load_sealed(sealed_path))


# ══════════════════════════════════════════════════════════

if __name__ == "__main__":
    gs = validate_all()
    print("capability_groups 校验通过: %d 组 / %d 任务" % (
        len(gs), sum(len(g.sealed_task_ids) for g in gs)))
    for g in gs:
        print("  %-22s n=%d rung=%d median=%.1f total=%-3d λ=%d "
              "1/median=%.4f ε=%d history=%s"
              % (g.group_id, len(g.sealed_task_ids), g.verifier_rung,
                 g.n_assertions_median, g.n_assertions_total,
                 g.lambda_assert, g.lambda_floor_ratio, g.epsilon,
                 g.has_history_scores))