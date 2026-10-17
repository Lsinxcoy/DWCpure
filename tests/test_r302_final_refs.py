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


@pytest.fixture()
def xroot(root):
    """★ 执行隔离：T.ROOT 进程首 import 定死⇒调 execute 的测试必须显式指 ROOT。

    现场：block 测试首 import 定死 ROOT=block-tmp，后续 honest 读旧 tmp
    全 FileNotFoundError×3 熔断（查了 1 小时）。手动 finally 复原子
    （monkeypatch.setattr 跨测试不复原——原因未明，不用）。"""
    import dwc.llm.task_exec as T
    _old, T.ROOT = T.ROOT, str(root)
    try:
        yield root
    finally:
        T.ROOT = _old


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
    # ★ R303-⑥语义更新：URL须在取证obs出现过；取证过则过
    assert verify_final_refs(
        "见 https://arxiv.org/abs/2606.09498 的§3.4", str(root),
        obs_urls=("https://arxiv.org/abs/2606.09498",)) is None


def test_url_unfetched_blocked(root):
    assert isinstance(verify_final_refs(
        "见 https://arxiv.org/abs/2606.09498 的§3.4", str(root)), str)


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


def test_bare_filename_hit_pass(root):
    _w(root, "config/dwc_self.md", text="6 轮未 final")
    assert verify_final_refs("自我认知 config/dwc_self.md 写了护栏",
                             str(root)) is None


def test_bare_filename_missing_block(root):
    err = verify_final_refs("自我认知（dwc_self.md）写了护栏", str(root))
    assert err and "dwc_self.md" in err


def test_final_ref_block_reroutes(xroot):
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


def test_final_ref_two_strikes_pass(xroot):
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


def test_revise_qa_run_rejected(root):
    """★ revision 产 run 在 qa 下被 validate 驳回（R5 绕过补洞）。"""
    from dwc.llm.step_judge import validate_step
    err = validate_step({"op": "run", "cmd": ["grep", "x"],
                         "analysis": "搜"}, allow_final=False, qa_mode=True)
    assert err and "qa" in err
    _w(root, "src/a.py")
    assert validate_step({"op": "read", "path": "src/a.py"},
                         allow_final=False, qa_mode=True,
                         root=str(root)) is None


def test_qa_noop_honest_converge(xroot):
    """★ qa 下取证≥4 后缺 op⇒诚实自动 final（零编造，只报事实）。"""
    import dwc.llm.task_exec as T

    _w(xroot, "src/dwc/llm/task_exec.py", n=1000)

    class _RD:
        ok = True
        text = ('{"op": "read", "path": "src/dwc/llm/task_exec.py", '
                '"offset": %d, "analysis": "读"}')

    class _Mute:
        ok = True
        text = '{"analysis": "思考中，无动作"}'

    box = {"n": 0}

    class _LLM:
        def complete(self, prompt, **kw):
            box["n"] += 1
            if box["n"] <= 5:
                r = _RD()
                r.text = _RD.text % (box["n"] * 100)
                return r
            return _Mute()

    _orig = T._do_action
    def _spy(op, args):
        _o = _orig(op, args)
        print("DBG_DO:", op, (args if isinstance(args, dict) else {}).get("offset"),
              "->", str(_o.get("offset")), str(_o.get("returned_lines")), repr(str(_o.get("content", ""))[:30]))
        return _o
    T._do_action = _spy
    try:
        r = T.execute_user_task("轮数上限依据是什么", llm=_LLM(),
                            task_id="T_R302H", retry_on_fail=False,
                            max_rounds=8)
    finally:
        T._do_action = _orig
    import dwc.llm.task_exec as _T2
    print("DBG_MOD:", id(T), id(_T2), id(T._do_action), T.ROOT)
    print("DBG_WHY:", r.get("status"), r.get("rounds"), str(r.get("why"))[:140])
    assert r["status"] == "done", r
    assert "如实说明" in r["answer"] or "未找到" in r["answer"], r["answer"]


def test_qa_revise_reject_reroutes(xroot):
    """★ 补3：qa 下 revision 被驳回⇒直回 prompt（不记 obs 不耗熔断）。"""
    import dwc.llm.task_exec as T

    class _Mute:
        ok = True
        text = '{"analysis": "思考"}'

    class _Run:
        ok = True
        text = ('{"op": "run", "cmd": ["python", "-c", "print(1)"], '
                '"analysis": "搜一下"}')

    class _F:
        ok = True
        text = '{"op": "final", "answer": "取证受限，如实说没找到确切依据", "analysis": "答"}'

    box = {"n": 0, "prompts": []}

    class _LLM:
        def complete(self, prompt, **kw):
            box["n"] += 1
            box["prompts"].append(prompt)
            # 主循环无 op→R4→revision（prompt 含"噪声动作"⇒产 run，
            # qa 驳回⇒直回 prompt）；次轮 final（纯观点，引用校验过）
            if "噪声动作" in prompt:
                return _Run()
            return _F() if box["n"] >= 3 else _Mute()

    r = T.execute_user_task("轮数上限依据是啥", llm=_LLM(),
                            task_id="T_R302R", retry_on_fail=False,
                            max_rounds=6)
    assert r["status"] == "done", r
    assert any("修订被驳回" in p for p in box["prompts"]), box["prompts"]


def test_read_default_limit_50(xroot):
    """★ 补4：read 缺省 50 行（35 行文件一轮读完，不翻页）。"""
    from dwc.llm.task_exec import _do_action
    _w(xroot, "doc.md", n=35)
    doc = str(xroot / "doc.md")
    out = _do_action("read", {"path": doc})
    assert out["ok"] is True and out["returned_lines"] == 35, out
    out1 = _do_action("read", {"path": doc, "limit": 1})
    assert out1["returned_lines"] == 1, out1


def test_revise_qa_produces_read(xroot):
    """★ 补5：qa 下 revision 约束产 read（不产 run，不被驳回）。"""
    import dwc.llm.task_exec as T

    _w(xroot, "src/qa_target.py", n=60)

    seen = {}

    class _LLM:
        def complete(self, prompt, **kw):
            if "噪声动作" in prompt:
                seen["rev_prompt"] = prompt
                r = type("R", (), {})()
                r.ok = True
                r.text = ('{"op": "read", "path": "src/qa_target.py", '
                          '"analysis": "取证"}')
                return r
            r = type("R", (), {})()
            r.ok = True
            r.text = '{"analysis": "想想"}'
            return r

    r = T.execute_user_task("这个目标是啥", llm=_LLM(),
                            task_id="T_R302Q", retry_on_fail=False,
                            max_rounds=6)
    assert "只能是 read" in seen.get("rev_prompt", ""), seen
    assert r["status"] == "done", r


def test_r4_blank3_converge(xroot):
    """★ 补5b：R4 连空≥3⇒诚实收敛（不耗尽轮数，零编造）。"""
    import dwc.llm.task_exec as T

    class _Mute:
        ok = True
        text = '{"analysis": "空想"}'

    class _LLM:
        def complete(self, prompt, **kw):
            return _Mute()

    r = T.execute_user_task("这事依据是啥", llm=_LLM(),
                            task_id="T_R302K", retry_on_fail=False,
                            max_rounds=8)
    assert r["status"] == "done" and r["rounds"] <= 4, (r,)
    assert "如实说明" in r["answer"], r["answer"]
