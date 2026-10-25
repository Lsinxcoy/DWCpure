import hashlib

from dwc.llm.output_compaction import CompactionConfig, compact_output, recover_output


def test_long_output_is_recoverable_with_hash_and_omitted_range(tmp_path):
    original = "BEGIN\n" + ("unique evidence line\n" * 100) + "END"
    result = compact_output(original, tmp_path, CompactionConfig(
        max_output_chars=120, head_chars=40, tail_chars=40,
        repeat_threshold=3,
    ))

    assert result["compacted"] is True
    assert result["compacted_chars"] < result["original_chars"]
    assert result["content_kind"] == "text"
    assert result["compaction_version"] == 1
    assert result["raw_sha256"] == hashlib.sha256(original.encode()).hexdigest()
    assert result["omitted_range"] is not None
    assert recover_output(result) == original
    start, end = result["omitted_range"]
    assert recover_output(result, (start, end)) == original[start:end]


def test_repeated_lines_are_folded_without_losing_raw(tmp_path):
    original = "start\n" + "same\n" * 8 + "finish\n"
    config = CompactionConfig(max_output_chars=20, head_chars=8, tail_chars=8)
    result = compact_output(original, tmp_path, config)

    assert "omitted 7 repeated lines" in result["output"]
    assert result["omitted_ranges"]
    assert recover_output(result) == original


def test_raw_write_failure_returns_entire_uncompacted_output(tmp_path, monkeypatch):
    original = "verification evidence\n" * 30
    config = CompactionConfig(max_output_chars=50, head_chars=20, tail_chars=20)

    def fail_write(self, mode="r", **kwargs):
        raise OSError("controlled evidence unavailable")

    monkeypatch.setattr(type(tmp_path / "raw"), "open", fail_write)
    result = compact_output(original, tmp_path, config)

    assert result["output"] == original
    assert result["compacted"] is False
    assert result["raw_ref"] is None
    assert result["compaction_status"] == "raw_write_failed_uncompacted"
    assert "OSError" in result["raw_write_error"]


def test_non_text_kinds_are_not_rewritten(tmp_path):
    config = CompactionConfig(max_output_chars=5, head_chars=2, tail_chars=2)
    for kind, content in (("binary", b"\x00\xffpayload"),
                          ("image", "base64-image-data"),
                          ("secret", "sensitive-token-data")):
        result = compact_output(content, tmp_path, config, content_kind=kind)
        assert result["compacted"] is False
        assert result["content_kind"] == kind
        assert result["raw_ref"] is None
