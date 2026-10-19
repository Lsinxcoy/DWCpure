# -*- coding: utf-8 -*-
"""R369 · 激活审计工具的行为锁。

守的是"分类逻辑"而不是"当前仓库的审计结果"——
后者会随接线工作变化（hook 从 TEST 变 PRODUCTION 是目标），
前者必须稳定。

四态语义:
  PRODUCTION  从生产入口可达
  SCRIPT      仅从工具脚本可达
  TEST        仅被 tests/ 引用
  ORPHAN      无人引用
"""
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

# 用显式模块加载，不污染 sys.path（scripts/ 下的同名模块会遮蔽真实包）
_SPEC = importlib.util.spec_from_file_location(
    "dwc_activation_audit",
    os.path.join(_ROOT, "scripts", "activation_audit.py"),
)
A = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(A)


def _mk(tmp_path, files):
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def _bind(monkeypatch, tmp_path, prod, script=()):
    monkeypatch.setattr(A, "ROOT", str(tmp_path))
    monkeypatch.setattr(A, "SRC_DWC", str(tmp_path / "src" / "dwc"))
    monkeypatch.setattr(A, "TESTS_DIR", str(tmp_path / "tests"))
    monkeypatch.setattr(A, "SCRIPTS_DIR", str(tmp_path / "scripts"))
    monkeypatch.setattr(A, "PRODUCTION_ENTRIES", list(prod))
    monkeypatch.setattr(A, "SCRIPT_ENTRIES", list(script))


def test_classification_four_states(tmp_path, monkeypatch):
    """一条链: entry -> a -> b；c 只有测试；d 无人引用。"""
    _mk(tmp_path, {
        "src/dwc/__init__.py": "",
        "src/dwc/a.py": "from dwc import b\n",
        "src/dwc/b.py": "",
        "src/dwc/c.py": "",
        "src/dwc/d.py": "",
        "scripts/entry.py": "import dwc.a\n",
        "tests/test_x.py": "import dwc.c\n",
    })
    _bind(monkeypatch, tmp_path, ["scripts/entry.py"])

    rows, summary = A.classify(A.collect_modules())

    assert rows["dwc.a"]["status"] == "PRODUCTION"
    assert rows["dwc.b"]["status"] == "PRODUCTION"   # import 传递可达
    assert rows["dwc.c"]["status"] == "TEST"         # 单测绿 ≠ 生产接线
    assert rows["dwc.d"]["status"] == "ORPHAN"
    # dwc 包本身经隐式父包可达
    assert rows["dwc"]["status"] == "PRODUCTION"
    assert summary["production"] == 3
    assert summary["test"] == 1
    assert summary["orphan"] == 1


def test_script_only_is_not_production(tmp_path, monkeypatch):
    """工具脚本可达 ≠ 常驻 agent 可达。"""
    _mk(tmp_path, {
        "src/dwc/__init__.py": "",
        "src/dwc/s.py": "",
        "scripts/entry.py": "",
        "scripts/tool.py": "import dwc.s\n",
    })
    _bind(monkeypatch, tmp_path, ["scripts/entry.py"], ["scripts/tool.py"])

    rows, _ = A.classify(A.collect_modules())
    assert rows["dwc.s"]["status"] == "SCRIPT"


def test_relative_import_resolves(tmp_path, monkeypatch):
    """from ..base import x 必须解析成 dwc.base 并传递可达。"""
    _mk(tmp_path, {
        "src/dwc/__init__.py": "",
        "src/dwc/base.py": "",
        "src/dwc/pkg/__init__.py": "",
        "src/dwc/pkg/x.py": "from ..base import helper\n",
        "scripts/entry.py": "import dwc.pkg.x\n",
    })
    _bind(monkeypatch, tmp_path, ["scripts/entry.py"])

    rows, _ = A.classify(A.collect_modules())
    assert rows["dwc.base"]["status"] == "PRODUCTION"
    assert rows["dwc.pkg.x"]["status"] == "PRODUCTION"


def test_import_dwc_does_not_pull_everything(tmp_path, monkeypatch):
    """`import dwc` 不等于 import 所有子模块 —— 否则全仓恒为可达。"""
    _mk(tmp_path, {
        "src/dwc/__init__.py": "",
        "src/dwc/unused.py": "",
        "scripts/entry.py": "import dwc\n",
    })
    _bind(monkeypatch, tmp_path, ["scripts/entry.py"])

    rows, _ = A.classify(A.collect_modules())
    assert rows["dwc"]["status"] == "PRODUCTION"
    assert rows["dwc.unused"]["status"] == "ORPHAN"
