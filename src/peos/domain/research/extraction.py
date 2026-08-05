"""Exact line and byte extraction with strict UTF-8 coverage."""

from __future__ import annotations

import hashlib


def extract_plain_text(raw: bytes, source_id: str, object_hash: str) -> dict[str, object]:
    segments: list[dict[str, object]] = []
    unreadable: list[dict[str, object]] = []
    readable_bytes = 0
    unreadable_bytes = 0
    offset = 0
    lines = raw.splitlines(keepends=True)
    if raw and (not lines or sum(len(line) for line in lines) < len(raw)):
        lines.append(raw[sum(len(line) for line in lines) :])
    for number, line in enumerate(lines, 1):
        content = (
            line[:-2]
            if line.endswith(b"\r\n")
            else line[:-1]
            if line.endswith((b"\n", b"\r"))
            else line
        )
        end = offset + len(content)
        common = {
            "source_artifact_id": source_id,
            "object_hash": object_hash,
            "line_start": number,
            "line_end": number,
            "byte_start": offset,
            "byte_end": end,
        }
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            unreadable.append({**common, "reason": "invalid_utf8"})
            unreadable_bytes += len(content)
        else:
            segments.append(
                {
                    **common,
                    "text": text,
                    "excerpt_hash": "sha256:" + hashlib.sha256(content).hexdigest(),
                }
            )
            readable_bytes += len(content)
        offset += len(line)
    return {
        "total_lines": len(lines),
        "readable_lines": len(segments),
        "unreadable_lines": len(unreadable),
        "readable_bytes": readable_bytes,
        "unreadable_bytes": unreadable_bytes,
        "segments": segments,
        "unreadable_segments": unreadable,
    }
