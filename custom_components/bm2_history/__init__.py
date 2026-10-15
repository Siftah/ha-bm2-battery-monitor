"""BM2 battery monitoring and history recovery."""

import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .bluetooth import download_history
from .const import DOMAIN, PLATFORMS, SIGNAL_UPDATE
from .protocol import hourly_statistics
from .tracking import freshest_source, should_recover

_LOGGER = logging.getLogger(__name__)
BATTERY_SCHEMA = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Required("mac_address"): cv.string,
        vol.Required("voltage_sources"): vol.All(cv.ensure_list, [cv.entity_id], vol.Length(min=1)),
    }
)
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("offline_after", default=180): vol.All(
                    cv.positive_int, vol.Range(min=60)
                ),
                vol.Optional("sync_interval", default=3600): vol.All(
                    cv.positive_int, vol.Range(min=3600)
                ),
                vol.Required("batteries"): {cv.slug: BATTERY_SCHEMA},
            }
        ),
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Create the shared connection manager and import legacy YAML."""
    store = Store(hass, 1, DOMAIN)
    manager = HistoryManager(hass, store, await store.async_load() or {})
    hass.data[DOMAIN] = manager
    manager.cancel_timer = async_track_time_interval(hass, manager.tick, timedelta(seconds=30))

    async def stop(_event):
        await manager.shutdown()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)

    async def recover(call):
        battery_id = call.data["battery_id"]
        if battery_id not in manager.batteries:
            from homeassistant.exceptions import ServiceValidationError

            raise ServiceValidationError(f"Unknown BM2 battery ID: {battery_id}")
        await manager.request_recovery(battery_id)

    hass.services.async_register(
        DOMAIN,
        "recover",
        recover,
        schema=vol.Schema(
            {
                vol.Required("battery_id"): cv.slug,
            }
        ),
    )
    if settings := config.get(DOMAIN):
        for battery_id, battery in settings["batteries"].items():
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": "import"},
                    data={
                        **battery,
                        "battery_id": battery_id,
                        "offline_after": settings["offline_after"],
                        "sync_interval": settings["sync_interval"],
                    },
                )
            )
    return True


async def async_setup_entry(hass, entry):
    """Set up one physical battery, independent of its receivers."""
    manager = hass.data[DOMAIN]
    battery_id = entry.data["battery_id"]
    manager.batteries[battery_id] = {**entry.data, **entry.options}
    entry.runtime_data = manager
    entry.async_on_unload(entry.add_update_listener(_async_update_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await manager.tick(dt_util.utcnow())
    return True


async def _async_update_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    manager = entry.runtime_data
    battery_id = entry.data["battery_id"]
    manager.batteries.pop(battery_id, None)
    if task := manager.tasks.get(battery_id):
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    return True


class HistoryManager:
    """Serialize downloads while keeping live entities responsive."""

    def __init__(self, hass, store, saved):
        self.hass, self.store, self.saved = hass, store, saved
        self.batteries = {}
        self.lock = asyncio.Lock()
        self.tasks = {}
        self.retry_after = {}
        self.live = {}
        self.cancel_timer = None
        self.stopping = False

    async def shutdown(self):
        self.stopping = True
        if self.cancel_timer:
            self.cancel_timer()
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self.store.async_save(self.saved)

    async def tick(self, now):
        if self.stopping:
            return
        registry = er.async_get(self.hass)
        for battery_id, battery in list(self.batteries.items()):
            sources = []
            for entity_id in battery["voltage_sources"]:
                # Never feed canonical BM2 sensors back into their own inputs.
                registered = registry.async_get(entity_id)
                if registered is not None and registered.platform == DOMAIN:
                    continue
                if source := self.hass.states.get(entity_id):
                    sources.append(source)
            fresh = freshest_source(sources)
            freshest = fresh.last_reported.timestamp() if fresh else 0
            self.live[battery_id] = fresh
            state = self.saved.setdefault(battery_id, {})
            before = dict(state)
            due = should_recover(
                state, freshest, now.timestamp(), battery["offline_after"], battery["sync_interval"]
            )
            if state != before:
                self.store.async_delay_save(lambda: self.saved, 5)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE, battery_id)
            if due and now.timestamp() >= self.retry_after.get(battery_id, 0):
                self.start_recovery(battery_id)

    @callback
    def start_recovery(self, battery_id):
        if self.stopping:
            return None
        if battery_id not in self.tasks:
            self.tasks[battery_id] = self.hass.async_create_background_task(
                self._recover(battery_id),
                f"BM2 history: {battery_id}",
                eager_start=False,
            )
        return self.tasks[battery_id]

    async def request_recovery(self, battery_id):
        task = self.start_recovery(battery_id)
        if task:
            await asyncio.shield(task)

    async def _recover(self, battery_id):
        try:
            async with self.lock:
                state = self.saved.setdefault(battery_id, {})
                state["pending"] = True
                self.store.async_delay_save(lambda: self.saved, 5)
                battery = self.batteries[battery_id]
                try:
                    readings = await download_history(self.hass, battery["mac_address"].upper())
                    statistics = hourly_statistics(readings, dt_util.utcnow())
                    if statistics:
                        async_add_external_statistics(
                            self.hass,
                            {
                                "source": DOMAIN,
                                "statistic_id": f"{DOMAIN}:{battery_id}_voltage",
                                "name": f"{battery['name']} Voltage",
                                "unit_of_measurement": "V",
                                "unit_class": "voltage",
                                "mean_type": StatisticMeanType.ARITHMETIC,
                                "has_sum": False,
                            },
                            statistics,
                        )
                    state.update(last_sync=dt_util.utcnow().timestamp(), pending=False)
                    state.pop("last_error", None)
                    self.retry_after.pop(battery_id, None)
                    self.hass.bus.async_fire(
                        "bm2_history_recovered",
                        {
                            "battery_id": battery_id,
                            "records": len(readings),
                            "hours": len(statistics),
                            "timestamps_estimated": True,
                        },
                    )
                    _LOGGER.info("%s: queued %s hourly statistics", battery_id, len(statistics))
                except Exception as err:
                    state["last_error"] = str(err)
                    self.retry_after[battery_id] = dt_util.utcnow().timestamp() + 300
                    _LOGGER.warning(
                        "%s: history recovery failed; retry in 5 minutes: %s", battery_id, err
                    )
        finally:
            self.tasks.pop(battery_id, None)
            self.store.async_delay_save(lambda: self.saved, 5)
            async_dispatcher_send(self.hass, SIGNAL_UPDATE, battery_id)
