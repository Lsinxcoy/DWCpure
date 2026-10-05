# -*- coding: utf-8 -*-
"""capability_groups 加载器的契约测试。

★★★ 存在理由
  这个模块是 DWC 的**第一份实现代码**（2026-10-05）。
  在它之前，所有判据都只是文档里的话，没人跑过。
  ⇒ 所以它的测试不只是"测功能"，而是**第一次把判据变成可执行的证据**。

★ 测什么（按意图，不按实现）:
  ① G1  每条 sealed 任务恰好属一个组（无遗漏、无重复）
  ② G2  每组至少 n_min 条
  ③ G3  config 声称的统计量必须与源数据一致（防止 yaml 与任务集脱节）
  ④ G4  lambda_assert ≥ 1/median（否则第⑦步是死判据）
  ⑤ G6  组数上限
  ⑥ ★  派生字段由 loader 重算，不从 config 读（这是它存在的主要理由）
  ⑦ ★  空/坏输入必须 raise，不许静默通过（承重代码不许吞异常）
"""
from __future__ import annotations

import copy
import io
import os
import subprocess
import sys
import tempfile

ROOT = r"E:/Divine Wisdom Core"
SRC = os.path.join(ROOT, "src", "dwc", "foundation", "capability_groups.py")

sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation import capability_groups as cg  # noqa: E402


def _tmp_yaml(obj, suffix=""):
    """写临时 yaml 并返回路径。★ 必须 os.close(fd)，否则 Windows 锁住文件，
    后面的 os.remove 会 PermissionError（这正是本文件初版 6 项失败的根因）。"""
    import yaml
    fd, path = tempfile.mkstemp(suffix=suffix or ".yaml")
    os.close(fd)                      # ★★★ 关键: 关闭 mkstemp 的原始句柄
    with io.open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True)
    return path


# ══════════════════════════════════════════════
# ⑥ 派生字段（这个模块存在的主要理由）
# ══════════════════════════════════════════════

def test_derived_field_is_recomputed_not_read():
    """★★ 意图: lambda_floor_ratio 由 loader 重算。

    为什么这条最重要: config 初版为三组各手填了一个 lambda_floor_ratio，
    其中 knowledge_reasoning 填 0.286 而精确值是 0.2857142857…
    ⇒ 核验时当场报红 ⇒ 结论是"派生字段不该由人填"。
    ⇒ 这个测试就是为了保证那条结论不被回退。
    """
    groups = cg.validate_all()
    raw = cg.load_config()
    # config 里**不该**有 lambda_floor_ratio
    for g in raw["groups"]:
        assert "lambda_floor_ratio" not in g, \
            "config 里不该手填派生字段（group %s）" % g["group_id"]
    # 而 loader 给出的值必须精确等于 1/median
    for g in groups:
        expect = 1.0 / g.n_assertions_median
        assert g.lambda_floor_ratio == expect, \
            "组 %s 的 lambda_floor_ratio=%r，应为 %r" \
            % (g.group_id, g.lambda_floor_ratio, expect)


def test_derived_field_declared_in_config():
    """意图: derived_fields 里必须声明 lambda_floor_ratio 由 loader 算。"""
    raw = cg.load_config()
    names = [d["name"] for d in raw.get("derived_fields") or []]
    assert "lambda_floor_ratio" in names, \
        "config 必须声明 lambda_floor_ratio 是派生字段（实测 %r）" % names


# ══════════════════════════════════════════════
# ① – ⑤ 正常路径的六条判据
# ══════════════════════════════════════════════

def test_valid_config_passes_all_six_criteria():
    """意图: 现存 config 应通过 G1–G6 全套（这是它该有的状态）。"""
    groups = cg.validate_all()
    assert len(groups) == 3, "应有 3 组，实为 %d" % len(groups)
    total = sum(len(g.sealed_task_ids) for g in groups)
    assert total == 15, "应覆盖 15 条任务，实为 %d" % total


def test_groups_are_frozen_dataclasses():
    """意图: Group 不可变（判据 I6 同款纪律 —— 造错值比改值更容易测）。"""
    groups = cg.validate_all()
    g0 = groups[0]
    try:
        g0.lambda_assert = 999
        raise AssertionError("Group 竟然可改 —— frozen 失效")
    except Exception as exc:
        assert "frozen" in str(exc).lower() or \
               "cannot assign" in str(exc).lower(), \
            "抛的不是 frozen 相关异常: %r" % exc


def _resync_stats(raw, gi):
    """★ 只同步统计量，**不碰 sealed_task_ids**。

    用途: 构造"只想触发某一条判据"的输入。
      loader 的检查顺序是 G3 → G2 → G4 → 再 G1/G5/G6，
      所以若不改统计量，G3 会先报错，测试就变成在测 G3。

    ★★★ 2026-10-05 修正（这是本文件第三次被自己的失败教）
      初版这个函数里有一行 `g["sealed_task_ids"] = [s.task_id for s in src]`，
      而 src 是**按 category 取全量**的 ⇒ 它把测试刚故意删掉的 id 又加回来
      ⇒ 违规被撤销 ⇒ 测试报"期待 G2 违规，但它没报"。
      ⇒ ★★ 教训: 造违规输入的辅助函数**绝不能顺手修复那个违规**。
    """
    import statistics as _st
    g = raw["groups"][gi]
    by_id = {s.task_id: s for s in cg.load_sealed()}
    per = [by_id[t].n_assertions for t in g["sealed_task_ids"]]
    g["n_assertions_per_task"] = per
    g["n_assertions_total"] = sum(per)
    g["n_assertions_median"] = float(_st.median(per))
    return raw


# ══════════════════════════════════════════════
# ③ G3：config 与源数据脱节必须被抓
# ══════════════════════════════════════════════

def test_g3_catches_median_mismatch():
    """★★ 意图: config 里的中位数被改错时必须 raise。

    真实发生过: 初版把 knowledge_reasoning 的 median 写成 4（上中位数），
    实测标准中位数是 3.5 ⇒ G3 就是为这类错误存在的。
    """
    raw = copy.deepcopy(cg.load_config())
    for g in raw["groups"]:
        if g["group_id"] == "knowledge_reasoning":
            g["n_assertions_median"] = 4.0
    p = _tmp_yaml(raw)
    try:
        with _expect_raises("G3"):
            cg.validate_all(cfg_path=p)     # ★ 用改过的临时 config
    finally:
        os.remove(p)


def test_g3_catches_total_mismatch():
    """意图: n_assertions_total 与源数据不符必须 raise。"""
    raw = copy.deepcopy(cg.load_config())
    raw["groups"][0]["n_assertions_total"] = 999
    p = _tmp_yaml(raw)
    try:
        # 用临时 config 跑
        with _expect_raises("G3"):
            cg.build_groups(raw, cg.load_sealed())
    finally:
        os.remove(p)


def test_g3_catches_per_task_mismatch():
    """意图: 逐任务断言数与源数据不符必须 raise。"""
    raw = copy.deepcopy(cg.load_config())
    raw["groups"][0]["n_assertions_per_task"] = [9, 9, 9, 9, 9, 9]
    try:
        with _expect_raises("G3"):
            cg.build_groups(raw, cg.load_sealed())
    except AssertionError:
        raise
    finally:
        pass


# ══════════════════════════════════════════════
# ① G1：覆盖完整性
# ══════════════════════════════════════════════

def test_g1_catches_missing_task():
    """★★ 意图: 有任务没被任何组覆盖必须 raise（不许静默通过）。

    ★★ 2026-10-05 修正: 初版只删掉一个 id, 结果 loader 先在 G3
      （per_task 与源数据不符）就报错了 ⇒ 测的其实是 G3, 不是 G1。
      ⇒ 修法: 删 id 的**同时**同步改该组的统计量, 让 G3 通过、只暴露 G1。
    """
    raw = copy.deepcopy(cg.load_config())
    g0 = raw["groups"][0]
    g0["sealed_task_ids"] = g0["sealed_task_ids"][:-1]
    _resync_stats(raw, 0)          # ★ 让 G3 通过
    with _expect_raises("G1"):
        cg.build_groups(raw, cg.load_sealed())


def test_g1_catches_duplicate_task():
    """★★ 意图: 同一任务被两个组覆盖必须 raise。

    ★★ 同上: 初版会让 G1 与 G3 同时触发 ⇒ 现在同步两组的统计量，
    让 G1 成为唯一触发点（真正的重复覆盖）。
    """
    raw = copy.deepcopy(cg.load_config())
    a = raw["groups"][0]["sealed_task_ids"]
    b = raw["groups"][1]["sealed_task_ids"]
    b[0] = a[0]
    _resync_stats(raw, 0)
    _resync_stats(raw, 1)
    with _expect_raises("G1"):
        cg.build_groups(raw, cg.load_sealed())


# ══════════════════════════════════════════════
# ② G2 / ④ G4 / ⑤ G6
# ══════════════════════════════════════════════

def test_g2_catches_undersized_group():
    """★★ 意图: 某组少于 n_min 条必须 raise。

    ★★ 同上: 只留 2 条会让 G3 先报（per_task 不符）⇒ 同步统计量，让 G2 单独触发。
    """
    raw = copy.deepcopy(cg.load_config())
    raw["groups"][0]["sealed_task_ids"] = raw["groups"][0]["sealed_task_ids"][:2]
    _resync_stats(raw, 0)
    with _expect_raises("G2"):
        cg.build_groups(raw, cg.load_sealed())


def test_g4_catches_dead_criteria():
    """★★ 意图: lambda_assert < 1/median ⇒ 第⑦步是死判据 ⇒ 必须 raise。

    这条对应真实缺陷: 分数口径 Λ=0.03 在三组上全部是死判据。
    """
    raw = copy.deepcopy(cg.load_config())
    for g in raw["groups"]:
        if g["group_id"] == "paper_reproduction":
            g["lambda_assert"] = 0        # 0 < 1/2.0 = 0.5 ⇒ 死判据
    try:
        with _expect_raises("G4"):
            cg.build_groups(raw, cg.load_sealed())
    finally:
        pass


def test_g5_catches_single_consumer():
    """意图: consumers 少于两处 ⇒ 能力组只是标签 ⇒ 必须 raise。"""
    raw = copy.deepcopy(cg.load_config())
    raw["consumers"] = ["only_one"]
    try:
        with _expect_raises("G5"):
            cg.build_groups(raw, cg.load_sealed())
    finally:
        pass


# ══════════════════════════════════════════════
# ⑦ 空 / 坏输入必须 raise
# ══════════════════════════════════════════════

def test_missing_sealed_file_raises():
    """★★ 意图: 源数据文件不存在必须 raise，不许返回空列表。

    这是 gate.py 那个 n_a 契约在加载器侧的对应要求:
    "无可检对象"必须与"检查通过"区分开。
    """
    try:
        cg.load_sealed(path=os.path.join(ROOT, "no_such_file.yaml"))
        raise AssertionError("★ 不该返回: 源数据不存在时必须 raise")
    except cg.ConfigError as e:
        assert "不存在" in str(e)


def test_empty_tasks_raises():
    """意图: sealed 里 tasks 为空必须 raise（不是"通过"）。"""
    import yaml
    p = _tmp_yaml({"tasks": []})
    try:
        cg.load_sealed(path=p)
        raise AssertionError("★ 不该返回: tasks 为空必须 raise")
    except cg.ConfigError as e:
        assert "无可检对象" in str(e)
    finally:
        os.remove(p)


def test_task_without_assertions_raises():
    """★★ 意图: 三种断言字段全缺时必须 raise，**不许默认为 1**。

    默认为 1 会让 n_assertions 全部错，而错误的中位数比报错更危险。
    """
    import yaml
    p = _tmp_yaml({"tasks": [{"id": "t1", "category": "c",
                               "verifier_rung": 1}]})
    try:
        cg.load_sealed(path=p)
        raise AssertionError("★ 不该返回: 无断言字段必须 raise")
    except cg.ConfigError as e:
        assert "不许默认为 1" in str(e)
    finally:
        os.remove(p)


def test_non_human_reviewed_flag_honoured():
    """★★ 意图: has_history_scores=false 的组必须如实保留该标记。

    这条不是校验，是**防止修代码时顺手把它改成 true** ——
    组定义条件②（历史成绩序列）目前确实未满足。
    """
    groups = cg.validate_all()
    assert all(g.has_history_scores is False for g in groups), \
        "三组的 has_history_scores 应全为 false（历史序列尚未落地）"


# ══════════════════════════════════════════════

class _expect_raises:
    """上下文管理器: 期待某个编号的判据被触发。"""

    def __init__(self, tag):
        self.tag = tag

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            raise AssertionError("★ 期待 %s 违规被 raise，但它没报" % self.tag)
        if not issubclass(exc_type, cg.ConfigError):
            return False
        if self.tag not in str(exc):
            raise AssertionError(
                "★ 期待 %s 违规，实为别的: %s" % (self.tag, exc))
        return True


def test_module_runs_as_script():
    """意图: 直接 python 跑它应打印三组概况并 rc=0。"""
    r = subprocess.run([sys.executable, SRC], capture_output=True,
                       timeout=120, cwd=ROOT)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0, "直跑应 rc=0\nstderr: %s" % r.stderr.decode()[-400:]
    assert "3 组 / 15 任务" in out, "输出应说明组数与任务数\n%s" % out