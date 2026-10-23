# -*- coding: utf-8 -*-
"""gate.py 的 n_a（无可检对象）契约测试。

★★★ 这份测试的由来（2026-10-05 · R10）
    R9 实测发现: src/dwc 为空时, G1/G2/G3/G4/G7 的循环体根本不执行,
    violations 恒空 ⇒ 报 pass=True 而输出是 `[✓ PASS]`
    ⇒ 【什么都能通过】与【什么都没检到】在输出里完全无法区分。
    R10 引入第三态 n_a。本测试把那个修复**固化**下来。

★ 为什么必须固化（判据 P7 / I6 / S2 的同款纪律）:
    今天这个修复是手工改 gate.py 得到的, 若不写测试,
    下一次有人"简化"掉 n_a 分支, 没有任何东西会变红。
    ⇒ 这正是判据 I6「每个检查器有阳性测试」要求的东西。

★ 测什么（按"意图"而非"实现"）:
    ① 门必须能表达"我没检过任何东西"      → status == "n_a"
    ② n_a 不许被算作通过                   → rc != 0
    ③ 门在**真有违规**时必须报红            → 不能被改成永远不绿
    ④ 有真实副作用时不该误报                → 不能变成噪声门
    ⑤ 有真实代码时不该误报 n_a             ← 2026-10-05 修订新增

★★★ 2026-10-05 修订（这份测试被自己的失败教了一次）
    初版**直接假定** src/dwc 是空的 ⇒ 断言 5 道门报 n_a。
    当第一份实现代码（capability_groups）落地当天，这三项立刻变红。
    ⇒ ★★ 错在: 我把**当时的状态**当成了**契约**（M2 代理指标）
    ⇒ ⇒ 契约是「**没有可检对象时**必须报 n_a」，
      所以测试必须自己制造那个条件（把 src/dwc 暂存起来），
      而不是假设它成立。
    ⇒ ⇒ 并因此补上第 ⑤ 项: 有真实代码时不该仍报 n_a
      （初版只测了空的一半，无法区分"门记得自己有对象"与"门还在报 n_a"）
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, "scripts", "gate.py")
SRC = os.path.join(ROOT, "src", "dwc")


# ── gate.py 不是包, 直接按路径加载 ──
def load_gate():
    spec = importlib.util.spec_from_file_location("dwc_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_gate(*args):
    r = subprocess.run([sys.executable, "scripts/gate.py"] + list(args),
                       capture_output=True, timeout=120, cwd=ROOT)
    return r.returncode, r.stdout.decode("utf-8", "replace"), \
        r.stderr.decode("utf-8", "replace")


@contextlib.contextmanager
def src_dwc(files=None):
    """★ 临时替换 src/dwc 的内容。必存后必还原, 异常路径也还原。

    ★ 为什么用「暂存」而不是「删」: src/dwc 里已有真实实现代码
      （capability_groups.py），测试绝不能毁掉它。
    """
    stash = SRC + "__stashed"
    had = os.path.isdir(SRC)
    if had:
        if os.path.isdir(stash):
            shutil.rmtree(stash)
        shutil.move(SRC, stash)
    try:
        if files is not None:
            for name, body in files.items():
                p = os.path.join(SRC, name)
                os.makedirs(os.path.dirname(p), exist_ok=True)
                io.open(p, "w", encoding="utf-8").write(body)
        yield
    finally:
        shutil.rmtree(SRC, ignore_errors=True)
        if had:
            if os.path.isdir(stash):
                shutil.move(stash, SRC)
            else:
                raise AssertionError("★ 暂存目录不见了 — 真实代码可能丢失")


def test_src_stash_fixture_works():
    """意图: 先证明 fixture 自身有效（藏起来能还原）。"""
    assert os.path.isdir(SRC), "本测试假定 src/dwc 存在"
    with src_dwc():
        assert not os.path.isdir(SRC), "fixture 应把 src/dwc 藏起来"
    assert os.path.isdir(SRC), "fixture 必须还原 src/dwc"
    assert os.listdir(SRC), "还原后不应为空"


class _SrcFixture:
    """写文件的 fixture（保留给后文用）。"""

    def __init__(self, files: dict):
        self.files = files

    def __enter__(self):
        os.makedirs(SRC, exist_ok=True)
        for name, body in self.files.items():
            p = os.path.join(SRC, name)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            io.open(p, "w", encoding="utf-8").write(body)
        return self

    def __exit__(self, *exc):
        # ★★★ 2026-10-05 修正: 原实现是 shutil.rmtree(SRC)
        #   ⇒ 那会在测试跑完后**删掉 src/dwc 里的真实实现代码**
        #   ⇒ 实际发生过: capability_groups.py 与两个 __init__.py 被删光
        #   ⇒ 这里只删自己造的文件，绝不动别人的
        for name in self.files:
            p = os.path.join(SRC, name)
            if os.path.exists(p):
                os.remove(p)
        return False


# ══════════════════════════════════════════════════════════
# ① 门必须能表达"我没检过任何东西"
# ══════════════════════════════════════════════════════════

def test_empty_src_yields_n_a_not_pass():
    """★ 意图: 空的 src/dwc 下, 扫源码的门必须报 n_a, 不是 pass。"""
    with src_dwc():                       # ★ 自己制造"空"这个条件
        rc, out, _ = run_gate()
    assert out.count("[○ N/A ]") == 5, \
        "应有 5 道门报 n_a（%s）\n实际输出:\n%s" % (5, out)
    assert "无可检对象" in out, "输出必须写明'无可检对象'"


def test_status_field_present_in_json():
    """★ 意图: --json 必须带 status, 否则机器读到的是缺失字段。"""
    with src_dwc():
        rc, out, _ = run_gate("--json")
    res = json.loads(out)
    # ★★★ R37: 原断言 `len(res) == 7` 是**硬编码门数**，
    #   我加 G8 ⇒ 它红了。但测试的**意图**是
    #   「机器读到的每道门都必须有 status」，不是「恰好 7 道」
    #   ⇒⇒ ⇒★ 断言测的不是意图（我 memory 里记着的教训）
    #   ⇒ ⇒★ 改: 下界 + 逐门查 status（加门/删门都不该红）
    assert len(res) >= 7, "应至少 7 道门（实际 %d）" % len(res)
    missing = [r.get("gate") for r in res if "status" not in r]
    assert not missing, "★ 这些门缺 status（机器读不到状态）: %s" % missing
    for r in res:
        assert "status" in r, "G%d 缺 status 字段" % r["gate"]
    need = {1, 2, 3, 4, 7}
    for r in res:
        if r["gate"] in need:
            assert r["status"] == "n_a", \
                "G%d 应为 n_a, 实为 %r" % (r["gate"], r["status"])
        else:
            assert r["status"] in ("pass", "fail"), \
                "G%d 状态非法: %r" % (r["gate"], r["status"])


def test_n_a_makes_exit_code_nonzero():
    """★★ 意图: "没检查到任何东西"不许被当成"通过" ⇒ rc 必须非 0。"""
    with src_dwc():
        rc, out, _ = run_gate()
    assert rc != 0, \
        "空 src/dwc 下 rc 必须非 0（因为 5 道门未被检验）\n实际输出:\n%s" % out


def test_summary_does_not_say_all_pass():
    """★★ 意图: 总结行不许写"全部通过"—— 那正是原来的假象。"""
    with src_dwc():
        rc, out, _ = run_gate()
    assert "总结: 全部通过" not in out, \
        "总结行不许写'全部通过'\n实际:\n%s" % out
    assert "无可检对象" in out, "总结行必须点明有门未被检验"


# ══════════════════════════════════════════════════════════
# ⑤ ★ 有真实代码时不该误报 n_a（2026-10-05 新增）
# ══════════════════════════════════════════════════════════

def test_real_code_does_not_yield_na():
    """★★ 意图: src/dwc 有文件时, 那五道门**不该**报 n_a。

    ★ 这是初版漏掉的一半: 初版只测"空时报 n_a"，
      于是无法区分「门记得自己有对象」与「门还在报 n_a」。
      ⇒ 第一份实现代码落地当天，这项立刻暴露了那个洞。
    """
    with src_dwc({"mod.py": '"""DWC-MEM 定位声明。"""\n\nX = 1\n'}):
        rc, out, _ = run_gate()
    assert "[○ N/A ]" not in out, \
        "有真实代码时不该报 n_a\n实际:\n%s" % out
    assert ("[✓ PASS]" in out or "[✗ FAIL]" in out), \
        "有代码时必须是 pass 或 fail\n实际:\n%s" % out


# ══════════════════════════════════════════════════════════
# ③ 真有违规时必须报红（防止被改成永远不绿）
# ══════════════════════════════════════════════════════════

VIOLATIONS = {
    # G1: 缺 DWC-MEM / DWC-AUTO 定位声明
    "organs/bad_locality.py": '"""没写定位声明。"""\n\n\ndef f():\n    return 1\n',
    # G2: 探针恒 True（母巢 P0-4）
    "bad_probe.py": ('"""DWC-AUTO 定位声明在。"""\n\n\n'
                     'def check_alive():\n    return True\n'),
    # G2: 评分函数恒 0.7（母巢 P0-5）
    "bad_score.py": ('"""DWC-AUTO 定位声明在。"""\n\n\n'
                     'def score_task(x):\n    return 0.7\n'),
    # G3: 六层活性字段全缺
    "bad_layers.py": '"""DWC-AUTO 定位声明在。"""\n\n\nX = 1\n',
    # G7: except: pass 且无计数/日志
    "bad_silent.py": ('"""DWC-MEM 定位声明在。"""\n\n\n'
                      'def load():\n    try:\n        x = 1\n'
                      '    except ValueError:\n        pass\n'),
    # G7: 伪装成功 —— 无任何副作用
    "bad_fake_ok.py": ('"""DWC-MEM 定位声明在。"""\n\n\n'
                       'def save():\n    return {"ok": True}\n'),
}


def test_real_violations_are_detected():
    """★★ 意图: 放了真违规, 门必须报红 —— 不能为了 n_a 而变成永远不绿。

    ★★ 2026-10-05 R14 修正: 原断言里含 "缺活性层"，那依赖 G3 强制要求六层。
      而 R14 已把六层改成"未采用即 not_adopted"，不再无条件强制
      （QUALITY_GATE.md §门3:「六层模型是候选，不是必然」）
      ⇒⇒ 六层的强制性改由 test_six_layer_* 三项专门测，不再混在这里。
    """
    with _SrcFixture(VIOLATIONS):
        rc, out, _ = run_gate()
    assert rc != 0, "有 5 类违规时 rc 必须非 0\n实际:\n%s" % out
    assert out.count("[○ N/A ]") == 0, \
        "有文件时不该再报 n_a\n实际:\n%s" % out
    for rule in ("缺定位声明", "探针恒 True", "P0-5",
                 "静默 except", "疑似伪装成功"):
        assert rule in out, "未检出规则 %r\n实际:\n%s" % (rule, out)


# ══════════════════════════════════════════════════════════
# ★★★ R14 · 六层模型的采纳状态（第四态 not_adopted）
# ══════════════════════════════════════════════════════════

DOC = '"""DWC-MEM 定位声明。"""\n\n'
LAYERS = ("present", "registered", "called", "succeeded",
          "produced_effect", "feedback_closed")


def test_six_layer_not_adopted_is_its_own_state():
    """★★ 意图: 无人声明六层时, 状态是 not_adopted —— 不是 pass, 也不是 fail。

    ★ 为什么这不是 pass: 若报 pass, 就与"六层检查通过"无法区分
      ⇒ 而那正是 R10 修掉的假通过同族问题。
    """
    with src_dwc({"a.py": DOC + "X = 1\n"}):
        rc, out, _ = run_gate("--gate", "3")
    assert "[◐ 未采用]" in out, \
        "无人声明六层应报未采用\n实际:\n%s" % out
    assert "尚未被项目采纳" in out
    assert rc != 0, "未采用不该算通过"


def test_six_layer_full_adoption_passes():
    """意图: 六层全部声明 **且 Γ 特征齐备** ⇒ 采用且完整 ⇒ PASS。

    ★★ 2026-10-05 R15 更正: R14 时这个断言是"六层名出现即通过"。
      而 R15 之后 Γ 已裁决采用（2026-10-05 用户裁决），
      故"六层名齐备但 Γ 未落地"是第四态 `adopted_not_implemented`，
      不是 pass —— 那正是 src/dwc/foundation/activity.py 落地前的真实状态。
      ⇒⇒ 所以本测试必须同时提供六层名**和** Γ 定义特征。
    """
    body = (DOC + "LAYERS = " + repr(list(LAYERS)) + "\n"
            "present = registered = called = True\n"
            "succeeded = produced_effect = feedback_closed = False\n"
            "class Layer:\n    pass\n"
            "ORDER = 1\n"
            "Layer = object()\n"
            "FEEDBACK_CLOSED = 1\n")
    with src_dwc({"b.py": body}):
        rc, out, _ = run_gate("--gate", "3")
    assert "[✓ PASS]" in out, "六层齐备且 Γ 已落地应通过\n实际:\n%s" % out
    assert rc == 0, "六层齐备且 Γ 已落地时 rc 应为 0"


def test_six_layer_names_without_gamma_is_pending():
    """★★★ 意图: 六层名齐备但 Γ 未落地 ⇒ `adopted_not_implemented`。

    ★★★ 这是 R15 引入的第五态，含义是「用户已裁决采用，但代码还没写」。
      它必须与 pass 区分开 —— 与 R10 修的假通过是同一个原则：
      「未被检验」不许与「检验通过」长得一样。
    """
    with src_dwc({"b.py": DOC + "LAYERS = " + repr(list(LAYERS)) + "\n"
                                "present = registered = called = True\n"
                                "succeeded = produced_effect = feedback_closed = False\n"}):
        rc, out, _ = run_gate("--gate", "3")
    assert "[◑ 待实现]" in out, \
        "六层齐备但 Γ 未落地应报待实现\n实际:\n%s" % out
    assert "已裁决采用" in out
    assert rc != 0, "待实现不该算通过"


def test_partial_adoption_becomes_mandatory():
    """★★★ 意图: **一旦任何文件声明六层，立刻转强制** —— 半套分层必须报红。

    ★★★ 这是 R14 方案的关键补偿:
      若只是"未采用就放行"，那有人写了 3/6 个层就能悄悄绕过完整性检查。
      ⇒⇒ 部分声明 = 采用 = 强制 ⇒ 拦掉"半套分层"。
    """
    with src_dwc({"c.py": DOC + "present = registered = called = True\n"}):
        rc, out, _ = run_gate("--gate", "3")
    assert "[✗ FAIL]" in out, "只声明 3/6 层必须报红\n实际:\n%s" % out
    assert "缺活性层" in out, "应指出缺哪几层\n实际:\n%s" % out
    for missing in ("succeeded", "produced_effect", "feedback_closed"):
        assert missing in out, "应点名缺失的层 %r" % missing


def test_weak_judgement_still_checked_when_not_adopted():
    """★★ 意图: not_adopted 只豁免"六层完整性"这一项，另两条规则照跑。

    ★★ 否则 not_adopted 会变成一个逃逸口: 声明零个层就能免检。
    """
    with src_dwc({"d.py": DOC + "X = 1\n\n\n"
                            "def record_call(v):\n"
                            "    if v.call_count == 0:\n"
                            "        stale.append(v)\n"}):
        rc, out, _ = run_gate("--gate", "3")
    assert "never_called 混入 stale" in out, \
        "never_called 规则不受 not_adopted 影响\n实际:\n%s" % out
    assert "[✗ FAIL]" in out


# ══════════════════════════════════════════════════════════
# ④ 有真实副作用时不该误报（防止变成噪声门）
# ══════════════════════════════════════════════════════════

NOT_VIOLATIONS = {
    "ok_with_side_effect.py": (
        '"""DWC-MEM 定位声明在。"""\n\n\n'
        'def save(obj):\n    n = write(obj)\n'
        '    return {"ok": True, "side_effect": n}\n'),
    "ok_with_readback.py": (
        '"""DWC-MEM 定位声明在。"""\n\n\n'
        'def save(o, v):\n    setattr(o, "k", v)\n'
        '    assert getattr(o, "k") == v\n'
        '    return {"ok": True}\n'),
    "ok_plain_module.py": '"""DWC-AUTO 定位声明在。"""\n\n\nVALUE = 1\n',
}


def test_no_false_positive_on_legit_code():
    """★★ 意图: 合法代码不该被报红 —— 否则门会变成噪声门而被忽略。"""
    with _SrcFixture(NOT_VIOLATIONS):
        rc, out, _ = run_gate("--gate", "7")
    assert "疑似伪装成功" not in out, \
        "有真副作用时不该报'伪装成功'\n实际:\n%s" % out


def test_multi_line_dict_is_detected():
    """★★ 意图（回归）: 多行 dict 也要检出 —— 今天的旧判据漏了它。"""
    with _SrcFixture({
            "bad_multiline.py": ('"""DWC-MEM 定位声明在。"""\n\n\n'
                                'def save():\n    return {\n'
                                '        "ok": True,\n        "n": 1,\n    }\n')}):
        rc, out, _ = run_gate("--gate", "7")
    assert "疑似伪装成功" in out, \
        "多行 dict 也要检出（旧判据漏检的就是这个）\n实际:\n%s" % out


def test_annotated_return_is_detected():
    """意图: 带类型注解的 return 也要检出（旧判据只检这一种）。"""
    with _SrcFixture({
            "bad_annot.py": ('"""DWC-MEM 定位声明在。"""\n\n\n'
                             'def save() -> dict:\n    return {"ok": True}\n')}):
        rc, out, _ = run_gate("--gate", "7")
    assert "疑似伪装成功" in out, \
        "带注解的 return 也要检出\n实际:\n%s" % out


# ══════════════════════════════════════════════════════════
# 单跑某一道门也必须给 n_a（今天修的第一处是 --gate 路径）
# ══════════════════════════════════════════════════════════

def test_single_gate_run_also_reports_n_a():
    """意图: --gate 3 单跑时也必须报 n_a, 且 rc 非 0。"""
    with src_dwc():
        rc, out, _ = run_gate("--gate", "3")
    assert "[○ N/A ]" in out, \
        "单跑 G3 也须报 n_a\n实际:\n%s" % out
    assert rc != 0, "单跑且无对象时 rc 必须非 0"


def test_trace_is_written_every_run():
    """意图: 门跑一次留一次痕（gate.py 头注释里写的首要目标）。"""
    with src_dwc():
        run_gate()
    trace = os.path.join(ROOT, "archive", "gate_trace.jsonl")
    assert os.path.exists(trace), "缺少痕迹文件"
    with io.open(trace, encoding="utf-8") as f:
        lines = [x for x in f.read().split("\n") if x.strip()]
    assert lines, "痕迹文件为空"


# ══════════════════════════════════════════════════════════

def test_load_gate_module_importable():
    """意图: gate.py 可被按路径导入（测试直接调它的 _status）。"""
    mod = load_gate()
    assert hasattr(mod, "_status")
    assert mod.NEED_FILES == {1, 2, 3, 4, 7}, \
        "NEED_FILES 被改了: %r（新增扫源码的门必须同步维护这张表）" % mod.NEED_FILES


def test_status_helper_semantics():
    """意图: _status 的三态语义 —— 空 files 必须是 n_a, 哪怕 pass=True。"""
    mod = load_gate()
    # 关键: pass=True 但 files=0 ⇒ 必须 n_a（这正是原来的漏洞）
    assert mod._status({"gate": 1, "pass": True, "files": 0}) == "n_a"
    assert mod._status({"gate": 1, "pass": False, "files": 0}) == "n_a"
    assert mod._status({"gate": 1, "pass": True, "files": 3}) == "pass"
    assert mod._status({"gate": 1, "pass": False, "files": 3}) == "fail"
    # 不需要文件的门
    assert mod._status({"gate": 5, "pass": True, "files": None}) == "pass"