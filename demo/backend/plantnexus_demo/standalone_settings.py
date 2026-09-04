"""Strict, versioned settings for the Windows standalone Demo package."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
import json
from pathlib import Path
from typing import Any, cast


STANDALONE_SETTINGS_VERSION = "cnc-demo-windows-settings.v1"
DEFAULT_ACCESS_PORT = 4174
DEFAULT_SETTINGS_DOCUMENT: dict[str, object] = {
    "settings_version": STANDALONE_SETTINGS_VERSION,
    "listen_host": "127.0.0.1",
    "access_port": DEFAULT_ACCESS_PORT,
    "lan_mode": False,
    "allowed_networks": [],
    "open_browser": True,
}
DEFAULT_TRUSTED_LAN_NETWORKS = (
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
)
_REQUIRED_FIELDS = frozenset(DEFAULT_SETTINGS_DOCUMENT)
_RFC1918_NETWORKS = tuple(
    cast(IPv4Network, ip_network(value)) for value in DEFAULT_TRUSTED_LAN_NETWORKS
)
_ULA_NETWORK = cast(IPv6Network, ip_network("fc00::/7"))

IPAddress = IPv4Address | IPv6Address
IPNetwork = IPv4Network | IPv6Network


class StandaloneConfigurationError(ValueError):
    """A safe configuration error suitable for a Chinese launcher message."""

    def __init__(self, code: str, *, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(code)


def _parse_ip(value: object, *, field: str) -> IPAddress:
    if not isinstance(value, str) or not value or value != value.strip():
        raise StandaloneConfigurationError("CONFIG_VALUE_INVALID", field=field)
    try:
        return ip_address(value)
    except ValueError as error:
        raise StandaloneConfigurationError("CONFIG_VALUE_INVALID", field=field) from error


def _is_trusted_lan_network(network: IPNetwork) -> bool:
    if isinstance(network, IPv4Network):
        return any(network.subnet_of(parent) for parent in _RFC1918_NETWORKS)
    return network.subnet_of(_ULA_NETWORK)


def parse_trusted_networks(value: object) -> tuple[IPNetwork, ...]:
    if not isinstance(value, list) or len(value) > 16:
        raise StandaloneConfigurationError(
            "CONFIG_VALUE_INVALID", field="allowed_networks"
        )
    networks: list[IPNetwork] = []
    raw_values: set[str] = set()
    for index, raw in enumerate(value):
        field = f"allowed_networks[{index}]"
        if not isinstance(raw, str) or not raw or raw != raw.strip():
            raise StandaloneConfigurationError("CONFIG_VALUE_INVALID", field=field)
        try:
            network = ip_network(raw, strict=True)
        except ValueError as error:
            raise StandaloneConfigurationError(
                "CONFIG_VALUE_INVALID", field=field
            ) from error
        if raw != str(network) or raw in raw_values or not _is_trusted_lan_network(network):
            raise StandaloneConfigurationError("CONFIG_NETWORK_NOT_PRIVATE", field=field)
        raw_values.add(raw)
        networks.append(network)
    return tuple(networks)


@dataclass(frozen=True, slots=True)
class StandaloneSettings:
    settings_version: str
    listen_host: str
    access_port: int
    lan_mode: bool
    allowed_networks: tuple[IPNetwork, ...]
    open_browser: bool

    @classmethod
    def from_document(cls, raw: object) -> StandaloneSettings:
        if not isinstance(raw, dict) or set(raw) != _REQUIRED_FIELDS:
            raise StandaloneConfigurationError("CONFIG_FIELDS_INVALID", field="config")
        document = cast(dict[str, Any], raw)
        if document.get("settings_version") != STANDALONE_SETTINGS_VERSION:
            raise StandaloneConfigurationError(
                "CONFIG_VERSION_UNSUPPORTED", field="settings_version"
            )
        host = _parse_ip(document.get("listen_host"), field="listen_host")
        port = document.get("access_port")
        lan_mode = document.get("lan_mode")
        open_browser = document.get("open_browser")
        if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
            raise StandaloneConfigurationError(
                "CONFIG_VALUE_INVALID", field="access_port"
            )
        if not isinstance(lan_mode, bool):
            raise StandaloneConfigurationError("CONFIG_VALUE_INVALID", field="lan_mode")
        if not isinstance(open_browser, bool):
            raise StandaloneConfigurationError(
                "CONFIG_VALUE_INVALID", field="open_browser"
            )
        networks = parse_trusted_networks(document.get("allowed_networks"))
        if lan_mode:
            if host.is_loopback or (
                not host.is_unspecified
                and not any(
                    host.version == network.version and host in network
                    for network in networks
                )
            ):
                raise StandaloneConfigurationError(
                    "CONFIG_LAN_BIND_INVALID", field="listen_host"
                )
            if not networks:
                raise StandaloneConfigurationError(
                    "CONFIG_LAN_NETWORKS_REQUIRED", field="allowed_networks"
                )
        else:
            if not host.is_loopback:
                raise StandaloneConfigurationError(
                    "CONFIG_LOOPBACK_REQUIRED", field="listen_host"
                )
            if networks:
                raise StandaloneConfigurationError(
                    "CONFIG_LAN_DISABLED", field="allowed_networks"
                )
        return cls(
            settings_version=STANDALONE_SETTINGS_VERSION,
            listen_host=str(host),
            access_port=port,
            lan_mode=lan_mode,
            allowed_networks=networks,
            open_browser=open_browser,
        )

    @classmethod
    def load(cls, path: Path) -> StandaloneSettings:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise StandaloneConfigurationError("CONFIG_READ_FAILED", field="config") from error
        return cls.from_document(raw)

    def to_document(self) -> dict[str, object]:
        return {
            "settings_version": self.settings_version,
            "listen_host": self.listen_host,
            "access_port": self.access_port,
            "lan_mode": self.lan_mode,
            "allowed_networks": [str(network) for network in self.allowed_networks],
            "open_browser": self.open_browser,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(
            self.to_document(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return f"sha256:{sha256(payload).hexdigest()}"

    @property
    def local_url(self) -> str:
        address = ip_address(self.listen_host)
        if address.is_unspecified:
            host = "[::1]" if address.version == 6 else "127.0.0.1"
        else:
            host = f"[{address}]" if address.version == 6 else str(address)
        return f"http://{host}:{self.access_port}/demo/"


def write_default_settings(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            DEFAULT_SETTINGS_DOCUMENT,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


__all__ = [
    "DEFAULT_ACCESS_PORT",
    "DEFAULT_SETTINGS_DOCUMENT",
    "DEFAULT_TRUSTED_LAN_NETWORKS",
    "STANDALONE_SETTINGS_VERSION",
    "StandaloneConfigurationError",
    "StandaloneSettings",
    "parse_trusted_networks",
    "write_default_settings",
]
