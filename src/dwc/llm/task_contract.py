# -*- coding: utf-8 -*-
"""TaskContract · 可验证的任务完成条件（P0）。

★★★ 定位（G1 定位门）: **DWC-AUTO** —— 任务执行完成判定层，不是记忆底座。
★★★ TRUTH_SOURCE（G2）: 产物真值来自文件系统（`os.path.isfile` + 非空），
   命令真值来自 `actions_log` 的成功回执；答案真值来自任务结果本身。
   本模块不产 epoch 评分、不替代 judge、不硬编码成功。

设计原则（与 DWC 现有语义兼容）：

- **纯问答**：只要求非空答案，不要求产物/命令。
- **写任务**：任务文本明确出现“写/写入/创建/生成/保存/修改”等意图时，
  必须有一个非空产物；产物来自 `artifacts` 或 `actions_log` 中成功的
  `write` 动作目标。
- **运行任务**：任务文本明确出现“运行/跑/执行/run/pytest”等意图时，
  必须有一条成功的 `run/test/check` 观察。
- 不把“测试任务”这种词当成运行意图；必须有执行动词。
- 契约失败只把 `done` 降为 `incomplete`，不删除已有答案/产物，便于诊断。

这不是模型自述的“完成”，而是可复查的完成条件。
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

#: 写意图。避免只匹配单个“写”字导致“描述/撰写建议”误判；
#: 这些词都要求落盘或改文件。
_WRITE_INTENT = re.compile(
    r"(写(?:一个|一份|入|进|到|成|下|回)|写入|写到|写进|创建|新建|生成|保存|"
    r"修改|替换|追加|落盘|write\s|create\s|save\s|append\s|apply_patch)",
    re.IGNORECASE,
)

#: 运行意图。必须出现执行动词；单独的“测试”/“pytest”不算。
#: 现场：readme 题面含“pytest 那一行”，旧规则把“找数字”误判成“跑 pytest”。
_RUN_INTENT = re.compile(
    r"(运行|跑(?:一下|一遍|起来)?|执行|试跑|"
    r"run\s|execute\s|make\s+test|npm\s+test|go\s+test)",
    re.IGNORECASE,
)

#: 题面明确指定的输出路径（DWC 写区）。用于区分“真产物”和“顺手写的脚本”。
_OUTPUT_PATH = re.compile(
    r"(?:var[/\\]inbox_work[/\\][\w.\-]+)", re.IGNORECASE)

#: 成功观察里算“验证”的动作。
_VERIFY_OPS = frozenset({"run", "test", "check", "verify"})

#: 写动作。
_WRITE_OPS = frozenset({"write", "edit", "apply_patch", "patch"})


@dataclass(frozen=True)
class TaskContract:
    goal: str
    checks: tuple[str, ...]
    write_intent: bool
    run_intent: bool
    qa_mode: bool
    max_rounds: int
    root: str = ""
    artifacts: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_task(cls, task: str, *, qa_mode: bool = False,
                  max_rounds: int = 999, root: str = "") -> "TaskContract":
        text = str(task or "")
        # 问答任务不做写/运行约束；问答的答案质量由既有 qa 闸负责。
        write_intent = bool(_WRITE_INTENT.search(text)) and not qa_mode
        run_intent = bool(_RUN_INTENT.search(text)) and not qa_mode
        expected = tuple(dict.fromkeys(
            m.group(0).replace("\\", "/") for m in _OUTPUT_PATH.finditer(text)))
        checks: list[str] = []
        if write_intent:
            checks.append("artifact_exists")
        # 写脚本 + “运行后打印”：脚本本身是可验证产物，verifier 会独立运行；
        # 不再强制要求 agent 在本次轨迹里额外跑一遍。若题面另有输出文件
        # （如“运行后写进 out.txt”），expected 不是纯 .py，仍要求 verification。
        script_only = (write_intent and run_intent and expected
                       and all(p.lower().endswith(".py") for p in expected))
        if run_intent and not script_only:
            checks.append("verification_ok")
        if not checks:
            checks.append("answer_nonempty")
        return cls(
            goal=text[:500],
            checks=tuple(checks),
            write_intent=write_intent,
            run_intent=run_intent,
            qa_mode=bool(qa_mode),
            max_rounds=int(max_rounds),
            root=root or "",
            artifacts=expected,
        )

    # ── 证据提取 ────────────────────────────────────────────────
    def _resolve(self, path: str) -> str:
        p = str(path or "").strip()
        if not p:
            return ""
        if os.path.isabs(p):
            return p
        return os.path.join(self.root, p) if self.root else p

    def _nonempty_file(self, path: str) -> bool:
        p = self._resolve(path)
        try:
            return bool(p) and os.path.isfile(p) and os.path.getsize(p) > 0
        except OSError:
            return False

    def _log(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        raw = result.get("actions_log")
        return [e for e in raw if isinstance(e, dict)] if isinstance(raw, list) else []

    def _artifact_paths(self, result: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for a in result.get("artifacts") or []:
            if isinstance(a, str) and a.strip():
                out.append(a.strip())
        for e in self._log(result):
            if e.get("op") in _WRITE_OPS and e.get("ok") is True:
                t = str(e.get("target") or "").strip()
                if t:
                    out.append(t)
        # 去重但保序
        seen: set[str] = set()
        return [x for x in out if not (x in seen or seen.add(x))]

    def _has_verification(self, result: dict[str, Any]) -> bool:
        for e in self._log(result):
            if e.get("op") in _VERIFY_OPS and e.get("ok") is True:
                return True
        return False

    # ── 判定 ────────────────────────────────────────────────────
    def evaluate(self, result: dict[str, Any]) -> dict[str, Any]:
        artifacts = self._artifact_paths(result)
        existing = [p for p in artifacts if self._nonempty_file(p)]
        expected_existing = [p for p in self.artifacts if self._nonempty_file(p)]
        answer = str(result.get("answer") or "").strip()
        evidence = {
            "n_artifacts": len(artifacts),
            "n_artifacts_nonempty": len(existing),
            "artifact_paths": existing[:8],
            "expected_artifacts": list(self.artifacts),
            "expected_nonempty": expected_existing,
            "verification_ok": self._has_verification(result),
            "answer_chars": len(answer),
        }
        checks: dict[str, bool] = {}
        for name in self.checks:
            if name == "artifact_exists":
                # 题面指定了输出路径 ⇒ 必须是指定文件非空；
                # 否则（“写一个清单”这类无路径任务）才接受任意成功产物。
                checks[name] = (bool(expected_existing) if self.artifacts
                                else bool(existing))
            elif name == "verification_ok":
                checks[name] = bool(evidence["verification_ok"])
            elif name == "answer_nonempty":
                checks[name] = len(answer) >= 1
            elif name == "diff_nonempty":
                # 当前没有统一 diff 对象；有成功写动作即视为非空改动。
                checks[name] = bool(existing) or any(
                    e.get("op") in _WRITE_OPS and e.get("ok") is True
                    for e in self._log(result))
            else:
                checks[name] = False
        missing = [k for k, v in checks.items() if not v]
        return {"ok": not missing, "checks": checks, "missing": missing,
                "evidence": evidence}

    def as_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "checks": list(self.checks),
            "write_intent": self.write_intent,
            "run_intent": self.run_intent,
            "qa_mode": self.qa_mode,
            "max_rounds": self.max_rounds,
            "expected_artifacts": list(self.artifacts),
        }
