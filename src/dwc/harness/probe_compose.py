"""DWC-AUTO · Shadow probes and diff-grounded composition (final specification section 6.4)."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import shutil
import tempfile
from typing import Any, Callable, Iterable, Mapping


class ComposeError(ValueError):
    pass


@dataclass(frozen=True)
class ProbeProtocol:
    protocol_id: str
    split: str
    task_ids: tuple[str, ...]
    model_id: str
    environment_hash: str

    def __post_init__(self) -> None:
        if self.split not in {"train", "dev"}:
            raise ComposeError("validation and held-out splits are forbidden in ProbeProtocol")
        if not self.protocol_id or not self.task_ids or not self.model_id or not self.environment_hash:
            raise ComposeError("complete probe identity is required")


@dataclass(frozen=True)
class ProbeResult:
    candidate_hash: str
    protocol_id: str
    split: str
    task_id: str
    model_id: str
    environment_hash: str
    behavior: str
    delivered: bool
    passed: bool | None
    adopted: bool = False
    verified: bool = False
    usage_ref: str | None = None
    infrastructure_error: str | None = None
    deliverable_kind: str = "artifact"
    evidence_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProbeRun:
    candidate_hash: str
    protocol_id: str
    results: tuple[ProbeResult, ...]
    status: str


def run_probe(
    protocol: ProbeProtocol,
    candidate_bytes: bytes,
    results: Iterable[ProbeResult],
    *,
    base_rollouts: Iterable[Any],
) -> ProbeRun:
    """Validate real shadow observations; this never substitutes fixed evaluation."""
    if protocol.split not in {"train", "dev"}:
        raise ComposeError("validation split is forbidden")
    if not tuple(base_rollouts):
        raise ComposeError("base measurement required before probe")
    digest = hashlib.sha256(candidate_bytes).hexdigest()
    observed = tuple(results)
    seen: set[str] = set()
    for result in observed:
        if result.candidate_hash != digest:
            raise ComposeError("candidate hash mismatch")
        if result.split not in {"train", "dev"} or result.split != protocol.split:
            raise ComposeError("validation or mismatched probe split")
        identity = (result.protocol_id, result.task_id, result.model_id, result.environment_hash)
        expected = (protocol.protocol_id, None, protocol.model_id, protocol.environment_hash)
        if identity[0] != expected[0] or identity[2:] != expected[2:] or result.task_id not in protocol.task_ids:
            raise ComposeError("probe execution identity mismatch")
        if result.task_id in seen:
            raise ComposeError("duplicate probe task result")
        seen.add(result.task_id)
        if not result.delivered and result.deliverable_kind != "state":
            raise ComposeError("artifact candidate has no deliverable")
    missing = set(protocol.task_ids) - seen
    status = "incomplete" if missing or any(r.infrastructure_error for r in observed) else "observed"
    return ProbeRun(digest, protocol.protocol_id, observed, status)


@dataclass(frozen=True)
class ComposeResult:
    decision: str
    kept: bool
    candidate_hash: str
    base_hash: str
    output_root: str
    status: str
    requires_reprobe: bool
    probe_result: Any = None
    labels: tuple[str, ...] = ()
    final_pool: tuple[str, ...] = ("base",)


def _tree(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        raise ComposeError("candidate root must be a directory")
    result: dict[str, bytes] = {}
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ComposeError("candidate symlinks are forbidden")
        if path.is_file():
            result[path.relative_to(root).as_posix()] = path.read_bytes()
    return result


def _hash(tree: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, content in sorted(tree.items()):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def compose_candidates(
    base_root: str | Path,
    decisions: Iterable[Mapping[str, Any]],
    *,
    output_root: str | Path | None = None,
    probe_runner: Callable[[Path], Any] | None = None,
) -> ComposeResult:
    """Merge explicitly selected trees, then derive KEEP_CURRENT from actual bytes."""
    rows = list(decisions)
    labels = [str(row.get("label", "")) for row in rows]
    if any(not label for label in labels):
        raise ComposeError("every compose input needs a label")
    if len(labels) != len(set(labels)):
        raise ComposeError("duplicate compose label")
    base_path = Path(base_root).resolve()
    base = _tree(base_path)
    selected: list[Mapping[str, Any]] = []
    for row in rows:
        evidence = row.get("evidence")
        if isinstance(evidence, Mapping) and evidence.get("split") not in {None, "train", "dev"}:
            raise ComposeError("validation SelectionReport cannot enter compose")
        if row.get("claimed_decision") != "discard" and (
            row.get("root") is not None or row.get("claimed_decision") != "KEEP_CURRENT"
        ):
            selected.append(row)
    temporary = output_root is None
    if temporary:
        output = Path(tempfile.mkdtemp(prefix="dwc-compose-")).resolve()
    else:
        output = Path(output_root).resolve()
        if output == base_path or output.is_relative_to(base_path):
            raise ComposeError("compose output must not overwrite base")
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True)
    try:
        merged = dict(base)
        for row in sorted(selected, key=lambda item: str(item["label"])):
            root = row.get("root")
            if root is None:
                continue
            overlay = _tree(Path(root).resolve())
            removals = set(row.get("delete", ()))
            for path in removals:
                merged.pop(path, None)
            merged.update(overlay)
        for path in sorted(merged):
            target = output / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(merged[path])
        base_hash = _hash(base)
        candidate_hash = _hash(merged)
        changed = candidate_hash != base_hash
        if not changed:
            return ComposeResult("KEEP_CURRENT", False, candidate_hash, base_hash, str(output), "no_change", False, labels=tuple(sorted(labels)), final_pool=("base",))
        if probe_runner is None:
            return ComposeResult("COMPOSED", True, candidate_hash, base_hash, str(output), "needs_reprobe", True, labels=tuple(sorted(labels)), final_pool=("base", "composed"))
        try:
            probe_result = probe_runner(output)
        except Exception as exc:
            raise ComposeError(f"composed candidate reprobe failed: {exc}") from exc
        if not probe_result:
            raise ComposeError("composed candidate requires a real reprobe")
        return ComposeResult("COMPOSED", True, candidate_hash, base_hash, str(output), "reprobed", False, probe_result=probe_result, labels=tuple(sorted(labels)), final_pool=("base", "composed"))
    except Exception:
        if temporary:
            shutil.rmtree(output, ignore_errors=True)
        raise
