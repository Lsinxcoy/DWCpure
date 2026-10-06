"""R30 · 端到端闭环 —— ★ 五段一次跑完，分数必须真来自两端。

★★★★★ 为什么这个脚本要入仓（它比任何单测都值钱）:
  本轮 **5 个断点全部是它抓到的**，而当时 357 项分段测试**全是绿的**:
    1 execute_task 只跑 REFERENCE ⇒ 带 bug 的实现跑不了
    2 patch 被路由给 applier（应归执行器）
    3 judge 不产签名 + actor 只在异常时产 ⇒ 三端都不产 ⇒ 手填
    4 三元组语义 (c,q,m) 被我当 (错误类, 函数名, 动作)
    5 apply_on_copy 对不存在的键留下 key:None 垃圾
  ⇒⇒ ⇒★★ '分段绿 != 链路通' 的**可复跑证据**
  ⇒⇒ ⇒★ 所以它进了 scripts/ —— 不是探针，是**回归验证**

  ★ 复跑: `python scripts/e2e_loop.py`（任意 cwd）
    成功标志: 最后一行 `★★★★★ 五段真接通了` 且 rc=0
  ★ 它会在 step5 的污染断言处**主动失败**（若 applier 退化）


R30 · 端到端闭环 —— 五段一次跑完，分数必须真来自两端。

★★★ 与上一次端到端的三处不同（那次暴露了三个断点）:
  ① execute_task 现在能传 implementation ⇒ 带 bug 的实现跑得了
  ② applier 落地的是 **RULES 条目**（甲类），patch 交给 actor 构建候选
  ③ 结算的 base/current **真来自** step2/step6 的 judge 输出
       ⇒★ 上次那两个是手工传的（gain=0.1 是假的）
"""
import os, sys, json, traceback
import subprocess
# ★★ 以脚本位置定位仓库根（可从任意 cwd 跑）
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge
from dwc.organs.actor import (Actor, execute_task, build_implementation,
                              PureFunctionExecutor)
from dwc.organs.evolver import Evolver, Mutator, Proposal
from dwc.organs.applier import Applier, Target, ApplierError
from dwc.organs.candidates import CandidateGenerator

# ★══★★★ 必须用 subprocess 跑，否则 kernel 里的旧模块读不到改动（本轮已踩）
j = Judge()
ev = Evolver()
ap = Applier(window=2)
TASK = "code_fix_001"
FN = "sum_first_n"
STEP = []


def step(n, title, **kw):
    STEP.append(dict(n=n, title=title, **kw))
    print("\n" + "=" * 60)
    print("step %d · %s" % (n, title))
    print("=" * 60)


# ── 1 · 带 bug 的实现 ──────────────────────────────────────
step(1, "准备带 bug 的实现")
BUGGY = "def sum_first_n(n):\n    return sum(range(n))"   # off-by-one
print("  %r" % BUGGY)

# ── 2 · 执行 + 判分（★ 这次跑的是 agent 的产出，不是 REFERENCE）──
step(2, "执行 + 判分（跑 agent 的产出）")
out1 = execute_task(Actor(), j, TASK, implementation=BUGGY)
print("  implementation_source = %s" % out1["implementation_source"])
v1 = j.evaluate(TASK, "dev", observed=out1["observation"])
print("  judge: success=%s" % v1.success)
base_score = 1.0 if v1.success else 0.0
print("  ★ base_score = %s（真来自 judge，不是手工传的）" % base_score)
if v1.success:
    print("  ★★ 意外: bug 实现也过？说明断言太松 —— 看观测:")
    print("    %s" % out1["observation"])

# ── 3 · 失败签名 ──────────────────────────────────────────
step(3, "失败签名（judge 产出 · R30 补的根因）")
# ★★★★ R30 后 judge 产签名（c/q 由规则分配 —— 2609.06396 原文分工）
#   ⇒ 不再手填 —— 手填是上次端到端断在 step4 的**根因**
print("  judge.failure_signature = %s" % v1.failure_signature)
print("  judge.diffs = %s" % ([d["reason"] for d in (v1.diffs or [])]))
assert v1.failure_signature, "★ judge 必须产签名（否则闭环仍断）"
sigs = [dict(v1.failure_signature)]
print("  ★ 签名由 judge 产出，非手填")

# ── 4 · evolver 提案 ──────────────────────────────────────
# ── 4 · 诊断 → 提案 → ★ 若未命中则转**候选生成**（R31 学习半边）──
step(4, "诊断 + 提案 + 学习半边（R31 新增生成器）")
d = ev.diagnose(sigs)
props = d["proposals"]
print("  查表: n_proposals=%d n_unmapped=%d n_clusters=%d"
      % (len(props), d["n_unmapped"], d["n_clusters"]))

gen = CandidateGenerator()
# ★★ 无论查表结果如何，都跑一次生成器（验证它与查表**并存**）
#   基线必须是**带 bug 的实现**（R31 纪律④: 传错会被拒）
r_gen = gen.generate(sigs[0], v1.diffs, BUGGY, fn_name=FN)
print("  生成: n=%d need_llm=%s" % (r_gen["n"], r_gen["need_llm"]))
print("        why=%s" % r_gen["why"][:70])

if props:
    p = props[0]
    print("  ★ 查表命中 ⇒ 走既有规则（学习半边不触发）")
    print("    proposal=%s target=%s patch=%r"
          % (p.proposal_id, p.target, p.patch))
else:
    # ★★★ 这就是"学习"的入口 —— R31 之前 unmapped 是**终点**
    print("  ★★ 查表未命中 ⇒ R31 前这里是终点（从失败学不到东西）")
    if r_gen["candidates"]:
        p = None
        print("    ⇒ 现在转候选生成（trace-grounded）:")
        for c in r_gen["candidates"]:
            print("      [%s] %r  grounding=%d"
                  % (c.rule, c.patch, len(c.grounding)))
    else:
        p = None
        print("    ⇒ 生成器也推不出 ⇒ need_llm=%s（诚实标注）"
              % r_gen["need_llm"])

LEARN = r_gen
LEARN_SOURCE = "lookup" if props else (
    "generated" if r_gen["candidates"] else "need_llm")

# ── 5 · applier 落地 RULES 条目（甲类）────────────────────
step(5, "applier 落地 RULES 条目（甲类 · 不是丙类代码替换）")
# ★★★ R30: 落地键取自 judge 的签名（c:q:fn）
RULES_KEY = "%s:%s:%s" % (v1.failure_signature["c"],
                          v1.failure_signature["q"],
                          v1.failure_signature["fn"])
print("  落地键: %s" % RULES_KEY)

# ── 5a · 本次是否有新规则要落？──
exists = RULES_KEY in Mutator.RULES
if exists:
    print("  ★ 该规则**已存在** ⇒ 本次无新规则可落")
    print("    (这条规则正是 step4 提案的来源 —— 落地它没有意义)")
    print("  ⇒⇒ 这才是本次闭环的**真实情况**: 提案来自已有知识，")
    print("    而**学习新规则**是另一条闭环（本次未触发）")
else:
    print("  ★ 该键不存在 ⇒ 要落地新规则（甲类: dict 项）")

# ── 5b · ★★ 真正验证 applier 不污染（用一个**不存在**的键）──
print("  ★★★ 单独验证: 对**不存在**的键试写，主干必须干净")
PROBE_KEY = "E_PROBE_NEVER:probe:probe"
tgt_probe = Target(getter=lambda: Mutator.RULES.get(PROBE_KEY),
                   setter=lambda v: Mutator.RULES.__setitem__(PROBE_KEY, v),
                   has_fn=lambda: PROBE_KEY in Mutator.RULES,
                   delete_fn=lambda: Mutator.RULES.pop(PROBE_KEY, None))
before = PROBE_KEY in Mutator.RULES
cp = ap.apply_on_copy("P_probe", tgt_probe, {"probe": True})
after = PROBE_KEY in Mutator.RULES
print("     试写前键存在=%s 试写后键存在=%s 清理方式=%s"
      % (before, after, cp["cleaned"]))
assert after == before, \
    "★★★ 试写改变了主干的键集合（R30 抓到的 applier bug）"
print("     ✓ 主干未被污染（2606.09498 line 9 的硬要求）")

# ── 5c · 若键不存在，真正落地一次（本轮是存在的 ⇒ 记录跳过）──
if not exists:
    tgt = Target(getter=lambda: Mutator.RULES.get(RULES_KEY),
                 setter=lambda v: Mutator.RULES.__setitem__(RULES_KEY, v),
                 has_fn=lambda: RULES_KEY in Mutator.RULES,
                 delete_fn=lambda: Mutator.RULES.pop(RULES_KEY, None))
    entry = {"component": props[0].component, "dimension": "D7",
             "target": props[0].target, "m": "",
             "m_source": "rule", "patch": props[0].patch,
             "rationale": props[0].rationale}
    res = ap.commit("P_rule", tgt, entry)
    print("  commit ✓ readback_ok=%s" % res.readback_ok)

# ── 6 · 构建候选实现 + 重判 ────────────────────────────────
step(6, "用 patch 构建候选实现 → 重判（★ 分数该上升）")
base_src = PureFunctionExecutor.REFERENCE[FN]
print("  基线: %r" % base_src)
cand = build_implementation(FN, base_src, p.patch)
print("  候选: %r" % cand)
out2 = execute_task(Actor(), j, TASK, implementation=cand)
print("  implementation_source = %s" % out2["implementation_source"])
v2 = j.evaluate(TASK, "dev", observed=out2["observation"])
print("  judge: success=%s" % v2.success)
cur_score = 1.0 if v2.success else 0.0
print("  ★ current_score = %s（真来自 judge）" % cur_score)

# ── 7 · 结算（base 真来自 step2，current 真来自 step6）─────
step(7, "结算（两头都是真分数）")
# ★ 端到端跑一次 ⇒ steps = 窗口 2（2 次执行 = 2 step）
st = ap.window_settle("P_rule", steps=2, base_score=base_score,
                      current_score=cur_score,
                      scorer_resolution=1.0,   # ★ 二值判分 ⇒ 分辨率=1
                      min_gain=0.0)
print("  base=%.1f current=%.1f gain=%.1f" % (st.get("base_score", -1),
                                              st.get("current_score", -1),
                                              st.get("gain", -9)))
print("  verdict = %s" % st.get("verdict"))
if st.get("verdict") == "revert":
    ap.rollback("P_rule", tgt)
    print("  → 已回滚，RULES 含该键 = %s" % (RULES_KEY in Mutator.RULES))

# ── 汇总 ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("端到端结果")
print("=" * 60)
print("  step2 base  = %.1f  (buggy 实现)" % base_score)
print("  step6 cur   = %.1f  (候选实现)" % cur_score)
print("  判定        = %s" % st.get("verdict"))
print("  落地记录    = %s" % json.dumps(ap.stats(), ensure_ascii=False))
ok = (base_score == 0.0 and cur_score == 1.0
      and st.get("verdict") == "keep")
print("\n  %s" % ("★★★★★ 五段真接通了: 分数从 0 → 1 且判 keep"
                 if ok else "★ 链路未达成预期（看上面哪段不对）"))

# ══════════════════════════════════════════════════════════
# ★★★★★ step 8 · **学习闭环**（R31: 查表未命中 ⇒ 生成候选 ⇒ 试 ⇒ 淘汰）
#    这是"进化增量"的唯一证据 —— 前面七步走的都是**已有知识**
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("step 8 · 学习闭环（RULES 里**没有**的失败 ⇒ 走生成器）")
print("=" * 60)

# ★ 用 RULES 未覆盖的函数（R1 需源码含 range ⇒ 选 fibonacci）
LEARN_FN = "fibonacci"
BUGGY2 = ("def fibonacci(n):\n    a, b = 0, 1\n"
          "    for _ in range(n - 1):\n        a, b = b, a + b\n"
          "    return a")
print("  目标: %s（RULES 未覆盖）" % LEARN_FN)
print("  带 bug 实现: %r" % BUGGY2)

# 8a · 执行 + 判分
T2 = None
for k in j.anchors:
    if not k.startswith("_"):
        fns = {c.get("fn") for c in (j.anchors[k].get("checks") or [])
               if c.get("fn")}
        if fns == {LEARN_FN}:
            T2 = k
            break
assert T2, "★ dev 里找不到 %s 的任务（前提变了）" % LEARN_FN
print("  任务: %s" % T2)

# ★★★★ R32 · **进入场景时**自清洁（不是结束时）
#   ★ 实测教训: 上一次跑因 CROSS_OK 的 NameError **中断** ⇒
#     放在结尾的自清洁**没执行** ⇒ fibonacci 规则残留 ⇒
#     这次开跑 `n_proposals=1` ⇒ 8b 的"应不在 RULES"前提炸
#   ⇒⇒ ⇒★★ 结论: 自清洁必须在**用到前提之前**做
#     —— 否则它防不住"上次异常中断"（而异常恰恰最可能留下脏状态）
print("  ── 前置自清洁（确保从零学起）──")
from dwc.organs.evolver import Mutator as _M   # ★ 提到这里（8g 之前就用）
_sig8_key = "%s:%s:%s" % ("E_OFF_BY_ONE", "off_by_one_in_range", LEARN_FN)
if _sig8_key in _M.RULES:
    # ★★★★ R32 实测: 这里**不能**用 ap.rollback ——
    #   那条规则是**上一个进程**落地的，本次 applier 没有它的 `_history`
    #   ⇒ 实测 raise "无落地历史 ⇒ 无法回滚"
    #   ⇒⇒ ⇒★★ 暴露持久化引入的**语义不对称**:
    #     · rollback = 撤销**本次进程**的落地（有 history 才成立）
    #     · 清理残留 = 删**上次进程**留下的（本次 history 里根本没有）
    #   ⇒ ⇒★ 两者**不是一回事**，不该复用同一个操作
    #   ⇒⇒ ⇒★ 而这还留了个缺口: 落地历史**不持久化** ⇒
    #     跨进程无法"回滚上次的固化"（已记入诚实边界）
    print("    ★ 检测到残留规则 ⇒ **直接清理**（不是 rollback，本次无它的历史）")
    _M.RULES.pop(_sig8_key, None)
    _M.persist_learned()
    print("    ✓ 已清理 + 落盘同步")
if os.path.exists(_M.LEARNED_PATH):
    _ld = json.load(open(_M.LEARNED_PATH, encoding="utf-8"))
    if not (_ld.get("learned") or {}):
        os.remove(_M.LEARNED_PATH)
        print("    ✓ 落盘已清（learned 空 ⇒ 删除文件）")
assert _sig8_key not in _M.RULES, "★ 前置自清洁未生效"
print("    ✓ 已就绪（RULES=%d 条，不含 fibonacci）" % len(_M.RULES))
out8 = execute_task(Actor(), j, T2, implementation=BUGGY2)
v8 = j.evaluate(T2, "dev", observed=out8["observation"])
print("  judge: success=%s" % v8.success)
assert v8.failure_signature, "★ 必须产出失败签名"
sig8 = v8.failure_signature
print("  sig: c=%s q=%s fn=%s" % (sig8["c"], sig8["q"], sig8["fn"]))

# 8b · 查表（应未命中 ⇒ RULES 没这条）
d8 = ev.diagnose([dict(sig8)])
print("  查表: n_proposals=%d n_unmapped=%d"
      % (len(d8["proposals"]), d8["n_unmapped"]))
assert not d8["proposals"], "★ 该签名应**不在** RULES 里（前提变了）"
print("  ★★★ R31 之前这里是**终点** —— 学不到任何东西")

# 8c · 生成候选（trace-grounded · 基线 = 带 bug 实现）
gen2 = CandidateGenerator()
r8 = gen2.generate(sig8, v8.diffs, BUGGY2, fn_name=LEARN_FN)
print("  生成: n=%d need_llm=%s why=%s"
      % (r8["n"], r8["need_llm"], r8["why"][:56]))
for c in r8["candidates"]:
    print("    [%s] %r" % (c.rule, c.patch))

# 8d · ★ 逐个候选: 构建 → 判分 → 采纳 or **淘汰**
print("\n  ── 试错（判分决定去留）──")
best = None
for c in r8["candidates"]:
    try:
        src = build_implementation(LEARN_FN, BUGGY2, c.patch)
    except Exception as e:
        print("    %-40s 构建失败 %s" % (c.rule, str(e)[:24]))
        gen2.record_rejection(c, "构建失败: %s" % type(e).__name__)
        continue
    o = execute_task(Actor(), j, T2, implementation=src)
    vv = j.evaluate(T2, "dev", observed=o["observation"])
    if vv.success and best is None:
        best = (c, src)
        print("    %-40s judge=%s ★采纳" % (c.rule, vv.success))
    else:
        print("    %-40s judge=%s 淘汰" % (c.rule, vv.success))
        gen2.record_rejection(c, "judge 判 fail（不修好）")

# 8e · ★ 淘汰表生效（同轮再生成 ⇒ 已否决的不重出）
print("\n  ── 淘汰表生效检查（G4）──")
r8b = gen2.generate(sig8, v8.diffs, BUGGY2, fn_name=LEARN_FN)
print("    再生成: n=%d（原 %d）· 淘汰池=%d"
      % (r8b["n"], r8["n"], len(gen2.rejected)))
if r8["n"] > 0 and r8b["n"] < r8["n"]:
    print("    ✓ 已否决的候选不再重出（否则每轮空转）")

# 8f · 用采纳的候选重判（学习的**结果**）
if best:
    c_ok, src_ok = best
    v8f = j.evaluate(
        T2, "dev",
        observed=execute_task(Actor(), j, T2,
                              implementation=src_ok)["observation"])
    print("\n  ★★★ 学习结果: 采纳 %s" % c_ok.rule)
    print("     原实现判 %s → 修后判 %s" % (v8.success, v8f.success))
    LEARN_RESULT = ("learned_and_verified" if v8f.success
                    else "adopted_but_not_verified")
else:
    print("\n  ★ 无候选通过判分 ⇒ 记为**未学到**（不假装学会）")
    LEARN_RESULT = ("need_llm" if r8["need_llm"] else "no_valid_candidate")

print("\n" + "=" * 60)
print("★ 学习闭环结果: %s" % LEARN_RESULT)
print("=" * 60)
print("  生成器产出: %d 条候选 · 淘汰池 %d"
      % (r8["n"], len(gen2.rejected)))
print("  %s" % ("★★★ 从失败里学到了新东西（此前这是终点）"
               if LEARN_RESULT == "learned_and_verified"
               else "★ 本轮未学到 —— 但**显式**报告了原因"))


# ══════════════════════════════════════════════════════════
# ★★★★★ step 8g · **固化**（2606.09498 line 23 MergeAccepted）
#    R31 学到的东西此前**无法累积** —— 缺的就是这条通路
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("step 8g · 固化（把验证过的候选写进 RULES）")
print("=" * 60)
from dwc.organs.evolver import Mutator as _M

assert best is not None, "★ 没有验证通过的候选 ⇒ 不许固化（不假装学会）"
c_ok, src_ok = best
sig_key = _M.key_for(sig8)
print("  键 = %s" % sig_key)
print("  固化前 RULES 含该键: %s" % (sig_key in _M.RULES))

entry = {
    "component": "control_flow",
    "dimension": "D7",
    "target": LEARN_FN,
    "m": "loop_bound",
    "m_source": "rule",
    "patch": c_ok.patch,
    "rationale": ("R31/R32 固化: %s 由 judge 验证（%s → %s）· "
                  "grounding=%d 条 diff"
                  % (c_ok.rule, v8.success, v8f.success,
                     len(c_ok.grounding))),
}
# ★ R32: 给 flush 能力 ⇒ 固化时**落盘**（否则进程结束就丢）
tgt_rule = Target(getter=lambda: _M.RULES.get(sig_key),
                  setter=lambda v: _M.RULES.__setitem__(sig_key, v),
                  has_fn=lambda: sig_key in _M.RULES,
                  delete_fn=lambda: _M.RULES.pop(sig_key, None),
                  flush_fn=_M.persist_learned)
evi = {"success": v8f.success, "split": "dev", "task": T2}
res_l = ap.land_rule(tgt_rule, sig_key, entry, evi, _M.check_entry)
print("  ✓ 固化: readback_ok=%s" % res_l.readback_ok)
print("    reason = %s" % res_l.reason)
print("  固化后 RULES 含该键: %s" % (sig_key in _M.RULES))

# ★ 负面: 未验证的证据必须被拒（不许"顺手"固化）
try:
    ap.land_rule(tgt_rule, sig_key, entry,
                 {"success": False, "task": T2}, _M.check_entry)
    print("  ★ 未验证的证据居然通过了（闸②失效）")
except Exception as e:
    print("  ✓ 未验证证据被拒: %s" % str(e)[:56])

# ══════════════════════════════════════════════════════════
# step 8h · ★★★ 固化的**效果**: 下次同类失败直接查表命中
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("step 8h · 固化的效果（再次遭遇同一失败 ⇒ 直接命中）")
print("=" * 60)
d_again = ev.diagnose([dict(sig8)])
print("  再诊断: n_proposals=%d n_unmapped=%d"
      % (len(d_again["proposals"]), d_again["n_unmapped"]))
hit = bool(d_again["proposals"])
print("  %s" % ("★★★★★ 命中！不必再试错 —— R31 前这里是 unmapped"
               if hit else "★ 仍未命中（固化口径有问题）"))
if hit:
    p_after = d_again["proposals"][0]
    print("    target=%s patch=%r" % (p_after.target, p_after.patch))
    src_l = build_implementation(LEARN_FN, BUGGY2, p_after.patch)
    v_l = j.evaluate(
        T2, "dev",
        observed=execute_task(Actor(), j, T2,
                              implementation=src_l)["observation"])
    print("    用固化规则跑: success=%s" % v_l.success)
    assert v_l.success, "★ 固化的规则必须仍能修好（否则是坏规则）"

print("\n" + "=" * 60)
print("★ 学习→固化 全链: %s"
      % ("learned_and_verified → **landed**" if hit
         else "landed but not queryable"))
print("=" * 60)
print("  生成 %d 条 → 试错采纳 1 条 → 固化 1 条 → 再查表%s"
      % (r8["n"], "**命中**" if hit else "**未命中**"))
print("  淘汰池 %d（已否决不重试）· 可回滚（G4 能生能死）"
      % len(gen2.rejected))
# step 8i · ★★★★★ **跨进程**存活（2606.09498 line 23 的实质）
#   "MergeAccepted 合并进主干" ⇒ 合并的东西必须**跨进程还在**
#   ⇒⇒ 否则固化只是"本进程内有效" ⇒ 下次跑又要重学
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("step 8i · 跨进程存活（固化的成果会不会丢）")
print("=" * 60)
print("  land_rule reason: %s" % res_l.reason[-46:])
if os.path.exists(_M.LEARNED_PATH):
    _evd = json.load(open(_M.LEARNED_PATH, encoding="utf-8"))
    print("  落盘 learned 条目: %s" % list(_evd.get("learned") or {}))
else:
    print("  ★★ 落盘文件不存在 ⇒ flush 没生效")
    _evd = {}

# ★ spawn 一个**全新进程**查表（"跨进程"的唯一真验证）
_probe = ("import sys, json\n"
          "sys.path.insert(0, %r)\n"
          "from dwc.organs.evolver import Mutator, Evolver\n"
          "sig = json.loads(sys.argv[1])\n"
          "d = Evolver().diagnose([sig])\n"
          "print('RULES=%%d HIT=%%d' %% (len(Mutator.RULES), "
          "len(d['proposals'])))\n") % (os.path.join(ROOT, "src"))
_tmp = os.path.join(os.environ.get("TEMP", "."), "_e2e_probe.py")
open(_tmp, "w", encoding="utf-8").write(_probe)
_r = subprocess.run([sys.executable, _tmp, json.dumps(dict(sig8))],
                    capture_output=True, timeout=120)
_out = _r.stdout.decode("utf-8", "replace").strip()
print("  新进程: %s" % _out)
try:
    os.remove(_tmp)
except OSError:
    pass
cross_ok = _r.returncode == 0 and " HIT=1" in _out
print("  %s" % ("★★★★★ 跨进程**仍能查到** ⇒ 固化真的留存了"
                if cross_ok else "★ 跨进程丢规则（未落盘/未加载）"))
CROSS_OK = cross_ok

print("  applier stats: %s"
      % {k: v for k, v in ap.stats().items() if k.startswith("n_")})
print("  ★ 跨进程存活: %s" % ("✓（line 23 的实质）" if CROSS_OK else "✗"))
# ★★ 出口自清洁（与入口**双保险** —— 入口那份防"上次中断"，
#   出口这份防"本次异常在别处断" ⇒ 两处都做才稳）
print("\n  ── 出口自清洁（回滚固化 + 清落盘）──")
if sig_key in _M.RULES:
    ap.rollback("LAND:" + sig_key, tgt_rule)
    _M.persist_learned()
if os.path.exists(_M.LEARNED_PATH):
    left = json.load(open(_M.LEARNED_PATH, encoding="utf-8"))
    if not (left.get("learned") or {}):
        os.remove(_M.LEARNED_PATH)
    print("    ✓ 出口: 回滚 %s · 落盘剩 %d 条"
          % ("成功" if sig_key not in _M.RULES else "★失败",
             len(left.get("learned") or {})))
else:
    print("    ✓ 出口: 回滚 %s · 无落盘文件"
          % ("成功" if sig_key not in _M.RULES else "★失败"))

# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
# step 9 · ★★★★ **LLM 形态**（R34 · need_llm 从「只报」变「能跑」）
#   ★ 场景必须**确定性推不出**（否则 LLM 分支不触发 —— 我栽过）
#     · is_palindrome 不含 range ⇒ R1 全失效
#     · 不在 RULES 种子 3 条里 ⇒ 查表不命中
#   ★★ 结论**只认 source == "llm"** 的候选（不许把确定性算进来）
# ══════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("step 9 · LLM 形态（真端点 · 需配置）")
print("=" * 60)
from dwc.llm import LLMClient

_llm_client = LLMClient()
if not _llm_client.configured:
    # ★★ 不静默跳过 —— 明确报出**为什么**没测
    print("  ★ 未配置 LLM ⇒ 本段**未测**（rc=0 但这条边界保留）")
    print("    配置: config/llm.json 或 DWC_LLM_* 三件套")
    print("    自检: python scripts/probe_llm.py --dry")
    LLM_SEGMENT = "not_configured"
else:
    print("  端点: %s · 模型: %s" % (_llm_client._host_only(),
                                   _llm_client._model))
    _LFN = "is_palindrome"
    _LBUG = "def is_palindrome(s):\n    return s == s[::-1]"
    _LT = "code_fix_005"
    # 9a · 真判分
    _o9 = execute_task(Actor(), j, _LT, implementation=_LBUG)
    _v9 = j.evaluate(_LT, "dev", observed=_o9["observation"])
    _sig9 = _v9.failure_signature or {}
    print("  judge: success=%s c=%s q=%s"
          % (_v9.success, _sig9.get("c"), _sig9.get("q")))
    assert not _v9.success, "★ 前提: 带 bug 必须判 fail"
    # 9b · 确定性必须推不出（前提校验 —— 不通过就别下结论）
    _g0 = CandidateGenerator()
    _r0 = _g0.generate(_sig9, _v9.diffs, _LBUG, fn_name=_LFN)
    print("  确定性: n=%d need_llm=%s" % (_r0["n"], _r0["need_llm"]))
    assert _r0["n"] == 0, "★ 前提不成立（确定性已推出 ⇒ 测不到 LLM）"
    # 9c · 真 LLM
    _g9 = CandidateGenerator(llm=_llm_client)
    _r9 = _g9.generate(_sig9, _v9.diffs, _LBUG, fn_name=_LFN)
    _llm_only = [cd for cd in _r9["candidates"] if cd.source == "llm"]
    print("  真 LLM: n=%d source=%s （**仅认 llm 来源** n=%d）"
          % (_r9["n"], _r9.get("source"), len(_llm_only)))
    print("    m_hint=%r" % _r9.get("m_hint"))
    print("    账本: calls=%d ok=%d" % (_g9.n_llm_calls, _g9.n_llm_ok))
    # 9d · 判分
    _passed = []
    print("  ── 判分 ──")
    for _cd in _llm_only:
        try:
            _src = build_implementation(_LFN, _LBUG, _cd.patch)
        except Exception as _e:
            print("    构建失败: %s" % str(_e)[:50])
            continue
        _v = j.evaluate(_LT, "dev",
                        observed=execute_task(
                            Actor(), j, _LT,
                            implementation=_src)["observation"])
        print("    judge=%s  m=%r" % (_v.success, _cd.m[:44]))
        if _v.success:
            _passed.append(_cd)
    if _passed:
        print("  ★★★ 真 LLM 候选**通过判分** ⇒ prompt 验证完成")
        print("       m 由模型填 = 2609.06396 Eq.10 在真端点落地")
        LLM_SEGMENT = "passed"
    elif _llm_only:
        print("  ★ 真 LLM 给了 %d 条但**无一通过**（如实记，不算已验证）"
              % len(_llm_only))
        LLM_SEGMENT = "candidates_rejected"
    else:
        print("  ★ 真 LLM **未给可用候选**（source=%s）⇒ 未完成验证"
              % _r9.get("source"))
        LLM_SEGMENT = "no_candidates"
    print("  LLM_SEGMENT=%s" % LLM_SEGMENT)
