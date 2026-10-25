"""Throttled DOP2 reads must still happen on the first poll after a host boot.

time.monotonic() counts from boot on Linux, so on a freshly booted HA host it
is smaller than the refresh interval. A last-fetch timestamp initialised to 0.0
then throttles the very first read, and the entities gated on it at setup are
never created for that run.
"""
from types import SimpleNamespace

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame

import custom_components.miele_lan.coordinator as coordinator_mod
from custom_components.miele_lan.const import MieleAppliance
from custom_components.miele_lan.coordinator import MieleLanCoordinator

SHORT_UPTIME = 120.0  # seconds since boot, below every refresh interval


class _Raw:
    def __init__(self) -> None:
        self.resources: list[str] = []

    async def _request_bytes(self, method: str, resource: str, **kwargs):
        self.resources.append(resource)
        return 404, b""


@pytest.fixture
def make_coordinator(tmp_path, monkeypatch):
    monkeypatch.setattr(frame, "report_usage", lambda *args, **kwargs: None)
    monkeypatch.setattr(coordinator_mod.time, "monotonic", lambda: SHORT_UPTIME)

    def make(device_type: MieleAppliance) -> MieleLanCoordinator:
        coord = MieleLanCoordinator(
            HomeAssistant(str(tmp_path)),
            SimpleNamespace(entry_id="test"),
            SimpleNamespace(raw=_Raw()),
            "000000000001",
        )
        coord._data.ident = {"device_type": int(device_type)}
        return coord

    return make


@pytest.mark.asyncio
async def test_device_context_read_on_first_poll_after_boot(make_coordinator):
    coord = make_coordinator(MieleAppliance.WASHING_MACHINE)
    await coord._maybe_refresh_device_context()
    assert any("/DOP2/2/1585" in r for r in coord.client.raw.resources)


@pytest.mark.asyncio
async def test_hours_of_operation_read_on_first_poll_after_boot(make_coordinator):
    coord = make_coordinator(MieleAppliance.OVEN)
    await coord._maybe_refresh_hours_of_operation()
    assert any("/DOP2/2/119" in r for r in coord.client.raw.resources)
