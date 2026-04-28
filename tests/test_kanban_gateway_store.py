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

    def test_atomic_read_returns_default_when_missing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "missing.json"
        result = atomic_read(path, [])
        assert result == []

    def test_atomic_read_returns_default_when_invalid_json(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("not json", encoding="utf-8")
        result = atomic_read(path, [])
        assert result == []

    def test_atomic_write_race(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "tasks.json"
        # Pre-seed so atomic_write only does full overwrites
        path.write_text(json.dumps([]), encoding="utf-8")

        def worker(n: int) -> None:
            for i in range(50):
                atomic_write(path, [{"id": f"thread-{n}-item-{i}"}])

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # After all writers finish, the file must contain valid JSON
        result = atomic_read(path, [])
        assert isinstance(result, list)
        assert len(result) == 1  # each write overwrites with a 1-element list
        # Verify the single item is well-formed
        assert "id" in result[0]


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

    def test_atomic_update_creates_file_if_missing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "new.json"
        result = atomic_update(path, lambda items: items + [{"id": "first"}], [])
        assert result == [{"id": "first"}]
        assert atomic_read(path, []) == [{"id": "first"}]
