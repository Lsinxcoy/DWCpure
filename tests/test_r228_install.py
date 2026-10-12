# -*- coding: utf-8 -*-
"""R228-R230 · 发布安装层: 根发现/一键安装/配置向导/环境 doctor。"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation.paths import find_root, DwcRootError         # noqa: E402
import pytest                                                   # noqa: E402


def test_find_root_auto_and_env(monkeypatch):
    """★★★ 根发现: ① 自动上溯（标志 config/+src/dwc/ 判定）
    ② env 覆盖 ③ env 指向非目录 ⇒ 大声报错不猜。"""
    assert find_root() == os.path.abspath(ROOT)
    monkeypatch.setenv("DWC_ROOT", ROOT)
    assert find_root() == os.path.abspath(ROOT)
    monkeypatch.setenv("DWC_ROOT", r"C:\nonexistent_dir_xxx")
    with pytest.raises(DwcRootError, match="不是目录"):
        find_root()


def test_no_hardcoded_drive_in_src():
    """★★★ 发布底线锁: src 核心模块不得写死盘符路径/用户名（新机器可装的
    结构性保证 — 回潮即红）。"""
    import glob
    banned = ("E:/Divine Wisdom Core", "E:\\Divine Wisdom Core", "41228")
    offenders = []
    for p in glob.glob(os.path.join(ROOT, "src", "dwc", "**", "*.py"),
                       recursive=True):
        if os.path.basename(p) == "paths.py":
            continue
        s = io.open(p, encoding="utf-8").read()
        for b in banned:
            if b in s:
                offenders.append((os.path.basename(p), b))
    assert offenders == [], "硬编码回潮: %s" % offenders


def test_install_scripts_exist_with_steps():
    """★ 一键安装脚本: 双平台在位 + 四步语义（venv/依赖/目录/冒烟）。"""
    ps1 = io.open(os.path.join(ROOT, "install.ps1"), encoding="utf-8").read()
    sh = io.open(os.path.join(ROOT, "install.sh"), encoding="utf-8").read()
    for content, name in ((ps1, "ps1"), (sh, "sh")):
        assert "requirements.txt" in content, name
        assert "dwc_setup.py" in content, name + " 缺配置向导指引"
        assert "冒烟" in content or "smoke" in content.lower() or "自检" in content
    assert os.path.exists(os.path.join(ROOT, "requirements.txt"))


def test_setup_check_runs_smoke_only():
    """★★ 向导 --check: 只冒烟不写配置（llm.json 不被测试改动）。"""
    llm = os.path.join(ROOT, "config", "llm.json")
    before = io.open(llm, encoding="utf-8").read() if os.path.exists(llm) else None
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "dwc_setup.py"),
         "--check"],
        capture_output=True, text=True, timeout=120, cwd=ROOT,
        encoding="utf-8", errors="replace")
    after = io.open(llm, encoding="utf-8").read() if os.path.exists(llm) else None
    assert before == after, "--check 动了配置（只许冒烟）"
    assert "冒烟自检" in r.stdout


def test_doctor_has_env_section():
    """★★ doctor 环境段（R230）: python/venv/deps/config_validators 齐 +
    本机全 ok（新机器上这里先红, 指引安装）。"""
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "dwc_cli.py"),
         "doctor", "--json"],
        capture_output=True, text=True, timeout=180, cwd=ROOT,
        encoding="utf-8", errors="replace")
    d = json.loads(r.stdout)
    ck = d.get("checks", d)
    for k in ("python", "venv", "deps", "config_validators"):
        assert k in ck, "doctor 缺环境项 %s" % k
    assert ck["python"].startswith("ok"), ck["python"]
    assert ck["deps"].startswith("ok"), ck["deps"]
    assert ck["config_validators"].startswith("ok"), ck["config_validators"]
