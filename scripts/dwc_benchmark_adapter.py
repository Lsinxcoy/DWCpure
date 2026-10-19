# -*- coding: utf-8 -*-
"""★ Phase 2.1 · DWC benchmark adapter (SWE-bench 风格, 轻量版).

无 docker / 无 swebench 依赖: 用 git + pytest 在本地仓库上跑 FAIL_TO_PASS。
支持:
  - 从 JSON/JSONL 加载 instance 列表
  - checkout base_commit + apply test_patch + apply agent patch
  - 运行 FAIL_TO_PASS / PASS_TO_PASS, 计算 resolved
  - 产出 benchmark_report.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class BenchInstance:
    instance_id: str
    repo: str                      # "owner/repo" 或本地路径
    base_commit: str
    patch: str = ""                # gold/agent patch (可空, 由外部提供)
    test_patch: str = ""
    FAIL_TO_PASS: List[str] = None
    PASS_TO_PASS: List[str] = None

    def __post_init__(self):
        if self.FAIL_TO_PASS is None:
            self.FAIL_TO_PASS = []
        if self.PASS_TO_PASS is None:
            self.PASS_TO_PASS = []


def load_instances(path: str) -> List[BenchInstance]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError("instances file not found: %s" % path)
    items: List[Dict[str, Any]] = []
    if p.suffix.lower() == ".jsonl":
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                items.append(json.loads(line))
    else:
        data = json.loads(p.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("instances", [])
    out: List[BenchInstance] = []
    for it in items:
        out.append(BenchInstance(
            instance_id=it.get("instance_id", it.get("id", "unknown")),
            repo=it.get("repo", ""),
            base_commit=it.get("base_commit", "HEAD"),
            patch=it.get("patch", ""),
            test_patch=it.get("test_patch", ""),
            FAIL_TO_PASS=list(it.get("FAIL_TO_PASS", []) or []),
            PASS_TO_PASS=list(it.get("PASS_TO_PASS", []) or []),
        ))
    return out


def _run(cmd: List[str], cwd: str, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def _git(repo_path: str, *args: str) -> subprocess.CompletedProcess:
    return _run(["git", *args], cwd=repo_path)


def ensure_repo(instance: BenchInstance, work_root: str) -> str:
    """checkout base_commit 到 work_root/<slug>, 返回 repo 路径。"""
    if os.path.isdir(instance.repo) and os.path.exists(os.path.join(instance.repo, ".git")):
        src = instance.repo
        slug = os.path.basename(src.rstrip("/\\"))
    else:
        slug = instance.repo.replace("/", "__")
        src = None
    dest = os.path.join(work_root, slug + "__" + instance.base_commit[:8])
    if not os.path.exists(dest):
        if src is None:
            url = "https://github.com/%s.git" % instance.repo
            r = _run(["git", "clone", url, dest], cwd=work_root, timeout=600)
            if r.returncode != 0:
                raise RuntimeError("clone failed: %s" % r.stderr)
        else:
            # 本地仓库: 复制 (shallow copy via clone local)
            r = _run(["git", "clone", src, dest], cwd=work_root, timeout=300)
            if r.returncode != 0:
                raise RuntimeError("local clone failed: %s" % r.stderr)
    # checkout base commit (clean)
    _git(dest, "fetch", "--all", "--tags")
    r = _git(dest, "checkout", "--force", instance.base_commit)
    if r.returncode != 0:
        # maybe already
        pass
    _git(dest, "clean", "-fdx")
    return dest


def apply_patch(repo_path: str, patch_text: str) -> Dict[str, Any]:
    if not patch_text or not patch_text.strip():
        return {"applied": True, "skipped": True}
    # 写入临时 patch 文件
    fd, pth = tempfile.mkstemp(suffix=".patch")
    os.close(fd)
    Path(pth).write_text(patch_text, encoding="utf-8")
    r = _run(["git", "apply", "--whitespace=nowarn", pth], cwd=repo_path)
    os.remove(pth)
    return {"applied": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr,
            "returncode": r.returncode}


def run_tests(repo_path: str, test_ids: List[str], timeout: int = 300) -> Dict[str, Any]:
    if not test_ids:
        return {"passed": 0, "failed": 0, "total": 0, "all_passed": True, "output": ""}
    cmd = [sys.executable, "-m", "pytest", "-q", "--no-header", "-p", "no:cacheprovider", *test_ids]
    r = _run(cmd, cwd=repo_path, timeout=timeout)
    # pytest exit: 0 all passed, 1 failures, 5 no tests
    passed = 0
    failed = 0
    for line in (r.stdout + r.stderr).splitlines():
        # 简单计数: "X passed, Y failed"
        pass
    # 解析 summary 行
    import re
    m = re.search(r"(\d+)\s+passed", r.stdout + r.stderr)
    if m:
        passed = int(m.group(1))
    m2 = re.search(r"(\d+)\s+failed", r.stdout + r.stderr)
    if m2:
        failed = int(m2.group(1))
    total = passed + failed
    if total == 0:
        # fallback: exit code
        all_passed = r.returncode == 0
    else:
        all_passed = (failed == 0 and r.returncode == 0)
    return {"passed": passed, "failed": failed, "total": total,
            "all_passed": all_passed, "returncode": r.returncode,
            "output": (r.stdout + r.stderr)[-2000:]}


def evaluate_instance(instance: BenchInstance, agent_patch: str, work_root: str) -> Dict[str, Any]:
    os.makedirs(work_root, exist_ok=True)
    repo_path = ensure_repo(instance, work_root)
    # apply test_patch first (测试侧变更)
    tp = apply_patch(repo_path, instance.test_patch)
    # apply agent patch
    ap = apply_patch(repo_path, agent_patch if agent_patch else instance.patch)
    if not ap.get("applied", False) and not ap.get("skipped", False):
        return {"instance_id": instance.instance_id, "resolved": False,
                "reason": "patch_apply_failed", "apply": ap, "repo_path": repo_path}
    # run FAIL_TO_PASS
    f2p = run_tests(repo_path, instance.FAIL_TO_PASS)
    p2p = run_tests(repo_path, instance.PASS_TO_PASS) if instance.PASS_TO_PASS else {"all_passed": True}
    resolved = bool(f2p.get("all_passed")) and bool(p2p.get("all_passed"))
    return {
        "instance_id": instance.instance_id,
        "resolved": resolved,
        "FAIL_TO_PASS": f2p,
        "PASS_TO_PASS": p2p,
        "repo_path": repo_path,
    }


def run_benchmark(instances: List[BenchInstance], agent_patches: Optional[Dict[str, str]] = None,
                  work_root: Optional[str] = None, limit: int = 0) -> Dict[str, Any]:
    agent_patches = agent_patches or {}
    if work_root is None:
        work_root = tempfile.mkdtemp(prefix="dwc_bench_")
    os.makedirs(work_root, exist_ok=True)
    os.makedirs(work_root, exist_ok=True)
    if limit and limit > 0:
        instances = instances[:limit]
    results = []
    resolved_n = 0
    for ins in instances:
        patch = agent_patches.get(ins.instance_id, "")
        try:
            r = evaluate_instance(ins, patch, work_root)
        except Exception as e:  # noqa: BLE001 — 单实例失败不掀全跑
            r = {"instance_id": ins.instance_id, "resolved": False, "error": str(e)}
        results.append(r)
        if r.get("resolved"):
            resolved_n += 1
    total = len(results)
    report = {
        "total": total,
        "resolved": resolved_n,
        "resolved_rate": (resolved_n / total) if total else 0.0,
        "work_root": work_root,
        "results": results,
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True, help="JSON/JSONL path")
    ap.add_argument("--patches", default="", help="JSON mapping instance_id->patch")
    ap.add_argument("--out", default="benchmark_report.json")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--work-root", default="")
    args = ap.parse_args()

    instances = load_instances(args.instances)
    patches = {}
    if args.patches and os.path.exists(args.patches):
        patches = json.loads(Path(args.patches).read_text(encoding="utf-8"))
    work_root = args.work_root or None
    report = run_benchmark(instances, patches, work_root, args.limit)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("total=%d resolved=%d rate=%.3f" % (report["total"], report["resolved"], report["resolved_rate"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())