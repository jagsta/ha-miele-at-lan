"""Array field types in the DOP2 walker, against real captures.

g7655_dop2_1584.hex is GLOBAL_ProgramList (2/1584) from issue #61: field 2 is
an ArrayU16 of programme ids and field 3 an ArrayU16 of durations in seconds,
confirmed by the reporter against the panel. g7310_dop2_196.hex is
GLOBAL_CS_DeviceContext (2/196) from issue #15.
"""
import struct
from pathlib import Path

from custom_components.miele_lan.dop2 import _walk_fields

FIXTURES = Path(__file__).parent / "fixtures"


def _walk(name: str):
    buf = bytes.fromhex((FIXTURES / name).read_text().strip())
    fields, end = _walk_fields(buf, 12, struct.unpack_from(">H", buf, 10)[0])
    return buf, fields, end


def test_program_list_is_walked_to_the_last_byte() -> None:
    buf, fields, end = _walk("g7655_dop2_1584.hex")
    assert end == len(buf)
    assert sorted(fields) == list(range(1, 18))


def test_program_list_ids_and_durations() -> None:
    _, fields, _ = _walk("g7655_dop2_1584.hex")
    assert fields[1] == (0x02, 12)
    assert fields[2] == (0x15, [200, 202, 203, 204, 205, 209, 206, 207, 208, 210, 214, 215, 0, 0, 0])
    assert fields[3][1][:3] == [15064, 11481, 9167]
    assert fields[3][1][11] == 753  # 215 Rinse/salt, 12.5 min


def test_bool_and_enum8_arrays_are_one_byte_per_element() -> None:
    _, fields, _ = _walk("g7655_dop2_1584.hex")
    assert fields[8] == (0x11, [False] * 15)
    assert fields[15] == (0x14, [0] * 15)


def test_select_object_with_nested_struct() -> None:
    buf, fields, end = _walk("g7655_dop2_1577_intensive.hex")
    assert end == len(buf)
    assert fields[1] == (0x07, 205)
    assert fields[4][1][1] == (0x0b, 0)  # SelectionParaDW.DelayedStart


def test_service_context_with_enum16_array() -> None:
    buf, fields, end = _walk("g7310_dop2_196.hex")
    assert end == len(buf)
    assert fields[14] == (0x17, [0] * 6)
    assert fields[3][1][29][1][2] == (0x01, True)  # AprdCartridge


def test_unknown_type_stops_the_walk() -> None:
    # field 1 has an unimplemented type (0x1e); field 2 must not be read
    # from whatever bytes follow it.
    buf = bytes.fromhex("0001" "1e" "0002" "0000" "0002" "02" "07")
    fields, end = _walk_fields(buf, 0, 2)
    assert fields == {1: (0x1e, None)}
    assert end == 3
