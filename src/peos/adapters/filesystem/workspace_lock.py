"""Process-held local workspace mutation lock."""

from __future__ import annotations

import json
import os
import sys
import time
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Self

from peos.domain.errors import WorkspaceLockedError

if sys.platform == "win32":
    import msvcrt

    def _try_acquire_platform_lock(handle: BinaryIO) -> None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)

    def _release_platform_lock(handle: BinaryIO) -> None:
        # LK_UNLCK was unreliable after metadata writes on the verified Windows runtime.
        # Closing the owning handle below releases the process-held byte-range lock.
        del handle

else:
    import fcntl

    def _try_acquire_platform_lock(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release_platform_lock(handle: BinaryIO) -> None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class WorkspaceLock(AbstractContextManager["WorkspaceLock"]):
    def __init__(self, lock_path: Path, command: str) -> None:
        self._path = lock_path
        self._command = command
        self._handle: BinaryIO | None = None

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
                _try_acquire_platform_lock(handle)
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
            _release_platform_lock(self._handle)
            self._handle.close()
            self._handle = None
