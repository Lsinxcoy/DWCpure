"""DWC-AUTO · Isolated sparse candidate trees; production application is deliberately absent."""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
from typing import Any, Mapping


class WorkspaceError(ValueError):
    pass


class CandidateWorkspace:
    def __init__(self, production_root: str | Path, shadow_root: str | Path):
        self.production_root = Path(production_root).resolve()
        self.shadow_root = Path(shadow_root).resolve()
        if self.shadow_root == self.production_root or self.shadow_root.is_relative_to(self.production_root):
            raise WorkspaceError("shadow root must be outside production")
        self.shadow_root.mkdir(parents=True, exist_ok=True)

    def _relative(self, name: str) -> Path:
        normalized = str(name).replace("\\", "/")
        rel = PurePosixPath(normalized)
        if rel.is_absolute() or ".." in rel.parts or not rel.parts or any(part in ("", ".") for part in rel.parts):
            raise WorkspaceError(f"invalid candidate path: {name}")
        return Path(*rel.parts)

    def create(self, candidate_id: str, edits: Mapping[str, str | bytes | None]) -> Path:
        target = (self.shadow_root / candidate_id).resolve()
        if not target.is_relative_to(self.shadow_root) or target == self.shadow_root:
            raise WorkspaceError("invalid candidate id")
        if target.exists():
            raise WorkspaceError("candidate workspace already exists")
        shutil.copytree(self.production_root, target, symlinks=True)
        for name, content in edits.items():
            relative = self._relative(name)
            path = (target / relative).resolve()
            if not path.is_relative_to(target):
                raise WorkspaceError("candidate path escapes shadow")
            if content is None:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                path.write_text(content, encoding="utf-8")
            else:
                path.write_bytes(content)
        return target

    def artifact_manifest(self, candidate_id: str) -> dict[str, Any]:
        root = (self.shadow_root / candidate_id).resolve()
        if not root.is_relative_to(self.shadow_root) or not root.is_dir():
            raise WorkspaceError("candidate workspace missing")
        files = []
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            files.append({"path": path.relative_to(root).as_posix(),
                          "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        return {"candidate_id": candidate_id, "kind": "shadow", "files": files}

    def rollback(self, candidate_id: str) -> str:
        root = (self.shadow_root / candidate_id).resolve()
        if not root.is_relative_to(self.shadow_root):
            raise WorkspaceError("invalid candidate id")
        shutil.rmtree(root, ignore_errors=True)
        return "shadow_removed"

    def commit(self, candidate_id: str) -> None:
        raise PermissionError("production commit is forbidden: candidate workspaces are shadow-only")
