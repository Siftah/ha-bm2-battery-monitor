"""Exercise the GATT session with encrypted synthetic notifications."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch, sentinel

import pytest

from custom_components.bm2_history.bluetooth import download_history
from custom_components.bm2_history.protocol import encrypt_command


@pytest.mark.parametrize("empty", [False, True])
async def test_gatt_download_and_disconnect(hass, empty):
    notify = None

    async def start_notify(uuid, callback):
        nonlocal notify
        notify = callback

    async def write(uuid, command, **kwargs):
        if command == encrypt_command(b"\xe7\x01"):
            notify(None, encrypt_command(b"\xe7\x00\x00" + (b"\x00" if empty else b"\x0d")))
        else:
            notify(None, encrypt_command(b"\xff\xff\xfe"))
            notify(None, encrypt_command(bytes.fromhex("4d411111")))
            notify(None, encrypt_command(b"\xff\xfe\xfe\x00\x00\x0d"))

    client = SimpleNamespace(
        services=SimpleNamespace(
            get_characteristic=lambda uuid: SimpleNamespace(properties=["write"])
        ),
        start_notify=AsyncMock(side_effect=start_notify),
        write_gatt_char=AsyncMock(side_effect=write),
        disconnect=AsyncMock(),
    )
    with (
        patch(
            "custom_components.bm2_history.bluetooth.bluetooth.async_ble_device_from_address",
            return_value=object(),
        ),
        patch(
            "custom_components.bm2_history.bluetooth.bleak_retry_connector.establish_connection",
            new=AsyncMock(return_value=client),
        ) as establish,
        patch(
            "custom_components.bm2_history.bluetooth.bleak_retry_connector.BleakClientWithServiceCache",
            sentinel.ha_proxy_client,
        ),
    ):
        readings = await download_history(hass, "AA:BB:CC:DD:EE:FF")
    # Simulate HA replacing the class after our module was imported.
    assert establish.call_args.args[0] is sentinel.ha_proxy_client
    assert len(readings) == (0 if empty else 1)
    if not empty:
        assert readings[0].voltage == 12.36
    client.disconnect.assert_awaited_once()


async def test_no_connectable_proxy(hass):
    with patch(
        "custom_components.bm2_history.bluetooth.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        with pytest.raises(ValueError, match="No connectable"):
            await download_history(hass, "AA:BB:CC:DD:EE:FF")
