"""P2 · 原子写（tmp + fsync + os.replace）。

定位声明 · **DWC-AUTO**（自我强化）

★ 只保证“要么旧内容、要么完整新内容”，不保证跨文件事务。
★ 目标文件在 Windows 上被占用时 os.replace 会失败；调用方需保留错误。
"""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def write_text_atomic(path: str, text: str, *, encoding: str = "utf-8",
                      mode: int | None = None) -> None:
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dwc-tmp-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            try:
                os.chmod(tmp, mode)
            except OSError as exc:
                import sys as _sys
                _sys.stderr.write("atomic_io chmod 失败（跳过）: %s\n" % exc)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError as exc:
                import sys as _sys
                _sys.stderr.write("atomic_io 清理临时文件失败: %s\n" % exc)


def write_json_atomic(path: str, obj: Any, *, indent: int = 0,
                      ensure_ascii: bool = False, **kwargs: Any) -> None:
    write_text_atomic(path, json.dumps(obj, ensure_ascii=ensure_ascii,
                                       indent=indent or None), **kwargs)
