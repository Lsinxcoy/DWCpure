# -*- coding: utf-8 -*-
"""dwc_benchmark_calibrate.py · Phase 3.1 校准 CLI。"""
import argparse, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.benchmark_fitness import write_calibration

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", default=os.path.join(ROOT, "var", "bench_phase23_report.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "var", "bench_calibration.json"))
    ap.add_argument("--internal", type=float, default=None, help="内部 pass_rate (可选)")
    args = ap.parse_args()
    sig = write_calibration(args.report, args.out, args.internal)
    print(json.dumps(sig, ensure_ascii=False))

if __name__ == "__main__":
    main()
