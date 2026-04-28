"""Atomic JSON store for KanbanGateway.

Uses fcntl.flock directly on the data file (no separate .lock file).
"""
import fcntl
import json
import os
import pathlib
import tempfile
from typing import Any, Callable, TypeVar

T = TypeVar("T")

__all__ = ["atomic_read", "atomic_write", "atomic_update"]


def atomic_read(path: pathlib.Path, default: T) -> T:
    """Read JSON from *path* under a shared lock.

    Returns *default* if the file does not exist or is malformed.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            except (json.JSONDecodeError, ValueError):
                return default
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except FileNotFoundError:
        return default


def atomic_write(path: pathlib.Path, data: Any) -> None:
    """Write *data* as JSON to *path* atomically.

    Uses a temp file in the parent directory + os.replace, guarded by
    an exclusive flock on the target file so concurrent writers cannot
    race and lose data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as lockfile:
        fcntl.flock(lockfile.fileno(), fcntl.LOCK_EX)
        try:
            fd, tmp = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=path.stem + "_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, str(path))
            except Exception:
                try:
                    os.unlink(tmp)
                except FileNotFoundError:
                    pass
                raise
        finally:
            fcntl.flock(lockfile.fileno(), fcntl.LOCK_UN)


def atomic_update(
    path: pathlib.Path, modifier: Callable[[T], T], default: T
) -> T:
    """Read-modify-write *path* atomically under an exclusive lock.

    The file is opened in append+read mode ("a+"), locked exclusively,
    read from the beginning, modified, truncated, written back, and fsync'd.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            try:
                data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                data = default
            result = modifier(data)
            f.seek(0)
            f.truncate()
            json.dump(result, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
            return result
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
