# -*- coding: utf-8 -*-
"""dwc_benchmark_longterm.py · Phase 4 长期评测 (稳定 eval set + 历史追踪)。"""
import argparse, json, os, subprocess, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import dwc_benchmark_adapter as A

HISTORY = os.path.join(ROOT, "var", "bench_history.jsonl")
EVAL_SET = os.path.join(ROOT, "config", "bench_eval_set.json")
EVAL_PATCH = os.path.join(ROOT, "config", "bench_eval_set_patch.json")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval-set", default=EVAL_SET)
    ap.add_argument("--patches", default=EVAL_PATCH)
    ap.add_argument("--work-root", default=os.path.join(ROOT, "var", "bench_longterm_work"))
    ap.add_argument("--out", default=os.path.join(ROOT, "var", "bench_longterm_report.json"))
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # 清理 work root
    import shutil
    if os.path.exists(args.work_root):
        shutil.rmtree(args.work_root, ignore_errors=True)

    # 调 adapter CLI
    cmd = [sys.executable, os.path.join(ROOT, "scripts", "dwc_benchmark_adapter.py"),
           "--instances", args.eval_set, "--patches", args.patches,
           "--out", args.out, "--work-root", args.work_root]
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip())
    if r.returncode != 0:
        print("adapter failed:", r.stderr[-500:])
        sys.exit(r.returncode)

    rep = json.load(open(args.out, encoding="utf-8"))
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n": rep.get("total", 0),
        "resolved": rep.get("resolved", 0),
        "rate": rep.get("resolved_rate", rep.get("rate", 0.0)),
    }
    os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # 趋势
    hist = []
    if os.path.exists(HISTORY):
        with open(HISTORY, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    hist.append(json.loads(line))
    print("history runs:", len(hist))
    for h in hist[-5:]:
        print("  ", h["ts"], h["resolved"], "/", h["n"], "=", round(h["rate"], 3))

if __name__ == "__main__":
    main()
