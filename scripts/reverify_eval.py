# -*- coding: utf-8 -*-
"""reverify_eval · 从 session answer 用当前判据重验（判据修正后两臂统一重验）。

用法: python scripts/reverify_eval.py run_A_xxx.jsonl run_B_xxx.jsonl
覆盖写回 ok/verify 字段（判据历史: 初判据错 3 处 rf03/rv10/an09, Layer-22 修正）。
"""
import io, json, os, sys, importlib.util
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
spec = importlib.util.spec_from_file_location("dwc_bench2",
    os.path.join(ROOT, "scripts", "dwc_bench2.py"))
B2 = importlib.util.module_from_spec(spec); spec.loader.exec_module(B2)
TASKS = {json.loads(l)["id"]: json.loads(l)
         for l in io.open(os.path.join(ROOT, "config", "eval_tasks.jsonl"),
                          encoding="utf-8")}
for run_p in sys.argv[1:]:
    rows = [json.loads(l) for l in io.open(run_p, encoding="utf-8")]
    changed = 0
    for r in rows:
        t = TASKS.get(r["id"])
        if not t:
            continue
        sp = os.path.join(ROOT, "var", "dwc_sessions",
                          "eval_%s_%s.jsonl" % (r.get("arm", "A"), r["id"]))
        ans = ""
        acts = []
        if os.path.exists(sp):
            for l in io.open(sp, encoding="utf-8"):
                try:
                    d = json.loads(l)
                except ValueError:
                    continue
                # ★ R388 · 重建 actions_log（离线复核也需要 agent 证据，
                #   否则 rc_and_contains 会被判 no-agent-evidence）
                if d.get("phase") == "obs":
                    acts.append(d)
                if d.get("op") == "final" and d.get("answer") is not None:
                    ans = str(d["answer"])
        rep = dict(r)
        rep["actions_log"] = acts
        ok, how = B2.verify(t["check"], ans, report=rep)
        if ok != r["ok"]:
            changed += 1
        r["ok"], r["verify"] = ok, how
    with io.open(run_p, "w", encoding="utf-8", newline="\n") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    n_ok = sum(1 for r in rows if r["ok"])
    print("%s: %d/%d（判据修正改变 %d 单）"
          % (os.path.basename(run_p), n_ok, len(rows), changed))
