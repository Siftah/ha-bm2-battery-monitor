"""Set up a physical BM2 battery and select its ESPHome receiver sensors."""

import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import DEFAULT_OFFLINE_AFTER, DEFAULT_SYNC_INTERVAL, DOMAIN


def settings_schema(defaults):
    return vol.Schema(
        {
            vol.Required(
                "voltage_sources", default=defaults.get("voltage_sources", [])
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor", device_class="voltage", multiple=True
                )
            ),
            vol.Required(
                "offline_after", default=defaults.get("offline_after", DEFAULT_OFFLINE_AFTER)
            ): vol.All(vol.Coerce(int), vol.Range(min=60)),
            vol.Required(
                "sync_interval", default=defaults.get("sync_interval", DEFAULT_SYNC_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=3600)),
        }
    )


def source_errors(hass, data):
    if not data["voltage_sources"]:
        return {"voltage_sources": "no_sources"}
    registry = er.async_get(hass)
    if any(
        (entry := registry.async_get(source)) and entry.platform == DOMAIN
        for source in data["voltage_sources"]
    ):
        return {"voltage_sources": "recursive_source"}
    return {}


class BM2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            data = dict(user_input)
            data["mac_address"] = data["mac_address"].strip().upper()
            if not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", data["mac_address"]):
                errors["mac_address"] = "invalid_mac"
            if not re.fullmatch(r"[a-z0-9]+(?:_[a-z0-9]+)*", data["battery_id"]):
                errors["battery_id"] = "invalid_battery_id"
            errors.update(source_errors(self.hass, data))
            if not errors:
                await self.async_set_unique_id(data["mac_address"])
                self._abort_if_unique_id_configured()
                if any(
                    entry.data["battery_id"] == data["battery_id"]
                    for entry in self._async_current_entries()
                ):
                    errors["battery_id"] = "duplicate_battery_id"
                else:
                    options = {
                        key: data.pop(key)
                        for key in ("voltage_sources", "offline_after", "sync_interval")
                    }
                    return self.async_create_entry(title=data["name"], data=data, options=options)
        defaults = user_input or {}
        schema = vol.Schema(
            {
                vol.Required("name", default=defaults.get("name", "Starter Battery")): str,
                vol.Required(
                    "battery_id", default=defaults.get("battery_id", "starter_battery")
                ): str,
                vol.Required("mac_address", default=defaults.get("mac_address", "")): str,
            }
        ).extend(settings_schema(defaults).schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, user_input):
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BM2OptionsFlow()


class BM2OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = source_errors(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=settings_schema(user_input or self.config_entry.options),
            errors=errors,
        )
