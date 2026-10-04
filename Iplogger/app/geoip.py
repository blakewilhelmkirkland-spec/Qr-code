from __future__ import annotations

import ipaddress
import logging
import urllib.request
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _ensure_db(db_path: str) -> Optional[str]:
    """Resolve a GeoIP DB path.

    Supports:
      - HTTP(S) URLs → downloaded to /tmp and cached
      - Local file paths → used directly
    Returns the local path to the .mmdb, or None on failure.
    """
    if not db_path:
        return None

    # URL: download and cache
    if db_path.startswith("http://") or db_path.startswith("https://"):
        local = Path("/tmp/GeoLite2-City.mmdb")
        # Reuse cached copy if it looks like a real DB (>1MB)
        try:
            if local.exists() and local.stat().st_size > 1_000_000:
                return str(local)
        except OSError:
            pass
        try:
            logger.info("Downloading GeoIP DB from %s ...", db_path)
            tmp = local.with_suffix(".part")
            with urllib.request.urlopen(db_path, timeout=60) as resp, open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
            tmp.replace(local)
            logger.info("GeoIP DB downloaded (%d bytes) -> %s", local.stat().st_size, local)
            return str(local)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to download GeoIP DB: %s", exc)
            return None

    # Local path
    p = Path(db_path)
    if p.exists():
        return str(p)
    logger.warning("GeoIP DB path does not exist: %s", db_path)
    return None


class GeoIP:
    def __init__(self, db_path: str | None) -> None:
        self._reader = None
        self._db_path = db_path or ""
        resolved = _ensure_db(self._db_path)
        if resolved:
            try:
                import maxminddb  # type: ignore

                self._reader = maxminddb.open_database(resolved)
                logger.info("GeoIP database loaded: %s", resolved)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to load GeoIP db %s: %s", resolved, exc)
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
        result["country"] = (
            country.get("iso_code") or country.get("names", {}).get("en")
        ) if country else None

        city = data.get("city") or {}
        result["city"] = city.get("names", {}).get("en") if city else None

        subdivisions = data.get("subdivisions") or []
        if subdivisions:
            result["region"] = subdivisions[0].get("names", {}).get("en")

        loc = data.get("location") or {}
        result["latitude"] = loc.get("latitude")
        result["longitude"] = loc.get("longitude")
        result["timezone"] = loc.get("time_zone")

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
