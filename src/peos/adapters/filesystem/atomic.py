"""Small same-filesystem atomic write helpers."""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def atomic_write(staging_dir: Path, final_path: Path, data: bytes) -> None:
    staging_dir.mkdir(parents=True, exist_ok=True)
    stage = staging_dir / f"write-{uuid.uuid4().hex}.tmp"
    try:
        with stage.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if final_path.exists():
            raise FileExistsError(final_path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, final_path)
        if os.name == "posix":
            descriptor = os.open(final_path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except Exception:
        if stage.exists():
            stage.unlink()
        raise
