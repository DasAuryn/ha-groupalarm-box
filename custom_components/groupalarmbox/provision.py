from __future__ import annotations

import logging
import socket
import time
from typing import Dict, Any

_LOGGER = logging.getLogger(__name__)

UDP_RETRIES_DEFAULT = 3
UDP_DELAY_SEC_DEFAULT = 0.8


def _looks_like_ip(host: str) -> bool:
    try:
        socket.inet_aton(host)
        return True
    except Exception:
        return False


def _resolve_host_to_ip(host: str) -> str:
    if not host:
        return ""
    if _looks_like_ip(host):
        return host
    try:
        return socket.gethostbyname(host)
    except Exception:
        return ""


def build_payload(cfg: Dict[str, Any]) -> bytes:
    host = (cfg.get("mqtt_host") or "").strip()
    port = int(cfg.get("mqtt_port") or 1883)
    user = (cfg.get("mqtt_user") or "").strip()
    pwd = (cfg.get("mqtt_password") or "").strip()
    prefix = (cfg.get("mqtt_prefix") or "homeassistant").strip()

    host_ip = (cfg.get("mqtt_host_ip") or "").strip()
    if not host_ip:
        host_ip = _resolve_host_to_ip(host)

    parts = [
        f"host={host}",
        f"host_ip={host_ip}",
        f"port={port}",
        f"user={user}",
        f"pass={pwd}",
        f"prefix={prefix}",
    ]
    return (";".join(parts)).encode("utf-8")


def send_udp(ip: str, cfg: Dict[str, Any]) -> None:
    udp_port = int(cfg.get("udp_port") or 42424)
    retries = int(cfg.get("udp_retries") or UDP_RETRIES_DEFAULT)
    delay = float(cfg.get("udp_delay") or UDP_DELAY_SEC_DEFAULT)

    payload = build_payload(cfg)
    addr = (ip, udp_port)

    _LOGGER.info("UDP Provisioning -> %s:%s payload='%s'", ip, udp_port, payload.decode("utf-8", errors="ignore"))

    for attempt in range(1, retries + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.sendto(payload, addr)
            return
        except Exception as err:
            _LOGGER.warning("UDP Provisioning fehlgeschlagen (%s:%s) Versuch %d/%d: %s", ip, udp_port, attempt, retries, err)
            time.sleep(delay)
