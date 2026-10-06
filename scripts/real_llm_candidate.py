# -*- coding: utf-8 -*-
"""R34 · 真端点候选生成实测 —— 补『prompt 未经真实模型验证』这条边界。

★★★ 我第一次写这个脚本时**撒了谎**（幻影声明，自己抓到）:
  我 print「真 LLM 候选通过判分」，但实际:
    source=deterministic · n_calls=0 · 4 条全是 R1 规则
  ⇒ 确定性先推出来了 ⇒ **LLM 分支根本没被触发**
  ⇒ 而结论句是**无条件** print 的 ⇒ 结论基于了错的东西
  ⇒⇒ ⇒★★ 那正是 G5 声称门与原则 12（名字与实现对齐）要防的
  ⇒ ⇒★ 修: ①场景必须**保证**确定性推不出 ②结论只认 source=="llm"

场景选择（逐条核过）:
  · `is_palindrome` — REFERENCE 用 `s.lower()`，带 bug 实现忘 lower
    ⇒ `is_palindrome('Racecar')` 判 False，期望 True ⇒ **真判 fail**
  · 不含 `range(` ⇒ R1 的唯一规则全失效 ⇒ 确定性**必然推不出**
  · 不在 RULES 种子（那 3 条是 sum_first_n/average/factorial）
    ⇒ 查表不命中 ⇒ 走 generate ⇒ 才可能进 LLM 分支
"""
import os
import sys

ROOT = os.path.join("E:", os.sep, "Divine Wisdom Core")
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import LLMClient
from dwc.organs.candidates import CandidateGenerator
from dwc.organs.judge import Judge
from dwc.organs.actor import Actor, execute_task, build_implementation

TASK = "code_fix_005"
FN = "is_palindrome"
# ★ 真 bug: 忘了 .lower() ⇒ 忽略大小写失效（而任务明说"忽略大小写"）
BUGGY = "def is_palindrome(s):\n    return s == s[::-1]"

print("=" * 64)
print("R34 · 真端点候选生成（MiMo-V2.6-Flash）")
print("=" * 64)

c = LLMClient()
assert c.configured, "★ 未配置（先跑 scripts/probe_llm.py）"
print("  端点: %s · 模型: %s" % (c._host_only(), c._model))
print("  场景: %s / %s（忘 .lower()）" % (TASK, FN))

j = Judge()
out = execute_task(Actor(), j, TASK, implementation=BUGGY)
v = j.evaluate(TASK, "dev", observed=out["observation"])
sig = v.failure_signature or {}
print("  judge: success=%s · c=%s q=%s fn=%s"
      % (v.success, sig.get("c"), sig.get("q"), sig.get("fn")))
assert not v.success, "★ 前提: 带 bug 实现必须判 fail"
assert "range(" not in BUGGY, "★ 前提: 源码不含 range（否则 R1 会先中）"

# ── ① 确定性（必须推不出 —— 这是前提，先验证它）──
gen0 = CandidateGenerator()
r0 = gen0.generate(sig, v.diffs, BUGGY, fn_name=FN)
print("\n  ① 确定性: n=%d need_llm=%s" % (r0["n"], r0["need_llm"]))
print("     why=%s" % r0["why"][:110])
assert r0["n"] == 0, ("★★ 前提不成立: 确定性推出了 %d 条 ⇒ "
                      "那样测不到 LLM 分支（我上次就栽在这）" % r0["n"])
assert r0["need_llm"] is True

# ── ② 真 LLM ──
gen = CandidateGenerator(llm=c)
print("\n  ② 真 LLM（发真实请求…）")
r = gen.generate(sig, v.diffs, BUGGY, fn_name=FN)
print("     n=%d need_llm=%s source=%s" % (r["n"], r["need_llm"], r.get("source")))
print("     why=%s" % str(r.get("why"))[:180])
print("     m_hint=%r" % r.get("m_hint"))
print("     账本: n_calls=%d n_ok=%d n_fail=%d"
      % (gen.n_llm_calls, gen.n_llm_ok, getattr(gen, "n_llm_fail", 0)))

# ★★★ 关键: **只认 source == "llm"** 的候选（不许把确定性的算进来）
llm_cands = [cd for cd in r["candidates"] if cd.source == "llm"]
for cd in llm_cands:
    print("       [llm] rule=%s m=%r m_source=%s grounding=%d"
          % (cd.rule, cd.m, cd.m_source, len(cd.grounding)))
    print("        patch=%r" % cd.patch[:130])
assert gen.n_llm_calls >= 1, "★★ 必须真发过 LLM 请求"

# ── ③ 判分（真值源）──
passed = []
print("\n  ③ 判分（judge 是真值源，不是模型自己说）")
for cd in llm_cands:
    try:
        src = build_implementation(FN, BUGGY, cd.patch)
    except Exception as e:
        print("       构建失败: %s" % str(e)[:60])
        continue
    o2 = execute_task(Actor(), j, TASK, implementation=src)
    vv = j.evaluate(TASK, "dev", observed=o2["observation"])
    print("       judge=%s  %s  m=%r" % (vv.success, cd.rule, cd.m))
    if vv.success:
        passed.append(cd)

print("\n" + "=" * 64)
if passed:
    print("★ 结果: **真 LLM 候选通过判分** —— rule=%s m=%r"
          % (passed[0].rule, passed[0].m))
    print("  ⇒ 补上 R34 诚实边界『prompt 未经真实模型验证』")
    print("  ⇒ m 由模型填 = 2609.06396 Eq.10 分工在**真端点**上落地")
elif llm_cands:
    print("★ 结果: 真 LLM 给了 %d 条，但**无一通过判分**" % len(llm_cands))
    print("  ⇒ 如实记: 模型给了候选但没修好（不是『已验证』）")
else:
    print("★ 结果: 真 LLM **未给出可用候选**（source=%s）" % r.get("source"))
    print("  ⇒ 如实记: 未完成 prompt 验证（cause 见上）")
print("=" * 64)
sys.exit(0 if passed else 2)
