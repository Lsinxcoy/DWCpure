"""DWC-AUTO · Auditable evidence-tree materialization with explicit withholding."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class EvidenceError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceEntry:
    ref: str
    kind: str
    role: str
    status: str
    path: str | None
    sha256: str | None
    reason: str | None = None


@dataclass(frozen=True)
class EvidenceManifest:
    entries: tuple[EvidenceEntry, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [asdict(entry) for entry in self.entries]}

    def write(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return target


class EvidenceBundleBuilder:
    def __init__(self, source_root: str | Path, output_root: str | Path | None = None):
        self.source_root = Path(source_root).resolve()
        self.output_root = Path(output_root).resolve() if output_root else None

    def _source(self, ref: str) -> Path:
        path = (self.source_root / ref).resolve()
        if not path.is_relative_to(self.source_root):
            raise EvidenceError("evidence path escapes source root")
        return path

    def build(self, requests: Iterable[Mapping[str, Any]]) -> EvidenceManifest:
        entries: list[EvidenceEntry] = []
        for request in requests:
            ref = str(request["ref"])
            kind = str(request.get("kind", "artifact"))
            role = str(request.get("role", "propose"))
            if request.get("withheld") or request.get("names_only"):
                entries.append(EvidenceEntry(ref, kind, role, "withheld", None, None,
                                             str(request.get("reason", "names_only" if request.get("names_only") else "withheld"))))
                continue
            source = self._source(ref)
            if not source.is_file():
                if kind == "trajectory":
                    raise EvidenceError(f"trajectory evidence unavailable: {ref}")
                entries.append(EvidenceEntry(ref, kind, role, "failed", None, None, "missing"))
                continue
            data = source.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            materialized = source
            if self.output_root is not None:
                materialized = self.output_root / digest
                materialized.parent.mkdir(parents=True, exist_ok=True)
                materialized.write_bytes(data)
            entries.append(EvidenceEntry(ref, kind, role, "materialized", str(materialized), digest))
        return EvidenceManifest(tuple(entries))
