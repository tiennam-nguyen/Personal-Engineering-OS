"""Inspect built wheel/sdist members and metadata without importing PEOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import tarfile
import zipfile
from pathlib import PurePosixPath

FORBIDDEN = (".env", ".peos/", ".venv/", "index.sqlite3", "/cache/", "/backups/")


def safe(name: str) -> None:
    path = PurePosixPath(name)
    intentional_example = "/examples/release-backup-v1/payload/.peos/" in name
    forbidden = any(marker in name for marker in FORBIDDEN) and not intentional_example
    if path.is_absolute() or ".." in path.parts or forbidden:
        raise ValueError(f"Unsafe or private package member: {name}")


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("wheel")
    parser.add_argument("sdist")
    arguments = parser.parse_args()
    with zipfile.ZipFile(arguments.wheel) as wheel:
        wheel_names = wheel.namelist()
        for name in wheel_names:
            safe(name)
        metadata_name = next(name for name in wheel_names if name.endswith(".dist-info/METADATA"))
        entry_name = next(name for name in wheel_names if name.endswith("entry_points.txt"))
        metadata = wheel.read(metadata_name).decode("utf-8")
        entry_points = wheel.read(entry_name).decode("utf-8")
        if (
            "Name: peos" not in metadata
            or "Version: 1.0.0" not in metadata
            or "Requires-Python: >=3.11" not in metadata
            or "requires-dist: pyyaml<7,>=6" not in metadata.lower()
            or "peos = peos.cli.main:main" not in entry_points
            or not any(name.startswith("peos/") for name in wheel_names)
        ):
            raise ValueError("Wheel metadata or package contents are invalid.")
    with tarfile.open(arguments.sdist, "r:gz") as sdist:
        sdist_names = sdist.getnames()
        for name in sdist_names:
            safe(name)
        if not any(name.endswith("/LICENSE") for name in sdist_names):
            raise ValueError("Source distribution lacks LICENSE.")
    wheel_raw = open(arguments.wheel, "rb").read()
    sdist_raw = open(arguments.sdist, "rb").read()
    print(
        json.dumps(
            {
                "valid": True,
                "wheel_members": len(wheel_names),
                "sdist_members": len(sdist_names),
                "wheel_sha256": digest(wheel_raw),
                "sdist_sha256": digest(sdist_raw),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
