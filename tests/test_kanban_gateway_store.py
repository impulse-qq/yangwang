"""Tests for kanban_gateway.store — atomic JSON file operations."""
import json
import pathlib
import tempfile
import threading

import pytest

from kanban_gateway.store import atomic_read, atomic_write, atomic_update


class TestAtomicReadWrite:
    def test_atomic_write_and_read(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "tasks.json"
        path.write_text(json.dumps([]), encoding="utf-8")
        atomic_write(path, [{"id": "T1"}])
        result = atomic_read(path, [])
        assert result == [{"id": "T1"}]


class TestAtomicUpdate:
    def test_atomic_update_race(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "tasks.json"
        path.write_text(json.dumps([]), encoding="utf-8")

        def worker() -> None:
            for _ in range(50):
                atomic_update(path, lambda items: items + [{"id": "x"}], [])

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        result = atomic_read(path, [])
        assert len(result) == 100
