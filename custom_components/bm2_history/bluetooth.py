"""Short-lived BM2 history connections through Home Assistant Bluetooth."""

import asyncio
import logging

import bleak_retry_connector
from homeassistant.components import bluetooth
from homeassistant.core import callback
from homeassistant.util import dt as dt_util

from .protocol import (
    READ_UUID,
    WRITE_UUID,
    HistoryBuffer,
    decode_records,
    decrypt_notification,
    encrypt_command,
)

_LOGGER = logging.getLogger(__name__)


async def download_history(hass, address):
    """Use a HA BLEDevice, so HA can route GATT through an ESPHome proxy."""
    device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
    if device is None:
        raise ValueError(f"No connectable Bluetooth proxy can reach {address}")
    loop = asyncio.get_running_loop()
    count_future = loop.create_future()
    done = loop.create_future()
    buffer = HistoryBuffer()

    @callback
    def disconnected(_client):
        for future in (count_future, done):
            if not future.done():
                future.set_exception(ConnectionError("BM2 disconnected during history download"))

    @callback
    def notify(_characteristic, encrypted):
        try:
            plain = decrypt_notification(bytes(encrypted))
            for offset in range(0, len(plain), 16):
                size = buffer.feed(plain[offset : offset + 16])
                if size is not None and not count_future.done():
                    count_future.set_result(size)
                if buffer.complete and not done.done():
                    done.set_result(bytes(buffer.data))
        except ValueError as err:
            for future in (count_future, done):
                if not future.done():
                    future.set_exception(err)

    client = None
    try:
        async with asyncio.timeout(90):
            # HA replaces this class when Bluetooth initializes. Resolve it here,
            # since importing a class during YAML/schema loading can retain the
            # raw platform client and bypass ESPHome proxy routing.
            client = await bleak_retry_connector.establish_connection(
                bleak_retry_connector.BleakClientWithServiceCache,
                device,
                address,
                disconnected_callback=disconnected,
                ble_device_callback=lambda: bluetooth.async_ble_device_from_address(
                    hass, address, connectable=True
                ),
            )
            write_characteristic = client.services.get_characteristic(WRITE_UUID)
            if write_characteristic is None:
                raise ValueError("BM2 history write characteristic is missing")
            write_response = "write" in write_characteristic.properties
            await client.start_notify(READ_UUID, notify)
            await client.write_gatt_char(
                WRITE_UUID, encrypt_command(b"\xe7\x01"), response=write_response
            )
            size = await asyncio.wait_for(asyncio.shield(count_future), 10)
            if size:
                # Upstream observes that BM2 ignores E3 if sent immediately after E7.
                await asyncio.sleep(1)
                command = b"\xe3\x00\x00" + size.to_bytes(4, "big")
                await client.write_gatt_char(
                    WRITE_UUID, encrypt_command(command), response=write_response
                )
            raw = await done
            return decode_records(raw, dt_util.utcnow())
    finally:
        if client is not None:
            try:
                async with asyncio.timeout(10):
                    await client.disconnect()
            except Exception:  # Cleanup must not mask the download error.
                _LOGGER.debug("BM2 disconnect cleanup failed", exc_info=True)
        for future in (count_future, done):
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()  # Retrieve a disconnect error from an unused future.
