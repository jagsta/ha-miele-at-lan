"""Sleep-vs-unsupported handling for the DOP2 2/1585 (device context) poll.

Regression tests for the wake-and-retry path added with the dishwasher
consumable sensors: a sleeping XKM answers HTTP 500 (empty body) to
every DOP2 read, and latching *that* as "unsupported" would permanently
hide AutoDos/salt/rinse-aid entities on an appliance that happened to
be in deep standby at HA startup.

Coordinator is constructed standalone (no HA imports): a minimal stub
client reports scripted statuses, and the real
`_maybe_refresh_device_context` runs against it.
"""

import asyncio
import importlib.util
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import custom_components.miele_lan.coordinator as coordinator_mod  # noqa: E402
from custom_components.miele_lan.const import MieleAppliance  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures" / "g7655_dop2_1585.hex"
LEAF_URL_BODY = (200, bytes.fromhex(FIXTURE.read_text().replace("\n", "")))


class _StubRaw:
    def __init__(self, statuses: list[int]) -> None:
        self._statuses = list(statuses)
        self.calls = 0

    async def _request_bytes(self, method: str, resource: str, **kwargs: Any):
        self.calls += 1
        status = self._statuses.pop(0)
        if status == 200:
            return LEAF_URL_BODY
        return (status, b"")


class _StubClient:
    def __init__(self, statuses: list[int]) -> None:
        self.raw = _StubRaw(statuses)
        self.wake = AsyncMock(return_value={})

    def set_statuses(self, statuses: list[int]) -> None:
        self.raw._statuses = list(statuses)
        self.raw.calls = 0


def _make_coordinator(statuses: list[int], device_type: MieleAppliance) -> Any:
    """Build a coordinator-shaped object without running DataUpdateCoordinator.__init__."""
    coord = coordinator_mod.MieleLanCoordinator.__new__(  # type: ignore[misc]
        coordinator_mod.MieleLanCoordinator
    )
    coord.client = _StubClient(statuses)  # type: ignore[assignment]
    coord.fab = "000106908768"
    # device_type is a read-only property derived from ident (self._data).
    coord._data = coordinator_mod.MieleLanData()
    coord._data.ident = {"device_type": int(device_type)}
    coord._device_context_unsupported = False
    coord._device_context_last_fetch = 0.0
    return coord


def _reset_throttle(coord: Any) -> None:
    coord._device_context_last_fetch = 0.0


async def _run(coord: Any) -> None:
    # 1585 was already fetched once at patch time... no: throttle only
    # applies to the timestamp, which _reset_throttle clears.
    t0 = time.monotonic()
    await coord._maybe_refresh_device_context()
    assert time.monotonic() - t0 < 10


def test_sleep_500_does_not_latch_unsupported() -> None:
    coord = _make_coordinator([500], MieleAppliance.DISHWASHER)
    coord.client.set_statuses([500])
    asyncio.run(_run(coord))
    assert coord._device_context_unsupported is False


def test_sleep_500_wakes_and_retries() -> None:
    coord = _make_coordinator([500], MieleAppliance.DISHWASHER)
    coord.client.set_statuses([500, 200])
    asyncio.run(_run(coord))
    assert coord.client.raw.calls == 2
    # device context decoded from the retried read
    assert coord._data.device_context.get("salt_percent") == 77


def test_404_latches_unsupported() -> None:
    coord = _make_coordinator([500], MieleAppliance.DISHWASHER)
    coord.client.set_statuses([404])
    asyncio.run(_run(coord))
    assert coord._device_context_unsupported is True


def test_still_500_after_wake_stays_transient() -> None:
    coord = _make_coordinator([500], MieleAppliance.DISHWASHER)
    coord.client.set_statuses([500, 500])
    asyncio.run(_run(coord))
    assert coord._device_context_unsupported is False
    assert coord.client.raw.calls == 2


def test_non_dw_family_never_polls() -> None:
    coord = _make_coordinator([500], MieleAppliance.OVEN)
    coord.client.set_statuses([500, 200])
    asyncio.run(_run(coord))
    assert coord.client.raw.calls == 0


def test_laundry_family_still_polls() -> None:
    """Gate extension must not regress the original TwinDos consumers."""
    coord = _make_coordinator([500], MieleAppliance.WASHING_MACHINE)
    coord.client.set_statuses([200])
    asyncio.run(_run(coord))
    assert coord.client.raw.calls == 1
    assert coord._data.device_context.get("dos_containers") is not None