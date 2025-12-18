from __future__ import annotations

import logging
from urllib.parse import urlparse

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import network

from .const import (
    DOMAIN,
    CONF_DEVICE_IP,
    CONF_UDP_PORT,
    DEFAULT_UDP_PORT,
    CONF_MQTT_PREFIX,
    DEFAULT_MQTT_PREFIX,
)
from .provision import send_udp

_LOGGER = logging.getLogger(__name__)

MQTT_DOMAIN = "mqtt"


def _pick_reachable_broker_host(hass: HomeAssistant, broker: str) -> str:
    if broker in ("core-mosquitto", "localhost", "127.0.0.1"):
        try:
            url = network.get_url(hass, allow_internal=True, allow_external=False)
            host = urlparse(url).hostname
            if host:
                return host
        except Exception:  
            pass
    return broker


def _get_mqtt_broker_settings(hass: HomeAssistant) -> dict | None:
    entries = hass.config_entries.async_entries(MQTT_DOMAIN)
    if not entries:
        return None

    entry = entries[0]
    data = {**entry.data, **entry.options}

    broker = data.get("broker") or data.get("host") or data.get("mqtt_host")
    port = data.get("port") or data.get("mqtt_port") or 1883
    username = data.get("username") or data.get("user") or ""
    password = data.get("password") or ""

    if not broker:
        return None

    broker = _pick_reachable_broker_host(hass, str(broker))

    return {
        "host": str(broker),
        "port": int(port),
        "username": str(username),
        "password": str(password),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    await _provision(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await _provision(hass, entry)


async def _provision(hass: HomeAssistant, entry: ConfigEntry) -> None:
    ip = entry.data.get(CONF_DEVICE_IP)
    if not ip:
        _LOGGER.warning("No device IP in config entry, cannot provision.")
        return

    mqtt = _get_mqtt_broker_settings(hass)
    if not mqtt:
        _LOGGER.warning("MQTT integration not configured/found. Cannot provision MQTT settings to box.")
        return

    udp_port = entry.options.get(CONF_UDP_PORT, entry.data.get(CONF_UDP_PORT, DEFAULT_UDP_PORT))
    prefix = entry.options.get(CONF_MQTT_PREFIX, entry.data.get(CONF_MQTT_PREFIX, DEFAULT_MQTT_PREFIX))

    cfg = {
        "mqtt_host": mqtt["host"],
        "mqtt_port": mqtt["port"],
        "mqtt_user": mqtt["username"],
        "mqtt_password": mqtt["password"],
        "mqtt_prefix": prefix,
        "udp_port": int(udp_port),
    }

    await hass.async_add_executor_job(send_udp, ip, cfg)
    _LOGGER.info("Provisioned GroupAlarmBox %s via UDP with HA MQTT settings (broker=%s:%s)", ip, mqtt["host"], mqtt["port"])
