from __future__ import annotations

import ipaddress
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GeoIP:
    def __init__(self, db_path: str | None) -> None:
        self._reader = None
        self._db_path = db_path or ""
        if self._db_path:
            try:
                import maxminddb  # type: ignore

                self._reader = maxminddb.open_database(self._db_path)
                logger.info("GeoIP database loaded: %s", self._db_path)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load GeoIP db %s: %s", self._db_path, exc)
                self._reader = None

    @property
    def enabled(self) -> bool:
        return self._reader is not None

    def lookup(self, ip: str) -> dict[str, Any]:
        if self._reader is None:
            return {}
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            return {}
        try:
            data = self._reader.get(ip) or {}
        except Exception:  # noqa: BLE001
            return {}

        result: dict[str, Any] = {}
        country = data.get("country") or data.get("registered_country") or {}
        result["country"] = (country.get("iso_code") or country.get("names", {}).get("en")) if country else None
        city = data.get("city") or {}
        result["city"] = city.get("names", {}).get("en") if city else None
        loc = data.get("location") or {}
        result["latitude"] = loc.get("latitude")
        result["longitude"] = loc.get("longitude")
        asn = data.get("traits", {}).get("autonomous_system_number")
        result["asn"] = asn
        return {k: v for k, v in result.items() if v is not None}

    def close(self) -> None:
        if self._reader is not None:
            try:
                self._reader.close()
            except Exception:  # noqa: BLE001
                pass
            self._reader = None


_geo: Optional[GeoIP] = None


def get_geoip() -> GeoIP:
    global _geo
    if _geo is None:
        from .config import get_settings

        _geo = GeoIP(get_settings().geoip_db)
    return _geo