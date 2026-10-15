"""Battery connectivity based on all configured receivers."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import BM2Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BM2Presence(entry)])


class BM2Presence(BM2Entity, BinarySensorEntity):
    _attr_name = "Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry):
        super().__init__(entry, "connected")

    @property
    def is_on(self):
        return self.fresh_source is not None
