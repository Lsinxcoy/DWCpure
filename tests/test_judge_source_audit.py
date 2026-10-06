# -*- coding: utf-8 -*-
"""★★★★★ R39 · **判据单源审计**的自动化守卫（把一次性审计变成常驻测试）。

═══════════════════════════════════════════════════════════
 为什么要有这文件（R37 的教训）:
   我 R37 在**同一个判据**（`component ∈ 𝒦∪𝒦_meta`）上写了**五个来源**:
     prompt / 生成校验 / 固化 schema / 读取 Proposal / G8 门
   ⇒⇒ 每改一处、其余与它矛盾 —— 实测踩了 5 次才收敛
   ⇒ ⇒★ 而我 R38 做的审计是**手跑一次**（grep + 打印）——
     手跑的审计下一轮就忘了，同样的模式还会再犯
   ⇒ ⇒★ 所以: 把审计判据写成**测试**，让它每次跑 pytest 都查

 三类守卫（对应审计发现的三类风险）:
   A 多来源: 同一语义的判据不许有多种写法
   B 死值:   字面量比较不许用值域外的值
   C 同族表: 同概念的多张表键集必须一致（当前一致但可能漂）
═══════════════════════════════════════════════════════════
"""
from __future__ import annotations

import io
import os
import re
import sys

ROOT = os.path.join("E:", os.sep, "Divine Wisdom Core")
SRC = os.path.join(ROOT, "src", "dwc")
if os.path.join(ROOT, "src") not in sys.path:
    # ★ 照 test_llm_candidates 的既有模式: 插 `src`（不是 src/dwc）
    #   我第一版插了 src/dwc ⇒ `import dwc.*` 找不到 ⇒ 5 个测试 ModuleNotFound
    sys.path.insert(0, os.path.join(ROOT, "src"))


def _files():
    out = []
    for dp, dn, fns in os.walk(SRC):
        for fn in fns:
            if fn.endswith(".py"):
                out.append(os.path.join(dp, fn))
    return out


def _read(fp):
    return io.open(fp, encoding="utf-8", errors="replace").read()


def _truth_lines():
    """★ 真源行号: `layer_of` / `check_component` 两个函数的行区间。

    ★ R39 教训: A1 第一版没白名单 ⇒ 把**真源自己**报成多来源
      （layer_of 内部当然要 `in COMPONENT_VOCAB` —— 它就是判定处）
    """
    fp = os.path.join(SRC, "organs", "evolver.py")
    out, start = set(), None
    src = io.open(fp, encoding="utf-8", errors="replace").read()
    for i, l in enumerate(src.split("\n"), 1):
        if l.startswith("def layer_of") or l.startswith("def check_component"):
            start = i
        elif start and l and not l.startswith((" ", "\t")):
            start = None
        if start:
            out.add(i)
    return out


# ══════════════════════════════════════════════════════════
# A · 多来源: 语义判据的写法数
# ══════════════════════════════════════════════════════════

def test_a1_component_check_is_single_sourced():
    """★★★★★ A1: `component ∈ 词表` 只许走 `check_component`（真源=layer_of）。

    ★★★ R37 实测: 我在**五处**各写了一次:
      `in COMPONENT_VOCAB` / `in COMPONENT_VOCAB or in K_META` / …
      ⇒ 改一处其余矛盾（prompt 扩了校验没扩 ⇒ e2e 卡死）
    ⇒ ⇒★ 除**定义处**与 `check_component` 自身，别处不许再写
        「component in COMPONENT_VOCAB」这种**直接判词表**的表达式
    """
    offenders = []
    _truth = _truth_lines()
    for fp in _files():
        rel = os.path.relpath(fp, SRC)
        s = _read(fp)
        for ln, line in enumerate(s.split("\n"), 1):
            st = line.strip()
            if st.startswith(("#", "*", '"', "'")):
                continue
            # 允许: 定义本身 / 真源函数内部 / 注释引用
            if "COMPONENT_VOCAB" not in line:
                continue
            if "=" in line and re.search(r"COMPONENT_VOCAB\s*[:=]", line):
                continue                       # 定义
            # ★★ 真源白名单: `layer_of` / `check_component` 函数体内
            #   （R39 第一版没这个 ⇒ 把真源自己报成多来源）
            if rel.replace("\\", "/").endswith("organs/evolver.py") and ln in _truth:
                continue
            if re.search(r"\bin\s+COMPONENT_VOCAB", line):
                offenders.append((rel, ln, st[:84]))
    assert not offenders, (
        "★ A1 多来源: 直接写 `in COMPONENT_VOCAB` 的地方（应走 "
        "check_component/layer_of，否则 component 判据又会有多个来源）:\n"
        + "\n".join("  %s:%d %s" % o for o in offenders))


def test_a2_layer_check_goes_through_layer_of():
    """★★ A2: target_layer 的取值不许被**重写**（必须经 layer_of）。"""
    offenders = []
    for fp in _files():
        rel = os.path.relpath(fp, SRC)
        s = _read(fp)
        for ln, line in enumerate(s.split("\n"), 1):
            st = line.strip()
            if st.startswith(("#", "*", '"', "'")):
                continue
            # 硬编码层名赋值（不是对比、不是文档）
            if re.search(r'target_layer\s*=\s*["\'](assets|architecture)', line):
                offenders.append((rel, ln, st[:84]))
    assert not offenders, (
        "★ A2 多来源: target_layer 被硬编码（应由 layer_of/逐项表给）:\n"
        + "\n".join("  %s:%d %s" % o for o in offenders))


# ══════════════════════════════════════════════════════════
# B · 死值: 字面量比较必须落在值域内
# ══════════════════════════════════════════════════════════

def test_b1_no_dead_literal_in_known_domains():
    """★★★ B1: 已知字段的字面量比较不许用值域外的值（死代码/错值）。"""
    from dwc.organs.evolver import (COMPONENT_VOCAB, K_META, DIMENSIONS,
                                    PROPOSAL_STATES, LAYER_BY_ITEM)
    # stage 域（从源码取，避免跨模块 import 因果链）
    ca = _read(os.path.join(SRC, "foundation", "causal_chain.py"))
    m = re.search(r"STAGES\s*=\s*\(([^)]*)\)", ca)
    stages = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()

    domains = {
        "stage": stages,
        "component": set(COMPONENT_VOCAB) | set(K_META),
        "dimension": set(DIMENSIONS),
        "state": set(PROPOSAL_STATES),
        "target_layer": set(LAYER_BY_ITEM.values()),
    }
    dead = []
    for fp in _files():
        rel = os.path.relpath(fp, SRC)
        s = _read(fp)
        for ln, line in enumerate(s.split("\n"), 1):
            st = line.strip()
            if st.startswith(("#", "*", '"', "'", "print", "raise", "return")):
                continue
            for fld, dom in domains.items():
                if not dom:
                    continue
                for mm in re.finditer(
                        r"\b%s\s*(==|!=)\s*\"(\w+)\"" % fld, line):
                    lit = mm.group(2)
                    if lit not in dom:
                        dead.append((rel, ln, "%s %s %r" % (fld, mm.group(1), lit)))
    assert not dead, (
        "★ B1 死值（比较了值域外的值 —— 不是错值就是死代码）:\n"
        + "\n".join("  %s:%d %s" % d for d in dead))


# ══════════════════════════════════════════════════════════
# C · 同族表: 键集必须一致（当前一致但可能漂）
# ══════════════════════════════════════════════════════════

def test_c1_stage_tables_share_one_keyset():
    """★★★ C1: stage 的三张表键集必须一致（改一张漏两张 = 静默漂）。"""
    ca = _read(os.path.join(SRC, "foundation", "causal_chain.py"))
    wi = _read(os.path.join(SRC, "foundation", "wiring.py"))
    m = re.search(r"STAGES\s*=\s*\(([^)]*)\)", ca)
    stages = set(re.findall(r'"(\w+)"', m.group(1))) if m else set()
    # ★★ R39: 我这个正则**犯了两次**同一错 —— `[:=]` 吃掉唯一的 `=`
    #   然后又要求一个 `=` ⇒ 永不匹配（STAGES 那次也是）
    #   ⇒ ⇒★ 修: 注解是**可选**的 `(?::[^=]+)?`
    m2 = re.search(r"STAGE_ID_COLUMN\s*(?::[^=]+)?=\s*\{(.*?)\n\s*\}", ca, re.S)
    id_col = set(re.findall(r'"(\w+)"\s*:', m2.group(1))) if m2 else set()
    m3 = re.search(r"STAGE_TO_LAYERS\s*(?::[^=]+)?=\s*\{(.*?)\n\s*\}", wi, re.S)
    s2l = set(re.findall(r'"(\w+)"\s*:', m3.group(1))) if m3 else set()

    assert stages, "★ STAGES 解析失败（正则或结构变了）"
    assert stages == id_col, (
        "★ C1: STAGES %s ≠ STAGE_ID_COLUMN %s ⇒ 改一张漏一张" %
        (sorted(stages), sorted(id_col)))
    assert stages == s2l, (
        "★ C1: STAGES %s ≠ STAGE_TO_LAYERS %s ⇒ 改一张漏一张" %
        (sorted(stages), sorted(s2l)))


def test_c2_layer_tables_agree():
    """★★★ C2: LAYER_BY_ITEM 与反推的 LAYER_BY_GROUP 不许各说各话。"""
    from dwc.organs.evolver import LAYER_BY_ITEM, LAYER_BY_GROUP, layer_of
    for lay, comps in LAYER_BY_GROUP.items():
        for c in comps:
            assert LAYER_BY_ITEM.get(c) == lay, \
                "★ C2: LAYER_BY_GROUP[%s] 含 %s，但逐项表说 %s" % (
                    lay, c, LAYER_BY_ITEM.get(c))
            assert layer_of(c) == lay
    # 反向: 每个逐项项都在某组里
    grouped = set().union(*[set(v) for v in LAYER_BY_GROUP.values()])
    missing = set(LAYER_BY_ITEM) - grouped
    assert not missing, "★ C2: 这些项不在任何 LAYER_BY_GROUP: %s" % missing


def test_c3_rule_entry_fields_cover_every_constructed_entry():
    """★★ C3: 固化字段与 Candidate 字段**双向**覆盖。

    ★ R35/R37 各踩一次「加字段没同步构造」（target / target_layer）
      ⇒⇒ 那是 C 类风险的**后果**（多来源 + 无覆盖检查）

    ★★ R39 破坏性验证抓到我第一版是**弱版本**:
      只查 `RULE_ENTRY_FIELDS - cand_fields`（schema 项是否有候选字段）
      ⇒⇒ 破坏方式是**从 schema 减字段**（删 target_layer）
        ⇒ `need` 变小 ⇒ `lack` 仍空 ⇒ **不红**（守卫没守住）
      ⇒ ⇒★ 真正要查的是**反向**: 候选侧的必填字段 schema 必须校验
        （否则「加了字段但 schema 不查」—— R37 那次的原形）
    """
    from dwc.organs.evolver import Mutator
    from dwc.organs.candidates import Candidate
    import dataclasses
    cand_fields = {f.name for f in dataclasses.fields(Candidate)}
    need = set(Mutator.RULE_ENTRY_FIELDS)

    # 方向 1: schema 项必须都有候选侧来源（rationale 由组装方补）
    lack = need - cand_fields - {"rationale"}
    assert not lack, (
        "★ C3: RULE_ENTRY_FIELDS 里 %s 没有对应 Candidate 字段 "
        "⇒ 固化时必然靠手填（R35/R37 踩过两次）" % sorted(lack))

    # ★★★ 方向 2（R39 补）: 必填字段**不许被 schema 摘掉**
    must_check = {"component", "dimension", "target_layer", "target"}
    missing = must_check - need
    assert not missing, (
        "★ C3: 必填字段 %s **不在 schema 里** ⇒ 固化不校验它"
        "（= 加了字段不查 —— 破坏性验证抓不到）" % sorted(missing))

# ══════════════════════════════════════════════════════════
# ★★★★★ 文档结构守卫（R40 事故的根因修复）
# ══════════════════════════════════════════════════════════

#: ★ 关键设计文档必须保留的章节标题（R40 我吃掉过 §五 ⇒ 锁住）
_KEY_DOC = os.path.join(ROOT, "docs", "COMPONENT_VOCABULARY.md")
_REQUIRED_SECTIONS = (
    "## 一、", "## 二、", "## 三、", "## 四、",
    "## 四·五", "## 四·六",              # R40/R42 补记（我加的）
    "## 五、可机械检查的判据",              # ★ R40 被吃掉的那节
    "## 六、诚实边界", "## 七、", "## 八、",
)
#: ★ K 判据编号必须齐全（§五 的内容锚点）
_REQUIRED_K = tuple("K%d ·" % k for k in range(1, 7))


def test_docs_structure_intact_no_section_eaten():
    """★★★★★ 文档**不许丢章节** —— R40 事故的直接守卫。

    ★★ 事故经过（我干的）:
      往文档里插新节时写成 `replace(旧标题, 新节)`，而新节**不含旧标题**
      ⇒⇒ 「## 五、可机械检查的判据（K1–K6）」**整节被替换掉**
      ⇒ ⇒★ 也就是说: 我以为在"追加"，实际在"**吃掉**"（G5 没抓到）
    ★★ 根因: 我 R39 的审计守卫只扫 `src/`，**不查 docs 结构**
    ⇒ ⇒★ 所以这条守卫必须查: ① 章节序列 ② K1–K6 内容锚点
    """
    assert os.path.exists(_KEY_DOC), "★ 关键设计文档不见了: %s" % _KEY_DOC
    s = io.open(_KEY_DOC, encoding="utf-8", errors="replace").read()
    # ★★★ R42 抓到我第一版是**子串匹配** ⇒ 假绿:
    #   散文里引用了标题（如 R42 节 ⑤ 那句「## 五、被吃掉」）就满足 `in`
    #   ⇒ 真标题被删了也测不到
    #   ⇒ ⇒★ 改**行首标题匹配**（R37「断言必须精确到来源」同族第 2 次）
    lines = s.split("\n")
    missing = [h for h in _REQUIRED_SECTIONS
               if not any(ln.startswith(h) for ln in lines)]
    assert not missing, (
        "★★★ 文档丢**标题行**（R40 那种事故又发生了）: 缺 %s" % missing)
    # K 判据: 也是行首（`K1 · …` 起头的行，不是散文里的提法）
    k_missing = [k for k in _REQUIRED_K
                 if not any(ln.startswith(k) for ln in lines)]
    assert not k_missing, (
        "★★★ §五 的 K 判据丢**内容行**: 缺 %s（K1–K6 是 gate 的依据）"
        % k_missing)


def test_docs_insertion_never_replaces_section_title():
    """★★ 我 R40 用的 `replace(标题, 新节)` 模式必须**不被**再用。

    ★ 这条不查文件，查的是**我自己的工具模式**:
      若新节里**丢了**被替换的标题 ⇒ 那就是吃章节
    ⇒ ⇒★ 实现: 模拟 R40 的写法, 断言它**会**导致丢节（作为回归警示）
      —— 也就是说这条测试**证明**那个模式是危险的，从而禁用它
    """
    base = "## 甲\n内容\n\n## 乙\n内容\n"
    # R40 的危险写法: replace(标题, 新节) 而新节不含标题
    new_section = "## 四·五 新节\n内容\n\n"
    broken = base.replace("## 乙", new_section)
    assert "## 乙" not in broken, "（前提）这个模式确实会吃掉标题"
    # ★ 正确写法: 新节**包含**原标题
    safe = base.replace("## 乙", new_section + "## 乙")
    assert "## 乙" in safe, "★ 正确写法必须把原标题放回"

def test_heading_guard_not_fooled_by_prose_quote():
    """★★★★ R42 假绿根因: **散文引用不能算标题**。

    ★ 事故: 我第一版守卫用 `h in s`（子串匹配）
      而 R42 节里我自己写了句「## 五、可机械检查的判据…被吃掉」
      ⇒⇒ 子串**命中** ⇒ 真标题被删了也测不到 = **假绿**
    ⇒ ⇒★ 改行首匹配后, 这条测试锁住那个差异（同族第 2 次: 断言要
      精确到**来源** —— R37 的 component 判据 5 来源是第 1 次）
    """
    # ① 只有散文引用（含标题全文）⇒ **没有**标题行
    prose = "我说过\n「## 五、可机械检查的判据（gate.py 候选，K1–K6）」被吃了\n"
    lines = prose.split("\n")
    # ★ 子串匹配会**误判为存在**（这就是假绿）
    assert "## 五、可机械检查的判据" in prose, "（前提）子串会命中"
    # ★ 行首匹配才对: 不存在
    assert not any(ln.startswith("## 五、可机械检查的判据")
                   for ln in lines), \
        "★ 散文引用不算标题行（否则守卫被自己的说明文字骗过）"
    # ② 真标题行 ⇒ 存在
    real = "正文\n## 五、可机械检查的判据（gate.py 候选，K1–K6）\nK1 …"
    assert any(ln.startswith("## 五、可机械检查的判据")
               for ln in real.split("\n"))
