"""DWC-AUTO · Recoverable evidence compaction; runtime tool output uses dwc.llm.tool_raw.

This module persists raw evidence and produces recoverable head/tail views for
evaluation artifacts. The production tool-output path is :mod:`dwc.llm.tool_raw`
(R440); do not wire both as competing runtime compressors.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALLOWED_CONTENT_KINDS = frozenset({"text", "log", "binary", "image", "secret"})


@dataclass(frozen=True)
class CompactionConfig:
    max_output_chars: int
    head_chars: int
    tail_chars: int
    repeat_threshold: int = 3

    def __post_init__(self) -> None:
        values = (self.max_output_chars, self.head_chars, self.tail_chars,
                  self.repeat_threshold)
        if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in values):
            raise ValueError("compaction thresholds must be positive integers")
        if self.head_chars + self.tail_chars >= self.max_output_chars:
            raise ValueError("head/tail must leave room for the recovery marker")


def _metadata(kind: str, original: str, compacted: str, *, raw_ref: str | None,
              raw_sha256: str | None, omitted_range: tuple[int, int] | None,
              error: str = "") -> dict[str, Any]:
    return {
        "output": compacted, "compacted": compacted != original,
        "raw_ref": raw_ref, "raw_sha256": raw_sha256,
        "original_chars": len(original), "compacted_chars": len(compacted),
        "omitted_range": omitted_range, "content_kind": kind,
        "compaction_version": 1, "raw_write_error": error,
    }


def compact_output(content: Any, evidence_dir: str | os.PathLike[str],
                   config: CompactionConfig, *, content_kind: str | None = None,
                   is_base64: bool = False) -> dict[str, Any]:
    """Persist raw bytes before any compaction; never drop output on write failure."""
    if content_kind not in ALLOWED_CONTENT_KINDS and content_kind is not None:
        raise ValueError("unsupported content kind")
    binary = isinstance(content, bytes)
    kind = content_kind or ("binary" if binary else "text")
    if binary:
        raw = bytes(content)
        original = raw.decode("utf-8", errors="replace")
    elif isinstance(content, str):
        original = content
        raw = original.encode("utf-8")
    else:
        original = json.dumps(content, ensure_ascii=False, default=str)
        raw = original.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    unchanged = _metadata(kind, original, original, raw_ref=None,
                          raw_sha256=None, omitted_range=None)
    if len(original) <= config.max_output_chars or kind in {"binary", "image", "secret"}:
        return unchanged

    path = Path(evidence_dir) / (digest + ".raw")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(raw)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise OSError("raw evidence verification failed")
    except OSError as exc:
        unchanged["raw_write_error"] = type(exc).__name__ + ":" + str(exc)
        unchanged["compaction_status"] = "raw_write_failed_uncompacted"
        return unchanged

    text, ranges = _compact_text(original, config)
    omitted = ranges[0] if ranges else None
    result = _metadata(kind, original, text, raw_ref=str(path.resolve()),
                       raw_sha256=digest, omitted_range=omitted)
    if ranges:
        result["omitted_ranges"] = ranges
        result["output"] += ("\n[raw evidence: %s; recover with recover_output; ranges=%s]"
                             % (path, ranges))
        result["compacted_chars"] = len(result["output"])
    return result


def _compact_text(original: str, config: CompactionConfig) -> tuple[str, list[tuple[int, int]]]:
    lines = original.splitlines(keepends=True)
    positions: list[int] = []
    pos = 0
    for line in lines:
        positions.append(pos)
        pos += len(line)
    output: list[str] = []
    ranges: list[tuple[int, int]] = []
    index = 0
    while index < len(lines):
        end = index + 1
        while end < len(lines) and lines[end] == lines[index]:
            end += 1
        count = end - index
        if count > config.repeat_threshold:
            start = positions[index + 1]
            stop = positions[end - 1] + len(lines[end - 1])
            output.append(lines[index])
            output.append("[ omitted %d repeated lines; raw range %d:%d ]\n"
                          % (count - 1, start, stop))
            ranges.append((start, stop))
        else:
            output.extend(lines[index:end])
        index = end
    compacted = "".join(output)
    if not ranges and len(compacted) > config.max_output_chars:
        head = original[:config.head_chars]
        tail = original[-config.tail_chars:]
        start, stop = len(head), len(original) - len(tail)
        compacted = (head + "[ omitted middle; raw range %d:%d ]" % (start, stop)
                     + tail)
        ranges.append((start, stop))
    return compacted, ranges


def recover_output(result: dict[str, Any], char_range: tuple[int, int] | None = None) -> str:
    """Recover full UTF-8 raw output or an exact character range after hash validation."""
    ref = result.get("raw_ref")
    if not ref:
        raise ValueError("output is not backed by raw evidence")
    raw = Path(ref).read_bytes()
    if hashlib.sha256(raw).hexdigest() != result.get("raw_sha256"):
        raise ValueError("raw evidence hash mismatch")
    text = raw.decode("utf-8")
    if char_range is None:
        return text
    start, stop = char_range
    if not 0 <= start <= stop <= len(text):
        raise ValueError("invalid character range")
    return text[start:stop]
