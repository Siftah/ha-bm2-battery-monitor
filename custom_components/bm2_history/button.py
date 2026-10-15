"""Manual history recovery."""

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .entity import BM2Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BM2Recover(entry)])


class BM2Recover(BM2Entity, ButtonEntity):
    _attr_name = "Recover history"
    _attr_icon = "mdi:history"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry):
        super().__init__(entry, "recover")

    async def async_press(self):
        await self.manager.request_recovery(self.battery_id)
