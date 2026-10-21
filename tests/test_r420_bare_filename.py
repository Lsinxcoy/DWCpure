# -*- coding: utf-8 -*-
"""R420 · 裸文件名按**基名**全仓解析，不按根目录。

★★★ 现场（analyze 41「铁律文档在哪个目录下？只答目录名」）：
    `config/iron_laws.yaml` **真实存在**（12KB），
    模型答「iron_laws.yaml」（裸名，没写目录），
    `verify_final_refs` 按 `os.path.join(root, "iron_laws.yaml")` 解析
    ⇒ 不存在 ⇒ 打回「引用路径不存在」；
    打回两次后任务以 `answer=None` 收场 —— **比答错更糟**。

★ 判据：裸名 = 没给路径，本来就不该按根目录解释。
  但**带路径的错路径**（`config/nope.yaml`）仍必须拒。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.step_judge import verify_final_refs  # noqa: E402

#: 拼接构造，避免假名被仓库检索命中（自证预言）
FAKE = "zzz_" + "nonexistent.yaml"


def test_bare_real_filename_passes():
    """★★★ 核心：`iron_laws.yaml` 在 config/ 下真实存在 ⇒ 裸名放行。"""
    assert os.path.exists(os.path.join(ROOT, "config", "iron_laws.yaml")), \
        "前提失效：config/iron_laws.yaml 不在了"
    assert verify_final_refs("铁律在 iron_laws.yaml", root=ROOT) is None


def test_bare_fake_filename_rejected():
    """★★ 反面：裸名在仓库里真的没有 ⇒ 仍要拒（别把校验改瞎）。"""
    got = verify_final_refs("见 %s" % FAKE, root=ROOT)
    assert got, "编造的文件名被放行了"
    assert "不存在" in got


def test_wrong_explicit_path_rejected():
    """★★ 反面：给了路径但路径错 ⇒ 仍要拒（只有裸名才做基名回退）。"""
    got = verify_final_refs("见 config/%s" % FAKE, root=ROOT)
    assert got, "错路径被放行了"


def test_correct_explicit_path_passes():
    """★ 回归：给了正确路径当然放行。"""
    assert verify_final_refs("见 config/iron_laws.yaml", root=ROOT) is None
