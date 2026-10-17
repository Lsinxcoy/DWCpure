# -*- coding: utf-8 -*-
"""R303-⑥ Browser取证：qa加web_read权+final编URL打回。零真实联网。"""
import tempfile

from dwc.llm.step_judge import judge_step, verify_final_refs


def test_qa_web_read_allowed():
    v, why, rid = judge_step({"op": "web_read", "url": "https://x.com/a"}, [], qa_mode=True)
    assert not (v == "noisy" and rid == "R5")


def test_nonqa_unchanged():
    v, why, rid = judge_step({"op": "run", "cmd": "ls"}, [], qa_mode=False)
    assert isinstance((v, why, rid), tuple)


def test_final_fake_url_blocked():
    with tempfile.TemporaryDirectory() as td:
        err = verify_final_refs("见 https://evil.example/none 和 config/a.md 第1行“依据”",
                                td, obs_urls=("https://real.example/a",))
    assert isinstance(err, str) and err


def test_final_real_url_pass():
    import os
    with tempfile.TemporaryDirectory() as td:
        os.makedirs(os.path.join(td, "config"))
        p = os.path.join(td, "config", "a.md")
        open(p, "w", encoding="utf-8").write("依据文本内容在此处可见\n")
        err = verify_final_refs("见 config/a.md 第1行“依据文本内容”及 https://real.example/a",
                                td, obs_urls=("https://real.example/a",))
    assert err is None
