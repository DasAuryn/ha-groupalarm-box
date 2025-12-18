from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import (
    DOMAIN,
    CONF_DEVICE_IP,
    CONF_DEVICE_NAME,
    CONF_DEVICE_MAC,
    CONF_UDP_PORT,
    DEFAULT_UDP_PORT,
    CONF_MQTT_PREFIX,
    DEFAULT_MQTT_PREFIX,
    CONF_TARGETS,
)


class GroupAlarmBoxConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo) -> FlowResult:
        host = discovery_info.host
        name = discovery_info.name or "GroupAlarm Box"

        props = discovery_info.properties or {}
        mac = props.get("mac") or props.get("mac_address") or props.get("id")
        if isinstance(mac, bytes):
            mac = mac.decode(errors="ignore")

        unique = (mac or host or name).lower()
        await self.async_set_unique_id(unique)
        self._abort_if_unique_id_configured(
            updates={
                CONF_DEVICE_IP: host,
                CONF_DEVICE_NAME: name,
                CONF_DEVICE_MAC: mac or "",
            }
        )

        self._discovered = {
            CONF_DEVICE_IP: host,
            CONF_DEVICE_NAME: name,
            CONF_DEVICE_MAC: mac or "",
        }

        return await self.async_step_user()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            data = {**getattr(self, "_discovered", {}), **user_input}
            title = data.get(CONF_DEVICE_NAME) or "GroupAlarm Box"
            return self.async_create_entry(title=title, data=data)

        schema = vol.Schema(
            {
                vol.Optional(CONF_MQTT_PREFIX, default=DEFAULT_MQTT_PREFIX): str,
                vol.Optional(CONF_UDP_PORT, default=DEFAULT_UDP_PORT): vol.Coerce(int),
                vol.Optional(CONF_TARGETS, default=DEFAULT_MQTT_PREFIX): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return GroupAlarmBoxOptionsFlowHandler(config_entry)


class GroupAlarmBoxOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        cur = {**self._config_entry.data, **self._config_entry.options}

        schema = vol.Schema(
            {
                vol.Optional(CONF_MQTT_PREFIX, default=cur.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX)): str,
                vol.Optional(CONF_UDP_PORT, default=cur.get(CONF_UDP_PORT, DEFAULT_UDP_PORT)): vol.Coerce(int),
                vol.Optional(CONF_TARGETS, default=cur.get(CONF_TARGETS, "")): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
