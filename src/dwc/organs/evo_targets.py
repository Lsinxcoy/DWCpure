"""evo_targets · 进化产物注册表（R438）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只做产物读写与校验，不做"决定改什么"——决策在 driver 层。

★★★ 存在理由
  审计（R437）结论：21 个进化对象里只有 `control_flow` 真能落地。
  其余维度不是"没写 mutator"，而是**没有产物文件**——就算起草了也无处可写。
  本模块给每个可编辑组件一个**真源文件 + schema + 消费者声明**。

★★★ 四条纪律（每项都对应一次踩坑）
  1. **白名单 schema**：只允许改登记过的键，值有类型与上下界。
     （否则"进化"能写任意 JSON，等于给 LLM 一个任意写盘口子。）
  2. **原子写**：tmp + os.replace。半截 JSON 会让下一个进程读崩。
  3. **先备份再写**：备份落 `var/backups/`，回滚有物证。
  4. **消费者必须存在**：`consumer` 字段写清谁读它；没有消费者的产物
     不许登记（那就是造了个没人读的 JSON —— R437 的教训）。

★ 本模块只做"读写 + 校验"，不做"决定改什么"——决策在 driver 层。
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))


def _p(rel: str) -> str:
    return os.path.join(ROOT, rel)


#: 组件 → 产物规格
#:   path     产物文件（相对仓库根）
#:   consumer 谁读它（必须真实存在，见模块头纪律 4）
#:   schema   key → (类型, 下界, 上界)；下界/上界为 None 表示不限
#:   defaults 缺文件时的默认值（**必须与消费者的硬编码默认一致**）
SPECS: dict[str, dict[str, Any]] = {
    "context_mgmt": {
        "path": "config/context_policy.json",
        "consumer": "dwc.llm.task_exec（read 默认行数 / search 默认条数）",
        "defaults": {"read_default_lines": 200, "search_limit": 60},
        "schema": {"read_default_lines": (int, 20, 2000),
                   "search_limit": (int, 10, 500)},
    },
    "client_tool": {
        "path": "config/tools_extra.json",
        "consumer": "dwc.llm.task_exec（TASK_TOOLS 合并）",
        "defaults": {"tools": []},
        "schema": {"tools": (list, 0, 8)},
    },
    "output_plumbing": {
        "path": "config/output_policy.json",
        "consumer": "dwc.llm.task_exec（最终答案截断）",
        "defaults": {"max_answer_chars": 6000},
        "schema": {"max_answer_chars": (int, 500, 20000)},
    },
    "config": {
        "path": "config/tunables.json",
        "consumer": "scripts/dwc_agent.py（interval/steps/预算默认值）",
        "defaults": {"interval": 600.0, "steps": 2,
                     "terms_per_day": 96.0, "budget_day": 80.0},
        "schema": {"interval": (float, 30.0, 3600.0),
                   "steps": (int, 1, 10),
                   "terms_per_day": (float, 8.0, 400.0),
                   "budget_day": (float, 8.0, 400.0)},
    },
    "subagent": {
        "path": "config/subagent_policy.json",
        "consumer": "dwc.caps.registry.cap_limit（delegate 超时/开关覆盖）",
        "defaults": {"timeout_s": 600},
        "schema": {"timeout_s": (int, 60, 1800)},
    },
}


class TargetError(Exception):
    """产物读写/校验错误（**大声**，不静默降级）。"""


def spec_of(component: str) -> dict[str, Any]:
    s = SPECS.get(component)
    if s is None:
        raise TargetError("组件 %r 没有登记产物（可编辑≠有落地面）"
                          % (component,))
    return s


def path_of(component: str) -> str:
    return _p(spec_of(component)["path"])


def read(component: str) -> dict[str, Any]:
    """读产物；文件不存在 ⇒ 返回 defaults 副本（不写盘）。"""
    s = spec_of(component)
    out = dict(s["defaults"])
    p = path_of(component)
    if not os.path.isfile(p):
        return out
    try:
        with open(p, encoding="utf-8") as f:
            got = json.load(f)
    except (OSError, ValueError) as exc:
        raise TargetError("产物读不了 %s: %r" % (p, exc))
    if not isinstance(got, dict):
        raise TargetError("产物必须是 JSON 对象: %s" % (p,))
    out.update(got)
    return out


def validate(component: str, patch: dict[str, Any]) -> list[str]:
    """白名单 + 类型 + 上下界。返回错误列表（空 = 合格）。"""
    s = spec_of(component)
    errs: list[str] = []
    if not isinstance(patch, dict):
        return ["patch 必须是 dict，实为 %r" % (type(patch).__name__,)]
    for k, v in patch.items():
        if k not in s["schema"]:
            errs.append("未知键 %r（白名单：%s）"
                        % (k, sorted(s["schema"])))
            continue
        typ, lo, hi = s["schema"][k]
        if typ is bool:
            if not isinstance(v, bool):
                errs.append("%s 须为 bool，实为 %r" % (k, v))
            continue
        if typ is int and isinstance(v, bool):
            errs.append("%s 须为 int（bool 不算），实为 %r" % (k, v))
            continue
        if typ is float and isinstance(v, bool):
            errs.append("%s 须为 float（bool 不算），实为 %r" % (k, v))
            continue
        if not isinstance(v, (int, float)):
            errs.append("%s 须为数字，实为 %r" % (k, v))
            continue
        if lo is not None and v < lo:
            errs.append("%s=%r 低于下界 %r" % (k, v, lo))
        if hi is not None and v > hi:
            errs.append("%s=%r 高于上界 %r" % (k, v, hi))
        if typ is int and isinstance(v, float) and not float(v).is_integer():
            errs.append("%s 须为整数，实为 %r" % (k, v))
    return errs


@contextmanager
def _target_lock(component: str):
    """跨进程/线程互斥；锁文件与目标同目录，绝不锁 replace 的目标本身。"""
    p = path_of(component)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    lock_path = p + ".lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if os.name == "nt":
            import msvcrt
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _atomic_bytes(path: str, payload: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=".%s." % os.path.basename(path),
                               suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _atomic_write(path: str, data: dict[str, Any]) -> None:
    """同目录唯一临时文件 + replace；失败清理且不碰旧文件。"""
    fd, tmp = tempfile.mkstemp(prefix=".%s." % os.path.basename(path),
                               suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _apply_locked(component: str, patch: dict[str, Any],
                  backup_dir: str = "") -> dict[str, Any]:
    """调用者必须持有目标锁。"""
    p = path_of(component)
    before = read(component)
    after = dict(before)
    after.update(patch)
    created = not os.path.isfile(p)
    bak = ""
    if not created:
        bd = backup_dir or _p(os.path.join("var", "backups"))
        os.makedirs(bd, exist_ok=True)
        bak = os.path.join(bd, "%s_%s_%s.json"
                           % (component, time.strftime("%Y%m%d_%H%M%S"),
                              uuid.uuid4().hex))
        shutil.copy2(p, bak)
    _atomic_write(p, after)
    got = read(component)
    if got != after:
        raise TargetError("读回不一致：写入 %r，读回 %r" % (after, got))
    return {"outcome": "applied", "component": component, "path": p,
            "before": before, "after": after, "backup": bak,
            "created": created}


def snapshot_backup(component: str, backup_dir: str = "") -> str:
    """在任何写入前复制当前文件；首次创建返回空路径。"""
    p = path_of(component)
    if not os.path.isfile(p):
        return ""
    bd = backup_dir or _p(os.path.join("var", "backups"))
    os.makedirs(bd, exist_ok=True)
    bak = os.path.join(bd, "%s_%s_%s.json" %
                       (component, time.strftime("%Y%m%d_%H%M%S"),
                        uuid.uuid4().hex))
    shutil.copy2(p, bak)
    return bak


def apply(component: str, patch: dict[str, Any],
          backup_dir: str = "") -> dict[str, Any]:
    """合并 + 校验 + 唯一备份 + 原子写 + 读回，整段跨进程互斥。"""
    errs = validate(component, patch)
    if errs:
        raise TargetError("; ".join(errs))
    with _target_lock(component):
        return _apply_locked(component, patch, backup_dir)


def update(component: str, mutator: Callable[[dict[str, Any]], dict[str, Any]],
           *, backup_dir: str = "") -> dict[str, Any]:
    """在锁内由当前值计算 patch，避免调用方 read/apply 之间丢更新。"""
    with _target_lock(component):
        patch = mutator(read(component))
        errs = validate(component, patch)
        if errs:
            raise TargetError("; ".join(errs))
        return _apply_locked(component, patch, backup_dir)


def rollback(component: str, backup_path: str) -> dict[str, Any]:
    """备份整份原子还原；空备份路径明确表示撤销首次创建。"""
    p = path_of(component)
    with _target_lock(component):
        if not backup_path:
            if os.path.isfile(p):
                os.unlink(p)
            if os.path.exists(p):
                raise TargetError("首次创建回滚失败，文件仍存在: %s" % (p,))
            return {"outcome": "rolled_back", "component": component,
                    "path": p, "restored_from": "", "removed": True}
        if not os.path.isfile(backup_path):
            raise TargetError("备份不存在: %r" % (backup_path,))
        with open(backup_path, "rb") as f:
            payload = f.read()
        data = json.loads(payload.decode("utf-8"))
        if not isinstance(data, dict):
            raise TargetError("备份必须是 JSON 对象: %s" % (backup_path,))
        _atomic_bytes(p, payload)
        got = read(component)
        if got != dict(spec_of(component)["defaults"], **data):
            raise TargetError("回滚读回不一致：写入 %r，读回 %r" % (data, got))
    return {"outcome": "rolled_back", "component": component,
            "path": p, "restored_from": backup_path, "removed": False}


def smoke(component: str) -> dict[str, Any]:
    """消费者冒烟：产物里的值能不能被消费者读到。

    ★ 这不是"效果验证"，只是"接线验证" —— 别把它当试验通过。
    """
    got = read(component)
    if component == "context_mgmt":
        from dwc.llm import task_exec as T
        fn = getattr(T, "read_default_lines", None)
        if fn is None:
            return {"ok": False, "why": "task_exec 没有 read_default_lines"}
        return {"ok": int(fn()) == int(got["read_default_lines"]),
                "consumer_saw": fn(), "file": got["read_default_lines"]}
    if component == "client_tool":
        from dwc.llm import task_exec as T
        names = {t.get("function", {}).get("name")
                 for t in getattr(T, "TASK_TOOLS", [])}
        want = {t.get("function", {}).get("name") for t in got["tools"]}
        return {"ok": want.issubset(names), "missing": sorted(want - names)}
    if component == "output_plumbing":
        from dwc.llm import task_exec as T
        fn = getattr(T, "output_max_chars", None)
        if fn is None:
            return {"ok": False, "why": "task_exec 没有 output_max_chars"}
        return {"ok": int(fn()) == int(got["max_answer_chars"]),
                "consumer_saw": fn(), "file": got["max_answer_chars"]}
    if component == "config":
        return {"ok": True, "why": "dwc_agent 在启动时读取（本进程不可见）"}
    return {"ok": False, "why": "未实现 smoke: %s" % component}
