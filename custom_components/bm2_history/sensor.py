"""One canonical live voltage entity per physical battery."""

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfElectricPotential

from .entity import BM2Entity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BM2Voltage(entry)])


class BM2Voltage(BM2Entity, SensorEntity):
    _attr_name = "Voltage"
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(self, entry):
        super().__init__(entry, "voltage")

    @property
    def available(self):
        return self.fresh_source is not None

    @property
    def native_value(self):
        source = self.fresh_source
        return float(source.state) if source else None

    @property
    def extra_state_attributes(self):
        state = self.manager.saved.get(self.battery_id, {})
        source = self.manager.live.get(self.battery_id)
        return {
            "battery_id": self.battery_id,
            "source_entity": source.entity_id if source else None,
            "last_reported": source.last_reported.isoformat() if source else None,
            "history_statistic_id": f"bm2_history:{self.battery_id}_voltage",
            "recovery_pending": state.get("pending", False),
            "last_history_sync": state.get("last_sync"),
            "last_history_error": state.get("last_error"),
        }
