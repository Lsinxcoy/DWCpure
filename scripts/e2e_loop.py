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
