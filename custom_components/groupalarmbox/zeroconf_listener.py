from __future__ import annotations

import socket
import logging
from typing import Any, List

from homeassistant.core import HomeAssistant
from zeroconf import ServiceBrowser

from .provision import send_udp

_LOGGER = logging.getLogger(__name__)


class GroupAlarmBoxZeroconfListener:
    def __init__(
        self,
        hass: HomeAssistant,
        zeroconf: Any,
        targets: List[str],
        udp_port: int,
        mqtt_cfg: dict,
    ) -> None:
        self.hass = hass
        self.zeroconf = zeroconf
        self.targets = [t.lower() for t in (targets or [])]
        self.udp_port = int(udp_port)
        self.mqtt_cfg = mqtt_cfg or {}

        self._provisioned_devices: set[str] = set()
        self._browser: ServiceBrowser | None = None

    def _matches(self, name: str, server: str | None) -> bool:
        name_l = (name or "").lower()
        server_l = (server or "").lower()
        return any(t in name_l or t in server_l for t in self.targets)

    def _extract_device_id(self, name: str, txt_mac: str | None = None) -> str:
        if txt_mac:
            return txt_mac.replace(":", "").lower()

        base = (name or "").split("._")[0]
        if "-" in base:
            return base.split("-", 1)[1].lower()
        return base.lower()

    async def async_service_update(self, service_type: str, name: str, state_change) -> None:
        zc = getattr(self.zeroconf, "zeroconf", self.zeroconf)

        info = await self.hass.async_add_executor_job(zc.get_service_info, service_type, name)
        if not info or not getattr(info, "addresses", None):
            return

        if not self._matches(name, getattr(info, "server", None)):
            return

        ip = socket.inet_ntoa(info.addresses[0])

        txt_mac = None
        try:
            props = getattr(info, "properties", None) or {}
            if b"mac" in props:
                txt_mac = props[b"mac"].decode(errors="ignore")
            elif "mac" in props:
                txt_mac = str(props["mac"])
        except Exception:
            txt_mac = None

        device_id = self._extract_device_id(name, txt_mac)

        if device_id in self._provisioned_devices:
            return
        self._provisioned_devices.add(device_id)

        sensor_id = f"sensor.groupalarmbox_{device_id}_ip"
        _LOGGER.info("GroupAlarmBox gefunden: %s (device_id=%s, ip=%s)", name, device_id, ip)

        self.hass.states.async_set(
            sensor_id,
            ip,
            {"friendly_name": f"GroupAlarmBox {device_id}", "icon": "mdi:ip"},
        )

        cfg = dict(self.mqtt_cfg)
        cfg["udp_port"] = self.udp_port

        await self.hass.async_add_executor_job(send_udp, ip, cfg)

    def _handle_service(self, zeroconf, service_type, name, state_change):
        self.hass.loop.call_soon_threadsafe(
            self.hass.async_create_task,
            self.async_service_update(service_type, name, state_change),
        )

    async def async_start(self) -> None:
        zc = getattr(self.zeroconf, "zeroconf", self.zeroconf)
        self._browser = ServiceBrowser(
            zc,
            ["_http._tcp.local."],
            handlers=[self._handle_service],
        )

    async def async_stop(self) -> None:
        if self._browser is not None:
            try:
                self._browser.cancel()
            except Exception:
                pass
            self._browser = None
