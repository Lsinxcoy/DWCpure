"""★ R302 · qa final 引用校验（ALCE 本地版：路径+行号+引文三验）。

只验有引用的句子，纯观点放行；URL 跳过；裸数字不验。
测试走 tmp cwd，禁碰生产 var。
"""
import os

import pytest

from dwc.llm.step_judge import verify_final_refs


@pytest.fixture()
def root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DWC_ROOT", str(tmp_path))
    return tmp_path


def _w(root, rel, n=10, text=None):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    body = text if text is not None else "\n".join("line%d" % i
                                                  for i in range(1, n + 1))
    p.write_text(body, encoding="utf-8")
    return p


def test_path_exists_pass(root):
    _w(root, "src/a.py")
    assert verify_final_refs("见 src/a.py 的实现", str(root)) is None


def test_path_missing_block(root):
    err = verify_final_refs("见 docs/world_model.py 的设计", str(root))
    assert err and "world_model.py" in err


def test_url_skipped(root):
    assert verify_final_refs(
        "见 https://arxiv.org/abs/2606.09498 的§3.4", str(root)) is None


def test_lineno_in_range_pass(root):
    _w(root, "src/a.py", 30)
    assert verify_final_refs("src/a.py 第 6 行写了护栏",
                             str(root)) is None


def test_lineno_out_of_range(root):
    _w(root, "src/a.py", 10)
    err = verify_final_refs("src/a.py 第 99 行", str(root))
    assert err and "99" in err


def test_quote_hit_pass(root):
    _w(root, "config/dwc_self.md", text="6 轮未 final ⇒ 报 incomplete")
    assert verify_final_refs("config/dwc_self.md 写了“6 轮未 final”",
                             str(root)) is None


def test_quote_miss_block(root):
    _w(root, "config/dwc_self.md", text="别的")
    err = verify_final_refs("config/dwc_self.md 写了“子曾经曰过”",
                            str(root))
    assert err and "子曾经曰过" in err


def test_pure_opinion_pass(root):
    assert verify_final_refs("我觉得这个设计对你有影响",
                             str(root)) is None


def test_final_ref_block_reroutes(root):
    """★ 引用打回：qa 下 final 含幻觉路径⇒不 done（第 2 次真答案⇒done）。"""
    import dwc.llm.task_exec as T

    class _Bad:
        ok = True
        text = ('{"op": "final", "answer": "见 docs/world_model.py 第 3 行'
                '的设计，很好", "analysis": "答"}')

    class _Good:
        ok = True
        text = ('{"op": "final", "answer": "自我认知里有这条，我觉得有影响", '
                '"analysis": "改"}')

    seq = [_Bad(), _Good()]
    box = {"n": 0}

    class _LLM:
        def complete(self, prompt, **kw):
            r = seq[min(box["n"], 1)]
            box["n"] += 1
            return r

    r = T.execute_user_task("自进化对你有影响吗", llm=_LLM(),
                            task_id="T_R302B", retry_on_fail=False)
    assert r["status"] == "done" and box["n"] == 2, (r, box)


def test_final_ref_two_strikes_pass(root):
    """★ 防死循环：引用连打回 2 次⇒第 3 次放行（不无限打回）。"""
    import dwc.llm.task_exec as T

    class _Bad:
        ok = True
        text = ('{"op": "final", "answer": "见 docs/ghost.py 的设计", '
                '"analysis": "执"}')

    class _LLM:
        def complete(self, prompt, **kw):
            return _Bad()

    r = T.execute_user_task("这个设计好吗你觉得", llm=_LLM(),
                            task_id="T_R302S", retry_on_fail=False,
                            max_rounds=5)
    assert r["status"] == "done" and r["rounds"] <= 4, (r,)
