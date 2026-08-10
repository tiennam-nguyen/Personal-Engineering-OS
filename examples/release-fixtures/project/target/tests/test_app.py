from src.app import status


def test_status() -> None:
    assert status() == "ok"
