"""Process-held local workspace mutation lock."""

from __future__ import annotations

import json
import os
import time
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from peos.domain.errors import WorkspaceLockedError


class WorkspaceLock(AbstractContextManager["WorkspaceLock"]):
    def __init__(self, lock_path: Path, command: str) -> None:
        self._path = lock_path
        self._command = command
        self._handle: Any | None = None

    def __enter__(self) -> Self:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("xb") as initial:
                initial.write(b" ")
                initial.flush()
                os.fsync(initial.fileno())
        except FileExistsError:
            pass
        handle = self._path.open("r+b")
        if self._path.stat().st_size == 0:
            handle.write(b" ")
            handle.flush()
            os.fsync(handle.fileno())
        deadline = time.monotonic() + 5
        while True:
            try:
                self._try_lock(handle)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise WorkspaceLockedError("Workspace is locked by another mutating process.")
                time.sleep(0.05)
        payload = {
            "pid": os.getpid(),
            "acquired_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "command": self._command,
        }
        metadata = json.dumps(payload, sort_keys=True).encode("utf-8") + b"\n"
        handle.seek(0, os.SEEK_END)
        previous_size = handle.tell()
        handle.seek(0)
        handle.write(metadata + b" " * max(0, previous_size - len(metadata)))
        handle.flush()
        os.fsync(handle.fileno())
        self._handle = handle
        return self

    def __exit__(self, *_: object) -> None:
        if self._handle is not None:
            # Closing a process-held Windows byte-range lock reliably releases it;
            # explicit LK_UNLCK can fail after metadata writes on the active runtime.
            if os.name != "nt":
                self._unlock(self._handle)
            self._handle.close()
            self._handle = None

    @staticmethod
    def _try_lock(handle: Any) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)  # type: ignore[attr-defined]

    @staticmethod
    def _unlock(handle: Any) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)  # type: ignore[attr-defined]
