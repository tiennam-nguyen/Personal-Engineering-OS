import hashlib

from peos.domain.research.extraction import extract_plain_text


def test_offsets_crlf_invalid_utf8_and_final_line() -> None:
    raw = b"alpha\r\n\xff\xfe\nomega"
    report = extract_plain_text(raw, "art_" + "a" * 32, "sha256:" + "b" * 64)
    readable = report["segments"]
    unreadable = report["unreadable_segments"]
    assert isinstance(readable, list) and isinstance(unreadable, list)
    assert [(item["line_start"], item["byte_start"], item["byte_end"]) for item in readable] == [
        (1, 0, 5),
        (3, 10, 15),
    ]
    assert unreadable == [
        {
            "source_artifact_id": "art_" + "a" * 32,
            "object_hash": "sha256:" + "b" * 64,
            "line_start": 2,
            "line_end": 2,
            "byte_start": 7,
            "byte_end": 9,
            "reason": "invalid_utf8",
        }
    ]
    assert readable[0]["excerpt_hash"] == "sha256:" + hashlib.sha256(b"alpha").hexdigest()
