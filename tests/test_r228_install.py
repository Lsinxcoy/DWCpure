# -*- coding: utf-8 -*-
"""R228-R230 · 发布安装层: 根发现/一键安装/配置向导/环境 doctor。"""
from __future__ import annotations

import io
import re
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
        # ★ 判据语义: 装完有配置向导指引 —— R235 后指引形态是 "dwc setup"
        #   （console_scripts 命令, 不再是脚本路径 — 锁跟语义不跟字面）
        assert ("dwc_setup.py" in content or "dwc setup" in content), \
            name + " 缺配置向导指引"
        assert "冒烟" in content or "smoke" in content.lower() or "自检" in content
    assert os.path.exists(os.path.join(ROOT, "requirements.txt"))


def test_setup_check_runs_smoke_only():
    """★★ 向导 --check: 只冒烟不写配置（llm.json 不被测试改动）。

    ★ 判据校准（2026-10-14 Layer-22）: timeout 120→300 — 端点卡时 client 的
      重试链（transport/timeout 重试 × 30s urlopen 超时）总时长可超 120s,
      120s 曾把"慢重试"误判为挂死（判据宽容真实重试链, 不是放水:
      配置未动与冒烟输出两个断言原样保留）。"""
    llm = os.path.join(ROOT, "config", "llm.json")
    before = io.open(llm, encoding="utf-8").read() if os.path.exists(llm) else None
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "dwc_setup.py"),
         "--check"],
        capture_output=True, text=True, timeout=300, cwd=ROOT,
        encoding="utf-8", errors="replace")
    after = io.open(llm, encoding="utf-8").read() if os.path.exists(llm) else None
    assert before == after, "--check 动了配置（只许冒烟）"
    assert "冒烟自检" in r.stdout
    # ★ 判据补(2026-10-14 Layer-22): 曾只断言标题 — probe 段把 LLMResult
    #   当 dict 用 .get() 崩成"probe 异常"也照样过。代码级异常=红;
    #   端点"未通过"是环境态允许（不产生"异常"行）。
    assert "LLM probe 异常" not in r.stdout, r.stdout[-400:]


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

def test_ps1_with_chinese_needs_bom():
    """★★★ R248b 锁: 含中文的 .ps1 必须带 UTF-8 BOM。

    ★ 起因(2026-10-13 用户实测): install.ps1 中文无 BOM, PS5.1 按 ANSI(GBK)
      读 ⇒ '已把' 变 '宸叉妸' 破坏字符串边界 ⇒ 级联 3 个 ParseError
      (第13行缺 }/第53行意外token)。负向对照: 无 BOM 副本 PARSE_ERRORS=3。
    """
    for dirpath, _d, files in os.walk(ROOT):
        if any(x in dirpath for x in (".git", ".venv", ".cache", "gh_clones")):
            continue          # 只锁本仓自有 ps1（外仓克隆缓存不归此锁）
        for f in files:
            if not f.endswith(".ps1"):
                continue
            p = os.path.join(dirpath, f)
            raw = io.open(p, "rb").read()
            if not raw.startswith(b"\xef\xbb\xbf"):
                body = raw.decode("utf-8")
                assert not re.search(r"[\u4e00-\u9fff]", body), (
                    "%s 含中文但无 UTF-8 BOM — PS5.1 会按 GBK 乱码解析"
                    % os.path.relpath(p, ROOT))


def test_step_smoke_probe_uses_object_api(capsys, monkeypatch):
    """★ 行为锁(2026-10-14): probe 返回 LLMResult **对象** — step_smoke 曾用
    dict 的 .get() ⇒ AttributeError 被 except 兜成"probe 异常"（用户实测
    "LLM probe 异常: 'LLMResult' object has no attribute 'get'"）。

    两态: ok=True → 返回 True 打 OK; ok=False → 返回 False 打"未通过"（**不**异常）。
    """
    import importlib.util
    import sys
    from types import SimpleNamespace

    import dwc.llm.client as CL
    from dwc.llm.client import LLMResult

    spec = importlib.util.spec_from_file_location(
        "dwc_setup_probe_lock",
        os.path.join(ROOT, "scripts", "dwc_setup.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    class _FakeOk:
        def probe(self):
            return LLMResult(ok=True, source="llm", text="pong")

    class _FakeBad:
        def probe(self):
            return LLMResult(ok=False, source="error", error="boom-503")

    monkeypatch.setattr(CL, "LLMClient", _FakeOk)
    assert mod.step_smoke() is True
    out = capsys.readouterr().out
    assert "LLM probe: OK" in out and "probe 异常" not in out, out

    monkeypatch.setattr(CL, "LLMClient", _FakeBad)
    assert mod.step_smoke() is False
    out = capsys.readouterr().out
    assert "未通过 — boom-503" in out and "probe 异常" not in out, out
