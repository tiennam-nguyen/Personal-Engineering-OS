from __future__ import annotations

import pytest

from peos.domain.errors import HardeningIntegrityError
from peos.domain.hardening import InventoryEntry, inventory_generation, validate_relative_path


def test_inventory_generation_is_order_independent_and_load_bearing() -> None:
    first = InventoryEntry("peos.yaml", "workspace_config", 1, "sha256:" + "1" * 64)
    second = InventoryEntry("artifacts/a.md", "artifact", 2, "sha256:" + "2" * 64)
    assert inventory_generation((first, second)) == inventory_generation((second, first))
    changed = InventoryEntry("artifacts/a.md", "artifact", 2, "sha256:" + "3" * 64)
    assert inventory_generation((first, second)) != inventory_generation((first, changed))


@pytest.mark.parametrize("value", ["../x", "/x", "C:/x", "a\\b", "./x", "a/../b"])
def test_inventory_paths_reject_escape_and_noncanonical_forms(value: str) -> None:
    with pytest.raises(HardeningIntegrityError):
        validate_relative_path(value)
