from __future__ import annotations

import httpx

from shared.adapters.geo.port import GeoResult
from shared.adapters.observability.logger import get_logger

log = get_logger(__name__)

_PRIVATE_PREFIXES = ("10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.",
                     "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.",
                     "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
                     "192.168.", "127.", "::1", "")


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE_PREFIXES)


class IpApiGeoService:
    """Resolve geolocalização via ip-api.com (gratuito, sem chave, ~45 req/min)."""

    async def lookup(self, ip: str) -> GeoResult | None:
        if _is_private(ip):
            return None
        url = f"http://ip-api.com/json/{ip}?fields=status,city,country,regionName"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url)
                data = resp.json()
                if data.get("status") != "success":
                    return None
                return GeoResult(
                    city=data.get("city", ""),
                    country=data.get("country", ""),
                    region=data.get("regionName", ""),
                )
        except Exception:
            log.warning("geo_lookup_failed", ip=ip)
            return None
