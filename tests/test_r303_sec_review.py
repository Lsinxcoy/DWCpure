# -*- coding: utf-8 -*-
"""R303-① PR级Security Review：纯规则六类漏洞，只报可利用，零LLM。"""
from dwc.llm.sec_review import review_diff


def test_sql_injection():
    out = review_diff('q = "SELECT * FROM u WHERE id=%s" % uid\n')
    assert any(i["cls"] == "SQL注入" for i in out)


def test_cmd_injection():
    out = review_diff("os.system('ls ' + name)\n")
    assert any(i["cls"] == "命令注入" for i in out)


def test_template_injection():
    out = review_diff("render_template_string('<h1>' + title + '</h1>')\n")
    assert any(i["cls"] == "模板注入" for i in out)


def test_auth_bypass():
    out = review_diff("requests.get(u, verify=False)\n")
    assert any(i["cls"] == "鉴权绕过" for i in out)


def test_secret_in_code():
    out = review_diff('api_key = "sk-live-abc123xyz"\n')
    assert any(i["cls"] == "密钥入库" for i in out)


def test_ssrf():
    out = review_diff("requests.get(url_from_user)\n")
    assert any(i["cls"] == "SSRF" for i in out)


def test_noise_tests_dir():
    out = review_diff("os.system('ls')\n", path="tests/test_x.py")
    assert out == []


def test_noise_comment():
    out = review_diff("# os.system('ls ' + name) 只是注释\n")
    assert out == []


def test_noise_param_query():
    out = review_diff('cur.execute("SELECT * FROM u WHERE id=%s", (uid,))\n')
    assert out == []


def test_deserialize():
    out = review_diff("obj = pickle.loads(data)\n")
    assert any(i["cls"] == "反序列化" for i in out)


def test_pinned_dep_ok():
    out = review_diff("requests==2.31.0\n", path="requirements.txt")
    assert out == []


def test_unpinned_dep():
    out = review_diff("requests\n", path="requirements.txt")
    assert any(i["cls"] == "问题依赖" for i in out)
