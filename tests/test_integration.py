"""Exercise setup, live entities and asynchronous recovery on real HA classes."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bm2_history import HistoryManager
from custom_components.bm2_history.const import DOMAIN
from custom_components.bm2_history.protocol import Reading

DATA = {"name": "Starter Battery", "battery_id": "starter", "mac_address": "AA:BB:CC:DD:EE:FF"}
OPTIONS = {
    "voltage_sources": ["sensor.garage_voltage", "sensor.drive_voltage"],
    "offline_after": 180,
    "sync_interval": 3600,
}


async def test_user_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.bm2_history.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {**DATA, **OPTIONS}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == DATA["mac_address"]
    assert result["result"].options == OPTIONS


@pytest.mark.parametrize(
    ("change", "field", "error"),
    [
        ({"mac_address": "wrong"}, "mac_address", "invalid_mac"),
        ({"battery_id": "Bad ID"}, "battery_id", "invalid_battery_id"),
        ({"voltage_sources": []}, "voltage_sources", "no_sources"),
    ],
)
async def test_invalid_input(hass, change, field, error):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={**DATA, **OPTIONS, **change}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"][field] == error


async def test_duplicates(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DATA["mac_address"], data=DATA, options=OPTIONS
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}, data={**DATA, **OPTIONS}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={**DATA, **OPTIONS, "mac_address": "AA:BB:CC:DD:EE:01"},
    )
    assert result["errors"] == {"battery_id": "duplicate_battery_id"}


async def test_options(hass):
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DATA["mac_address"], data=DATA, options=OPTIONS
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**OPTIONS, "offline_after": 240}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["offline_after"] == 240


async def test_import_preserves_id(hass):
    with patch("custom_components.bm2_history.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data={**DATA, **OPTIONS}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].data["battery_id"] == "starter"


async def test_reject_canonical_source(hass, entity_registry):
    entity = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "canonical", suggested_object_id="canonical_voltage"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={**DATA, **OPTIONS, "voltage_sources": [entity.entity_id]},
    )
    assert result["errors"] == {"voltage_sources": "recursive_source"}


async def test_entities_and_unload(hass, mock_bluetooth, freezer):
    hass.states.async_set("sensor.garage_voltage", "12.4")
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=DATA["mac_address"], title=DATA["name"], data=DATA, options=OPTIONS
    )
    entry.add_to_hass(hass)
    with patch("custom_components.bm2_history.download_history", new=AsyncMock(return_value=[])):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    voltage = hass.states.get("sensor.starter_battery_voltage")
    assert voltage.state == "12.4"
    assert voltage.attributes["history_statistic_id"] == "bm2_history:starter_voltage"
    assert hass.states.get("binary_sensor.starter_battery_connected").state == "on"
    freezer.tick(timedelta(seconds=60))
    hass.states.async_set("sensor.drive_voltage", "12.6")
    await entry.runtime_data.tick(dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.starter_battery_voltage").state == "12.6"
    freezer.tick(timedelta(seconds=181))
    await entry.runtime_data.tick(dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("sensor.starter_battery_voltage").state == "unavailable"
    assert hass.states.get("binary_sensor.starter_battery_connected").state == "off"
    manager = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert "starter" not in manager.batteries


def manager_for(hass):
    store = Store(hass, 1, "bm2_test")
    store.async_delay_save = lambda *args: None
    manager = HistoryManager(hass, store, {})
    manager.batteries["starter"] = {**DATA, **OPTIONS}
    return manager


async def test_recovery_statistics(hass):
    manager = manager_for(hass)
    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    readings = [Reading(start + timedelta(minutes=i * 2), 12 + i / 100, 0, 0) for i in range(30)]
    with (
        patch(
            "custom_components.bm2_history.download_history", new=AsyncMock(return_value=readings)
        ),
        patch("custom_components.bm2_history.async_add_external_statistics") as add,
    ):
        await manager.request_recovery("starter")
    metadata, rows = add.call_args.args[1:]
    assert metadata["statistic_id"] == "bm2_history:starter_voltage"
    assert metadata["unit_class"] == "voltage"
    assert rows[0]["min"] == 12
    assert rows[0]["max"] == 12.29
    assert manager.saved["starter"]["pending"] is False
    assert not manager.tasks


async def test_failed_recovery_and_retry(hass):
    manager = manager_for(hass)
    hass.states.async_set("sensor.garage_voltage", "12.4")
    with patch(
        "custom_components.bm2_history.download_history",
        new=AsyncMock(side_effect=ConnectionError("busy")),
    ) as download:
        await manager.request_recovery("starter")
        assert manager.saved["starter"]["pending"] is True
        assert manager.saved["starter"]["last_error"] == "busy"
        await manager.tick(dt_util.utcnow())
        assert download.await_count == 1
    manager.retry_after["starter"] = 0
    with patch(
        "custom_components.bm2_history.download_history", new=AsyncMock(return_value=[])
    ) as download:
        await manager.tick(dt_util.utcnow())
        await asyncio.gather(*list(manager.tasks.values()))
        assert download.await_count == 1
        assert manager.saved["starter"]["pending"] is False


async def test_download_deduplication_and_serialization(hass):
    manager = manager_for(hass)
    manager.batteries["other"] = {**DATA, **OPTIONS, "mac_address": "AA:BB:CC:DD:EE:01"}
    entered = asyncio.Event()
    release = asyncio.Event()
    active = maximum = calls = 0

    async def download(*args):
        nonlocal active, maximum, calls
        active += 1
        calls += 1
        maximum = max(maximum, active)
        entered.set()
        await release.wait()
        active -= 1
        return []

    with patch("custom_components.bm2_history.download_history", new=download):
        first = manager.start_recovery("starter")
        assert manager.start_recovery("starter") is first
        second = manager.start_recovery("other")
        await entered.wait()
        assert calls == 1
        release.set()
        await asyncio.gather(first, second)
    assert calls == 2
    assert maximum == 1


async def test_cancel_preserves_pending(hass):
    manager = manager_for(hass)
    started = asyncio.Event()

    async def download(*args):
        started.set()
        await asyncio.Event().wait()

    with patch("custom_components.bm2_history.download_history", new=download):
        task = manager.start_recovery("starter")
        await started.wait()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert manager.saved["starter"]["pending"]
    assert not manager.tasks


async def test_real_recorder_import_replaces_hour(hass, recorder_mock):
    """Verify actual Recorder storage, including replacing an existing UTC hour."""
    from homeassistant.components.recorder.statistics import statistics_during_period
    from pytest_homeassistant_custom_component.components.recorder.common import (
        async_recorder_block_till_done,
    )

    manager = manager_for(hass)
    start = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

    async def recover(voltage):
        readings = [Reading(start + timedelta(minutes=i * 2), voltage, 0, 0) for i in range(30)]
        with patch(
            "custom_components.bm2_history.download_history", new=AsyncMock(return_value=readings)
        ):
            await manager.request_recovery("starter")
        await async_recorder_block_till_done(hass)
        return await recorder_mock.async_add_executor_job(
            statistics_during_period,
            hass,
            start,
            start + timedelta(hours=1),
            {"bm2_history:starter_voltage"},
            "hour",
            None,
            {"min", "mean", "max"},
        )

    rows = await recover(12.4)
    assert rows["bm2_history:starter_voltage"][0]["mean"] == pytest.approx(12.4)
    rows = await recover(12.6)
    assert len(rows["bm2_history:starter_voltage"]) == 1
    assert rows["bm2_history:starter_voltage"][0]["mean"] == pytest.approx(12.6)
