# -*- coding: utf-8 -*-
"""R432 · 注释里不许写答案（本仓库就是评测语料）。

★★★ 现场（17:14，rf08 那次"通过"）：
    模型搜到的第一条命中是 `src/dwc/llm/task_exec.py:833` ——
    **我自己在 R430 写的注释**：

        #   `prev` ⇒ 77 条引用、0 条定义 ⇒ 它把 `prev` 当答案（正确是 `_rev_prev`）。

    它直接读到了正确答案。同一次排查里，R429 的注释也写着
    「最后只敢说"推测是 <类名>"」—— 那是 rf05 的答案。

    这不是模型变强了，是**我把答案递给了它**。

★ 规则：本仓库的源码/脚本**同时是评测语料**。
  注释可以写"为什么修"，**不能写"答案是什么"**。
  允许出现的标识符（产品代码里的类名/环境变量）不受影响 ——
  真正要禁的是**把答案和"推测/正确/答案/答对"这类叙述写在同一行**。
"""
from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 叙述性标记：出现这些词的行，如果同时出现答案，就是在"讲答案"
NARRATIVE = ("推测", "正确", "答案", "答对", "应该答", "标准答案", "正确键")

#: 太常见的英文词，出现在注释里不代表泄漏（否则守卫全是噪声）
COMMON = {"prev", "config", "docs", "eval", "llm", "passed", "deep", "src",
          "true", "false", "none", "self", "test", "tests"}


def _eval_targets():
    out = []
    for line in io.open(os.path.join(ROOT, "config", "eval_tasks.jsonl"),
                        encoding="utf-8"):
        if not line.strip():
            continue
        ck = json.loads(line).get("check") or {}
        tg = ck.get("target")
        for t in ([tg] if isinstance(tg, str) else (tg or [])):
            t = str(t)
            # 只盯"标识符形态"的答案（英文词/中文短语不算——它们在
            # 正常注释里太常见，检查会变成噪声）
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]{3,}$", t) and t not in COMMON:
                out.append(t)
    return sorted(set(out))


def _scan(root):
    bad = []
    for d, ds, fs in os.walk(root):
        ds[:] = [x for x in ds if x not in ("__pycache__", ".git", ".venv")]
        for f in fs:
            if not f.endswith(".py"):
                continue
            p = os.path.join(d, f)
            for i, line in enumerate(io.open(p, encoding="utf-8",
                                             errors="replace"), 1):
                s = line.strip()
                if not s.startswith("#"):
                    continue
                if not any(k in s for k in NARRATIVE):
                    continue
                for t in TARGETS:
                    if t in s:
                        bad.append("%s:%d: %s" % (os.path.relpath(p, ROOT), i,
                                                  s[:100]))
                        break
    return bad


TARGETS = _eval_targets()


def test_src_comments_do_not_state_answers():
    """★★★ src/ 的注释不许把"答案"和"推测/正确"写在一起。"""
    bad = _scan(os.path.join(ROOT, "src"))
    assert not bad, "注释泄漏答案:\n" + "\n".join(bad)


def test_scripts_comments_do_not_state_answers():
    """★★★ scripts/（含评测器本身）同样不许。"""
    bad = _scan(os.path.join(ROOT, "scripts"))
    assert not bad, "注释泄漏答案:\n" + "\n".join(bad)


def test_scan_is_not_vacuous():
    """★★ 守卫必须真的能抓到 —— 用一个合成的泄漏行自测。"""
    sample = "    # 现场：模型答错了（正确答案是 MemoryKernel）"
    hits = [t for t in TARGETS if t in sample]
    assert hits, "扫描逻辑失效：合成样本没命中"
    assert any(k in sample for k in NARRATIVE)
