# -*- coding: utf-8 -*-
"""DWC 主类（core.py）· 三入口 + 组装契约测试。

★★★ 为什么这份测试重要
  主类是「agent 形态」本身 —— 三入口收拢后, DWC 第一次能被当作一个 agent
  而不是一堆器官来使用。它最易犯的病: ① 器官各存各的（入口与 runner 记忆
  不同源）② 决策层缺了却假装有 ③ 入口静默放行不合格痕迹。
  ⇒ 这里三件事都锁死。

★ 判据: ARCHITECTURE §2.1 形状 / §三 三入口 / §11.2 core.py 落点
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import ACTIONS, DwcError, DWC  # noqa: E402


def _dwc(**kw) -> DWC:
    kw.setdefault("depth_limit", 3)
    kw.setdefault("max_nodes", 50)
    d = DWC(**kw)
    # ★ R77 测试隔离: 构造走生产 store 路径（R71）⇒ 载回生产判分历史,
    #   δ 排序被生产盘数据触发 = 结果依赖生产状态 — 换内存 store 断开。
    from dwc.organs.judge import TaskScoreStore
    d.judge.store = TaskScoreStore(dw_version="test")
    return d


def _ok_executor(task):
    from dwc.organs.actor import Receipt
    return Receipt(ok=True, detail={"echo": task.get("task_id")}, verified=True)


class FakeLLM:
    """假 LLM（测试不打真端点 —— LLM 层的逻辑与降级可离线验）。"""

    configured = True

    def __init__(self, reply="remember", raises=False):
        self.reply, self.raises = reply, raises

    def complete(self, prompt, *, system=None):
        if self.raises:
            raise RuntimeError("endpoint down")
        return self.reply


# ══════════════════════════════════════════════════════════
# 组装 · §2.1 形状
# ══════════════════════════════════════════════════════════

def test_shape_holds_all_seven_organs():
    """§2.1 形状: 主类持有七器官（一个不少, 平级）。"""
    d = _dwc()
    for name in ("memory", "judge", "actor", "world_model", "evolver",
                 "iwm", "iron_laws"):
        assert hasattr(d, name), "★ 形状缺器官: %s" % name
    assert isinstance(d.iron_laws, dict) and d.iron_laws["laws"]


def test_organs_are_shared_not_copied():
    """★★ 一个 agent 一份状态: runner 与主类共享同一批器官实例。"""
    d = _dwc()
    assert d.runner.memory is d.memory
    assert d.runner.judge is d.judge
    assert d.runner.world_model is d.world_model
    assert d.runner.iwm is d.iwm


def test_constructor_requires_depth_and_max_nodes():
    """W6 同款: 组装参数必填无默认（不许主类里埋默认深度）。"""
    with pytest.raises(TypeError):
        DWC()
    with pytest.raises(DwcError, match="depth_limit"):
        DWC(0, 50)
    with pytest.raises(DwcError, match="max_nodes"):
        DWC(3, -1)


def test_iron_laws_load_validates_ids_and_severity():
    """铁律配置面加载带校验（id 唯一 + severity 三档）—— 并且真的校验。"""
    from dwc.core import _load_iron_laws
    import tempfile
    p = os.path.join(tempfile.gettempdir(), "bad_laws.yaml")
    with open(p, "w", encoding="utf-8") as f:
        f.write("version: 1\nlaws:\n- id: G1\n  severity: banana\n")
    with pytest.raises(DwcError, match="severity"):
        _load_iron_laws(p)
    os.remove(p)


# ══════════════════════════════════════════════════════════
# 入口① · ingest
# ══════════════════════════════════════════════════════════

def test_ingest_good_trace_enters_memory():
    """合法痕迹 → MemoryId, 记忆 total +1。"""
    d = _dwc()
    mid = d.ingest({"outcome": "returned", "success": True,
                    "action": "demo"}, chain_id="CH_t")
    assert isinstance(mid, str) and mid
    assert d.memory.usage_stats()["total"] == 1


def test_ingest_rejects_unjudgable_trace():
    """阳性①: outcome 与 success 双 None ⇒ 不可评价, 拒收。"""
    d = _dwc()
    with pytest.raises(DwcError, match="不可评价"):
        d.ingest({"outcome": None, "success": None}, chain_id="CH_t")
    assert d.memory.usage_stats()["total"] == 0, "拒收不许落盘"


def test_ingest_rejects_failed_trace_without_signature():
    """阳性②: 失败痕迹无 failure_signature ⇒ 拒收（失败定位硬要求）。"""
    d = _dwc()
    with pytest.raises(DwcError, match="failure_signature"):
        d.ingest({"outcome": "raised", "success": None}, chain_id="CH_t")
    with pytest.raises(DwcError, match="failure_signature"):
        d.ingest({"outcome": "returned", "success": False}, chain_id="CH_t")
    # 带上签名就放行
    mid = d.ingest({"outcome": "raised", "success": None,
                    "failure_signature": {"c": "c1", "q": "q1", "m": "m1"}},
                   chain_id="CH_t")
    assert mid


def test_ingest_rejects_unknown_shape():
    """阳性③: 只收 Trace / dict —— 不猜其他形态。"""
    d = _dwc()
    with pytest.raises(DwcError, match="只收"):
        d.ingest(["not", "a", "trace"], chain_id="CH_t")


# ══════════════════════════════════════════════════════════
# 入口② · step
# ══════════════════════════════════════════════════════════

def test_step_requires_executor():
    """阳性: 没有执行器 ⇒ 大声报错（不假装能行动）。"""
    d = _dwc()
    with pytest.raises(DwcError, match="executor"):
        d.step({"task_id": "t1", "kind": "demo"})


def test_step_runs_decide_act_ingest_chain():
    """★ 完整链: 决策 → 执行 → 痕迹入记忆（三入口的 step 半环）。"""
    d = _dwc(executor=_ok_executor)
    out = d.step({"task_id": "t1", "kind": "demo"})
    assert out["decision"]["source"] == "heuristic"     # llm 未配置
    assert out["decision"]["action"] == "remember"
    assert out["trace"].outcome == "returned"
    assert out["memory_id"] and d.memory.usage_stats()["total"] == 1
    assert out["chain_id"].startswith("CH_step_")


def test_step_takes_task_from_world_tree():
    """环节⑥: 不给 task ⇒ 从世界树未揭示叶子取（任务自产, 不编造）。

    ★ R77 播种改约: 构造即播 dev 任务（§4.7「初始播种」）⇒ 空树不再出现
      在构造时, 只在**全部揭示后** —— 空 raise 语义保留到那个终态。
    """
    d = _dwc(executor=_ok_executor)
    # ★ 播种断言: 构造即有 dev 任务叶, 且 node_id = judge task_id（同域）
    dev_ids = {t for t in d.judge.anchors if not t.startswith("_")}
    acts = d.world_model.legal_actions()
    assert {a["node"] for a in acts} == dev_ids and len(dev_ids) > 0
    out = d.step()
    assert out["trace"].action_params["task_source"].startswith("world_model:")
    # ★ 全部揭示 ⇒ 空树 raise 原语义仍在
    for a in acts:
        d.world_model.record_observation(a["tree"], a["node"], 1.0, True)
    with pytest.raises(DwcError, match="没有可执行对象"):
        d.step()


def test_step_pre_enactment_layer_is_honestly_absent():
    """★★ §3.2 第一层: DWC 无 dynamics 预测层 ⇒ available=False 显式缺席。"""
    d = _dwc(executor=_ok_executor)
    out = d.step({"task_id": "t1", "kind": "demo"})
    pre = [x for x in out["decision"]["layers"]
           if x["layer"] == "pre_enactment"]
    assert pre and pre[0]["available"] is False


def test_step_llm_layer_selects_action():
    """LLM 层 configured ⇒ source=llm 且动作来自显式动作集。"""
    d = _dwc(executor=_ok_executor, llm=FakeLLM(reply="evolve"))
    out = d.step({"task_id": "t1", "kind": "demo"})
    assert out["decision"]["source"] == "llm"
    assert out["decision"]["action"] == "evolve"
    # ★ R138: action_dispatched 从 str 改 dict（kind/dispatched/why）—
    #   语义不变: evolve 不假装分发（dispatched=False + 理由在位）
    disp = out["action_dispatched"]
    assert isinstance(disp, dict), "R138 后是结构化分发记录"
    assert disp["kind"] == "evolve" and disp["dispatched"] is False, \
        "非 remember/dream 动作不假装分发（诚实边界）"
    assert "not_dispatched" in disp["why"]


def test_step_llm_bad_reply_degrades_with_trace():
    """LLM 回非动作 ⇒ 降级 heuristic 且 layers 里留痕（G7: 不静默）。"""
    d = _dwc(executor=_ok_executor, llm=FakeLLM(reply="我全都要"))
    out = d.step({"task_id": "t1", "kind": "demo"})
    assert out["decision"]["source"] == "heuristic"
    why = " ".join(x["why"] for x in out["decision"]["layers"])
    assert "降级" in why and "我全都要" in why


def test_step_llm_exception_degrades_with_trace():
    """LLM 抛异常 ⇒ 降级 + 异常名进 layers（except 有留痕, G7 同族）。"""
    d = _dwc(executor=_ok_executor, llm=FakeLLM(raises=True))
    out = d.step({"task_id": "t1", "kind": "demo"})
    assert out["decision"]["source"] == "heuristic"
    why = " ".join(x["why"] for x in out["decision"]["layers"])
    assert "RuntimeError" in why and "endpoint down" in why


def test_action_set_is_explicit():
    """§3.2: 候选动作是显式动作集（不是由任务类型决定）。"""
    assert ACTIONS == ("remember", "learn", "dream", "maintain", "evolve")


# ══════════════════════════════════════════════════════════
# 入口③ · run_term
# ══════════════════════════════════════════════════════════

def test_run_term_delegates_to_runner():
    """★ run_term 委托 TermRunner（六步不重写）且共享同一记忆。"""
    d = _dwc()
    rep = d.run_term("t", n_steps=1)
    assert rep.missing_stages() == []
    assert rep.memory_after["total"] == 1
    assert d.memory.usage_stats()["total"] == 1, \
        "★ 入口与 runner 必须同一份记忆（不许各存各的）"


def test_lazy_export_from_package():
    """`from dwc import DWC` 惰性导出可用（§11.2 字面 + 不触发循环）。"""
    from dwc import DWC as Exported
    assert Exported is DWC
    import dwc
    with pytest.raises(AttributeError):
        dwc.not_a_thing
