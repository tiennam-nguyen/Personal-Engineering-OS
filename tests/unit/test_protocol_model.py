import pytest

from peos.domain.errors import ValidationError
from peos.domain.protocols.model import validate_protocol_identity


@pytest.mark.parametrize("name,version", [("sample.concept-summary", "1.0.0"), ("a", "0.0.1")])
def test_valid_protocol_identity(name: str, version: str) -> None:
    validate_protocol_identity(name, version)


@pytest.mark.parametrize(
    "name,version", [("Bad Name", "1.0.0"), ("sample", "v1"), ("../x", "1.0.0")]
)
def test_invalid_protocol_identity(name: str, version: str) -> None:
    with pytest.raises(ValidationError):
        validate_protocol_identity(name, version)
