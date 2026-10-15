"""Shared battery entity lifecycle."""

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, SIGNAL_UPDATE


class BM2Entity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, suffix):
        self.manager = entry.runtime_data
        self.battery_id = entry.data["battery_id"]
        self._attr_unique_id = f"{entry.unique_id}_{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id)},
            name=entry.title,
            manufacturer="BM2",
            model="Bluetooth Battery Monitor",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._updated))

    @callback
    def _updated(self, battery_id):
        if battery_id == self.battery_id:
            self.async_write_ha_state()

    @property
    def fresh_source(self):
        source = self.manager.live.get(self.battery_id)
        settings = self.manager.batteries[self.battery_id]
        from homeassistant.util import dt as dt_util

        if (
            source
            and dt_util.utcnow().timestamp() - source.last_reported.timestamp()
            <= settings["offline_after"]
        ):
            return source
        return None
