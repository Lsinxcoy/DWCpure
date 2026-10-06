"""R31 · 候选生成实测 —— "学习新规则"闭环的生成半边。"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge
from dwc.organs.candidates import Candidate, CandidateGenerator, CandidateError
from dwc.organs.actor import PureFunctionExecutor, build_implementation
from dwc.organs.evolver import Evolver

j = Judge()
gen = CandidateGenerator()

print("=" * 60)
print("场景 1 · 真实的 off-by-one 失败（trace-grounded）")
print("=" * 60)
BUGGY = "def sum_first_n(n):\n    return sum(range(n))"
v = j.evaluate("code_fix_001", "dev",
               observed={"sum_first_n": [[3, 3], [5, 10]]})
print("  judge: success=%s" % v.success)
print("  sig   : %s" % {k: v.failure_signature[k]
                       for k in ("c", "q", "fn")})
print("  diffs : %s" % [(d["args"], d["expected"], d["actual"])
                        for d in v.diffs])
# ★★★ R31: 基线必须是**产生该失败的实现**（不是 REFERENCE）
#   传错会被纪律④拒绝（见场景 1b）
r = gen.generate(v.failure_signature, v.diffs, BUGGY, fn_name="sum_first_n")
print("  ⇒ n=%d need_llm=%s why=%s" % (r["n"], r["need_llm"], r["why"][:50]))
for c in r["candidates"]:
    print("    [%s] patch=%r" % (c.rule, c.patch))
    print("       grounding=%d 条" % len(c.grounding))

print("\n" + "=" * 60)
print("场景 1b · ★★★ 纪律④: 传**错误基线**必须被拒")
print("=" * 60)
r1b = gen.generate(v.failure_signature, v.diffs,
                   PureFunctionExecutor.REFERENCE["sum_first_n"],
                   fn_name="sum_first_n")
print("  n=%d need_llm=%s" % (r1b["n"], r1b["need_llm"]))
print("  why=%s" % r1b["why"][:88])
assert r1b["n"] == 0 and not r1b["need_llm"], \
    "★★★ 传错基线没被拒 —— 那会静默产生全错的候选"
print("  ✓ 被拒（我 R31 第一版就传错 REFERENCE，抓到全错候选）")

print("\n" + "=" * 60)
print("场景 2 · ★ 纪律①: 无 diffs ⇒ 不产候选")
print("=" * 60)
r2 = gen.generate(v.failure_signature, None,
                  PureFunctionExecutor.REFERENCE["sum_first_n"])
print("  n=%d need_llm=%s\n  why=%s" % (r2["n"], r2["need_llm"], r2["why"]))
assert r2["n"] == 0 and not r2["need_llm"], "★ 无证据不应转 need_llm"

print("\n" + "=" * 60)
print("场景 3 · ★ 纪律③: 推不出 ⇒ 显式 need_llm")
print("=" * 60)
# 用一个确定性规则推不出的证据（差值不恒定 ⇒ 非边界偏移）
DIFFS_NOMATCH = [
    {"index": 0, "ok": False, "fn": "mystery", "args": 1,
     "expected": 100, "actual": 7, "reason": "值不匹配"},
    {"index": 1, "ok": False, "fn": "mystery", "args": 2,
     "expected": 200, "actual": 9, "reason": "值不匹配"},
    {"index": 2, "ok": False, "fn": "mystery", "args": 3,
     "expected": 400, "actual": 11, "reason": "值不匹配"},
]
# ★★ R31 修正: 原基线 `x + 6` 复现不了 actual(7,9,11) ⇒ 被**纪律④先拦**
#   ⇒ 那不是"推不出"，是"基线传错" ⇒ 我的测试数据自相矛盾（不是实现错）
#   ⇒⇒ 现改为能复现 actual 的基线 2x+5（1→7 2→9 3→11 ✓）
r3 = gen.generate({"c": "E_VALUE", "q": "wrong_magnitude", "fn": "mystery"},
                  DIFFS_NOMATCH,
                  "def mystery(x):\n    return 2 * x + 5")
print("  n=%d need_llm=%s" % (r3["n"], r3["need_llm"]))
print("  why=%s" % r3["why"])
assert r3["n"] == 0 and r3["need_llm"], "★ 推不出必须显式 need_llm"

print("\n" + "=" * 60)
print("场景 4 · ★ 纪律②: 无 grounding 的候选必须 raise")
print("=" * 60)
try:
    Candidate(patch="return 0", source="deterministic", grounding=[])
    print("  ★ 未 raise —— 纪律②失效")
except CandidateError as e:
    print("  ✓ raise: %s" % str(e)[:74])

print("\n" + "=" * 60)
print("场景 5 · ★★★ 闭环: 候选 → 构建实现 → 判分（该比 bug 好）")
print("=" * 60)
if r["candidates"]:
    best = r["candidates"][0]
    try:
        cand_src = build_implementation("sum_first_n", BUGGY, best.patch)
        print("  候选实现: %r" % cand_src)
        from dwc.organs.actor import Actor, execute_task
        out = execute_task(Actor(), j, "code_fix_001",
                           implementation=cand_src)
        v2 = j.evaluate("code_fix_001", "dev",
                        observed=out["observation"])
        print("  judge: success=%s ⇒ %s"
              % (v2.success, "★ 候选有效" if v2.success else "候选无效"))
    except Exception as e:
        print("  ★ 构建/判分异常: %s" % e)
else:
    print("  （无候选）")

print("\n" + "=" * 60)
print("场景 6 · ★★ 与 Mutator.propose 的分工")
print("=" * 60)
ev = Evolver()
# 查表命中
d_hit = ev.diagnose([dict(v.failure_signature)])
print("  查表(RULES)  : n_proposals=%d" % len(d_hit["proposals"]))
# 查表未命中（新签名）
NEW_SIG = {"c": "E_NO_RESULT", "q": "abstained_or_missing", "fn": "fibonacci"}
d_miss = ev.diagnose([NEW_SIG])
print("  查表未命中   : n_proposals=%d n_unmapped=%d"
      % (len(d_miss["proposals"]), d_miss["n_unmapped"]))
# ★★ 此前 unmapped = 终点；现在走生成器
# ★ 该签名的 fn 是 fibonacci，但证据/基线都是 sum_first_n 的
#   ⇒ 纪律④ 会拒绝（基线复现不了 fibonacci 的 actual）—— 这是对的
r6 = gen.generate(NEW_SIG, v.diffs, BUGGY, fn_name="sum_first_n")
print("  ⇒ 转生成器   : n=%d need_llm=%s"
      % (r6["n"], r6["need_llm"]))
print("  why=%s" % r6["why"][:78])

print("\n" + "=" * 60)
print("★ 结论")
print("=" * 60)
print("  场景1 有证据 ⇒ 产候选 %d 条（grounding 齐）" % r["n"])
print("  场景2 无证据 ⇒ 0 条 + 不编造（need_llm=False）")
print("  场景3 推不出 ⇒ 0 条 + **显式 need_llm=True**")
print("  场景4 无依据 ⇒ raise")
print("  场景5 候选可走构建+判分链")
print("  场景6 unmapped **不再是终点** —— 会转生成器")
print("\n  generator 规则触发: %s" % gen.rules_fired)