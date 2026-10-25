"""DWC-AUTO · Content-addressed run identity and crash-safe completion/resume markers."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

SCHEMA_VERSION = "1"


def content_fingerprint(value: str | Path | bytes | bytearray | Mapping[str, Any]) -> str:
    if isinstance(value, (str, Path)):
        data = Path(value).read_bytes()
    elif isinstance(value, (bytes, bytearray)):
        data = bytes(value)
    elif isinstance(value, Mapping):
        data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    else:
        raise TypeError("fingerprint requires path, bytes, or a mapping")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class RunIdentity:
    run_id: str
    task_id: str
    protocol_id: str
    component_hash: str
    artifact_fingerprint: str
    solver_id: str
    model_id: str
    evaluator_version: str


class RunMarkerStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def marker_path(self, identity: RunIdentity) -> Path:
        return self.root / f"{identity.run_id}.complete.json"

    def _result_path(self, identity: RunIdentity) -> Path:
        return self.root / f"{identity.run_id}.result"

    def run(self, identity: RunIdentity, runner: Callable[[], Any]) -> Any:
        self.marker_path(identity).unlink(missing_ok=True)
        try:
            result = runner()
        except Exception:
            self._result_path(identity).unlink(missing_ok=True)
            return None
        if not isinstance(result, (str, bytes)):
            raise TypeError("runner result must be text or bytes")
        data = result.encode() if isinstance(result, str) else result
        self._result_path(identity).write_bytes(data)
        marker = {"schema_version": SCHEMA_VERSION, "runner_normal_exit": True,
                  **asdict(identity)}
        temp = self.marker_path(identity).with_suffix(".tmp")
        temp.write_text(json.dumps(marker, sort_keys=True), encoding="utf-8")
        temp.replace(self.marker_path(identity))
        return result

    def resume(self, identity: RunIdentity, artifact: str | Path) -> str | None:
        marker_path = self.marker_path(identity)
        result_path = self._result_path(identity)
        if not marker_path.is_file() or not result_path.is_file() or not Path(artifact).is_file():
            return None
        try:
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            expected = {"schema_version": SCHEMA_VERSION, "runner_normal_exit": True, **asdict(identity)}
            if marker != expected:
                return None
            if content_fingerprint(artifact) != identity.artifact_fingerprint:
                return None
            return result_path.read_text(encoding="utf-8")
        except (OSError, ValueError, TypeError):
            return None
