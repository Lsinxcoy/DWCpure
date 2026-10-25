"""DWC-AUTO · Eight DWC component consumers and safe sparse materialization (section 6.3)."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
from typing import Any, Iterable, Mapping


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class ComponentSpec:
    consumer: str
    allowed_roots: tuple[str, ...]
    activation: str


COMPONENT_MANIFEST: dict[str, ComponentSpec] = {
    "system prompt": ComponentSpec("prompt_ota", ("prompts/",), "always_on"),
    "guardrails": ComponentSpec("hook", ("guardrails/",), "always_on"),
    "memory": ComponentSpec("memory/agent_quality", ("memory/",), "on_demand"),
    "tool guidance": ComponentSpec("context_mgmt/client_tool", ("tool_guidance/",), "always_on"),
    "subagents": ComponentSpec("subagent_policy/caps", ("subagents/",), "on_demand"),
    "skills": ComponentSpec("skill_store/dwc_skills", ("skills/",), "on_demand"),
    "scripts": ComponentSpec("shadow_sandbox", ("scripts/",), "on_demand"),
    "plugin/hooks": ComponentSpec("agent_harness", ("plugin/", "hooks/"), "always_on"),
}


@dataclass(frozen=True)
class ManifestEntry:
    path: str
    action: str
    sha256: str | None


@dataclass(frozen=True)
class MaterializedManifest:
    entries: tuple[ManifestEntry, ...]
    content_hash: str

    def verify(self, root: str | Path) -> bool:
        base = Path(root)
        rows = []
        for entry in self.entries:
            target = base / entry.path
            if entry.action == "deleted":
                if target.exists():
                    return False
                digest = None
            else:
                if not target.is_file():
                    return False
                digest = hashlib.sha256(target.read_bytes()).hexdigest()
                if digest != entry.sha256:
                    return False
            rows.append((entry.path, entry.action, digest))
        return _tree_hash(rows) == self.content_hash


def _tree_hash(rows: Iterable[tuple[str, str, str | None]]) -> str:
    digest = hashlib.sha256()
    for path, action, content_hash in sorted(rows):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(action.encode("ascii"))
        digest.update(b"\0")
        digest.update((content_hash or "").encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _relative(path: str) -> PurePosixPath:
    if not isinstance(path, str) or not path or "\\" in path:
        raise ManifestError("path must be a non-empty normalized relative POSIX path")
    pure = PurePosixPath(path)
    if pure.is_absolute() or pure.drive or any(part in {"", ".", ".."} for part in pure.parts):
        raise ManifestError(f"unsafe candidate path: {path}")
    if any(root == path or path.startswith(root) for spec in COMPONENT_MANIFEST.values() for root in spec.allowed_roots):
        return pure
    raise ManifestError(f"path has no component consumer: {path}")


def _check_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ManifestError(f"symlink or reparse point forbidden: {path.relative_to(root)}")


def materialize_sparse_patch(
    base_root: str | Path,
    patches: Iterable[Mapping[str, Any]],
    output_root: str | Path,
) -> MaterializedManifest:
    """Materialize inherited files plus explicit writes/deletes into a new tree."""
    base = Path(base_root).resolve()
    output = Path(output_root).resolve()
    if output == base or output.is_relative_to(base):
        raise ManifestError("output must be separate from base")
    _check_tree(base)
    rows = list(patches)
    by_path: dict[str, Mapping[str, Any]] = {}
    for patch in rows:
        path = str(_relative(str(patch.get("path", ""))))
        if path in by_path:
            raise ManifestError(f"duplicate sparse path: {path}")
        by_path[path] = patch
    if output.exists():
        shutil.rmtree(output)
    entries: dict[str, ManifestEntry] = {}
    if base.exists():
        for source in sorted(base.rglob("*")):
            if not source.is_file():
                continue
            path = source.relative_to(base).as_posix()
            if path in by_path:
                continue
            target = output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            target.write_bytes(data)
            entries[path] = ManifestEntry(path, "inherited", hashlib.sha256(data).hexdigest())
    for path, patch in sorted(by_path.items()):
        operation = str(patch.get("operation", "write"))
        target = output / path
        if operation == "delete":
            if target.exists():
                target.unlink()
            entries[path] = ManifestEntry(path, "deleted", None)
        elif operation in {"write", "replace", "create"}:
            if "content" not in patch or patch.get("content_ref"):
                raise ManifestError("content bytes and content_ref are mutually exclusive")
            content = patch.get("content", b"")
            data = content.encode("utf-8") if isinstance(content, str) else bytes(content)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            entries[path] = ManifestEntry(path, operation, hashlib.sha256(data).hexdigest())
        else:
            raise ManifestError(f"unsupported operation: {operation}")
    _check_tree(output)
    manifest = MaterializedManifest(
        tuple(entries[path] for path in sorted(entries)),
        _tree_hash((entry.path, entry.action, entry.sha256) for entry in entries.values()),
    )
    if not manifest.verify(output):
        raise ManifestError("materialized content hash verification failed")
    return manifest
