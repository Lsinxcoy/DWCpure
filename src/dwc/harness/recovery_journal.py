"""DWC-AUTO · 多组件产物事务的持久化 journal 与 committed-only canary。

所有状态先写 journal，再改目标；applying 是恢复时的整体回滚指令。
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from typing import Any

from dwc.organs import evo_targets as ET


class RecoveryError(Exception):
    """事务或恢复失败。"""


def _hash(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                     separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: str, value: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".%s." % os.path.basename(path),
                               suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class RecoveryJournal:
    """一个 JSON outbox 记录一个事务；replace 保证记录本身原子可见。"""

    def __init__(self, journal_path: str, backup_dir: str = ""):
        self.journal_path = os.path.abspath(journal_path)
        self.backup_dir = backup_dir
        self._tx_lock = self.journal_path + ".lock"

    def _save(self, record: dict[str, Any]) -> None:
        _atomic_json(self.journal_path, record)

    def _load(self) -> dict[str, Any]:
        try:
            with open(self.journal_path, encoding="utf-8") as f:
                record = json.load(f)
        except (OSError, ValueError) as exc:
            raise RecoveryError("journal 读不了: %r" % (exc,)) from exc
        if not isinstance(record, dict):
            raise RecoveryError("journal 必须是 JSON 对象")
        return record

    def canary(self, transaction_id: str) -> dict[str, dict[str, Any]]:
        """只有 committed 且目标哈希仍匹配的事务才允许发布。"""
        record = self._load()
        if record["transaction_id"] != transaction_id:
            raise RecoveryError("transaction_id 不匹配")
        if record["state"] != "committed":
            raise RecoveryError("canary 只允许 committed 事务")
        out = {}
        for target in record["targets"]:
            current = ET.read(target["component"])
            if _hash(current) != target["after_hash"]:
                raise RecoveryError("目标已漂移，拒绝 canary: %s" % target["component"])
            out[target["component"]] = current
        return out

    def apply(self, patches: dict[str, dict[str, Any]]) -> dict[str, Any]:
        record: dict[str, Any] = {
            "transaction_id": uuid.uuid4().hex,
            "state": "applying",
            "targets": [],
        }
        # 先持久化全部 undo 信息，再允许第一次目标写入。
        for component in sorted(patches):
            before = ET.read(component)
            created = not os.path.isfile(ET.path_of(component))
            backup = "" if created else ET.snapshot_backup(component, self.backup_dir)
            record["targets"].append({
                "component": component,
                "patch": patches[component],
                "before": before,
                "before_hash": _hash(before),
                "backup": backup,
                "created": created,
                "state": "applying",
            })
        self._save(record)
        try:
            for target in record["targets"]:
                component = target["component"]
                result = ET.apply(component, patches[component], self.backup_dir)
                target["after"] = result["after"]
                target["after_hash"] = _hash(result["after"])
                target["state"] = "applied"
                self._save(record)
            record["state"] = "committed"
            for target in record["targets"]:
                target["state"] = "committed"
            self._save(record)
            return record
        except Exception:
            self.rollback(record)
            raise

    def rollback(self, record: dict[str, Any]) -> dict[str, Any]:
        for target in reversed(record["targets"]):
            ET.rollback(target["component"], target["backup"])
            target["state"] = "rolled_back"
            self._save(record)
        record["state"] = "rolled_back"
        self._save(record)
        return record

    def recover(self) -> dict[str, Any]:
        """进程重启入口：只有 applying 需要整体逆序回滚。"""
        record = self._load()
        if record["state"] == "applying":
            return self.rollback(record)
        return record
