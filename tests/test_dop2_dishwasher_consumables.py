"""Dishwasher consumable sensors — G7655 DOP2 2/1585 fixture regressions.

Fixture captured live from a G7655 (XKM EK057S, FW 09.14, protocolVersion 4) via
`miele_lan.dump_dop2_leaf` while the Miele cloud integration reported
PowerDisk 72 %, salt 77 %, rinse aid 89 % for the same machine.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from custom_components.miele_lan.dop2 import parse_global_device_context  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "g7655_dop2_1585.hex"


def _load_fixture() -> bytes:
    content = FIXTURE.read_text()
    return bytes.fromhex(content.replace("\n", " ").replace(" ", ""))


def test_autodos_container_decoded() -> None:
    ctx = parse_global_device_context(_load_fixture())
    containers = ctx["dos_containers"]
    assert containers is not None
    assert len(containers) == 1
    c = containers[0]
    assert c["filling_level_pct"] == 72
    assert c["current_dosage_ml"] == 65
    assert c["container_size_ml"] == 400
    assert c["bitmask_inserted"] is True
    assert c["bitmask_empty"] is False
    assert c["bitmask_low_level"] is False


def test_salt_level_matches_cloud() -> None:
    ctx = parse_global_device_context(_load_fixture())
    assert ctx["salt_percent"] == 77


def test_rinse_aid_level_matches_cloud() -> None:
    ctx = parse_global_device_context(_load_fixture())
    assert ctx["rinse_aid_percent"] == 89


def test_missing_fields_return_none_not_crash() -> None:
    ctx = parse_global_device_context(_load_fixture())
    # device_attributes may lack fields 8/9 on non-DW machines
    if ctx.get("device_attributes_dwtdwm") is None:
        assert ctx["salt_percent"] is None
        assert ctx["rinse_aid_percent"] is None


def test_wash2dry_absent_on_dishwasher() -> None:
    ctx = parse_global_device_context(_load_fixture())
    assert ctx["wash2dry_state"] is None