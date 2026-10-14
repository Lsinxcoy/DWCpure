# -*- coding: utf-8 -*-
"""R263 · 短板3 补齐①: web_search + ② PDF 读 的测试锁。

判据设计（G2 纪律）:
- 搜索的**网络**活体不进测试（离线锁 _parse_ddg 结构解析 + 接线三处）;
- PDF 用**自造 fixture**（手写 minimal PDF 生成器 — refs/*.pdf 被
  gitignore 追踪不到, 测试不得依赖仓库外数据）;
- pypdf 依赖进 pyproject 有回归锁（曾"venv 里有但依赖清单缺"）。
"""
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from dwc.llm import step_judge as SJ
from dwc.llm.task_exec import (
    TaskExecError,
    _do_action,
    _parse_ddg,
    ROOT,
)


def _fixture_pdf(text: str) -> bytes:
    """★ 手写 minimal PDF（含 Helvetica 字体资源 — pypdf extractable）。"""
    content = ("BT /F1 12 Tf 20 50 Td (%s) Tj ET" % text).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] "
         b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"),
        (b"<< /Length " + str(len(content)).encode()
         + b" >>\nstream\n" + content + b"\nendstream"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += ("%d 0 obj\n" % i).encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += ("xref\n0 %d\n" % (len(objs) + 1)).encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
            % (len(objs) + 1, xref_at)).encode()
    return bytes(out)


# ---------- ① web_search ----------

def test_parse_ddg_offline_fixture():
    """_parse_ddg 离线解析（真实结构: uddg 重定向链 + 标题 + snippet）。"""
    html = (
        '<a rel="nofollow" class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F'
        '2609.28416&amp;rut=abc123">[2609.28416] Agent-Editing &amp; World</a>'
        '<a class="result__snippet">We propose <b>AEWM</b> a new approach.</a>'
        '<a class="result__a" href="https://example.com/x">Plain Link</a>'
    )
    res = _parse_ddg(html)
    assert len(res) == 2, res
    # uddg 解链出真实 URL（rut 追踪参数丢弃）
    assert res[0]["url"] == "https://arxiv.org/abs/2609.28416", res[0]
    assert "Agent-Editing" in res[0]["title"]
    assert "AEWM" in res[0]["snippet"]
    assert res[1]["url"] == "https://example.com/x"


def test_web_search_wired_three_places():
    """web_search 接线三处: 白名单错误消息 / 系统提示 / step_judge VALID_OPS。"""
    import dwc.llm.task_exec as TE
    src = io.open(TE.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
    assert "web_search" in src
    # 白名单错误消息
    with pytest.raises(TaskExecError) as ei:
        _do_action("definitely_not_an_op", {})
    assert "web_search" in str(ei.value)
    # 系统提示有 web_search 行（搜 query 参数形态）
    assert '"web_search"' in src or '\\"web_search\\"' in src
    # step_judge 白名单
    assert "web_search" in SJ.VALID_OPS


def test_web_search_empty_query_offline():
    """空 query 明确报错（不打网）。"""
    r = _do_action("web_search", {})
    assert r["ok"] is False and "query" in r["error"]


# ---------- ② PDF read ----------

def test_pdf_read_text_and_paging():
    """自造 PDF → read 抽文本 + p.N 页标 + offset/limit 分页复用。

    ★ 目录必须在 repo 内（tmp_path 跨盘会被 _guard_path 拒 — R259 同坑）。"""
    d = os.path.join(ROOT, "var", "__test_r263__")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "r263_fixture.pdf")
    with io.open(p, "wb") as fh:
        fh.write(_fixture_pdf("DWC R263 PDF READ OK"))
    rel = os.path.relpath(p, ROOT).replace("\\", "/")
    r = _do_action("read", {"path": rel, "limit": 10})
    assert r["ok"], r
    assert "DWC R263 PDF READ OK" in r["content"], r["content"]
    assert "--- p.1 ---" in r["content"]
    assert r["n_lines"] >= 1 and r["offset"] == 0
    # 大 limit 不截断该小文件
    assert r["truncated"] is False


def test_pdf_read_missing_file_is_honest_error():
    """不存在的 PDF 如实报错（ok=False + 解析失败原因, 不静默不空串）。"""
    rel = "var/__test_r263__/nope.pdf"
    r = _do_action("read", {"path": rel})
    assert r["ok"] is False
    assert "PDF" in r["error"] or "解析失败" in r["error"]


def test_pypdf_in_pyproject_dependencies():
    """pypdf 必须在 pyproject 依赖（曾'venv 有但清单缺' — 新环境会装不上）。"""
    pp = io.open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8").read()
    dep_block = pp[pp.find("dependencies"):pp.find("optional-dependencies")]
    assert "pypdf" in dep_block, dep_block
