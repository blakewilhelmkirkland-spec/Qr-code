"""Extract the real client IP, honoring trusted proxy headers only when the
direct peer is inside a configured trusted CIDR range."""
from __future__ import annotations

import ipaddress
from typing import Iterable, Optional

from starlette.requests import Request


def _parse_networks(cidrs: Iterable[str]) -> list[ipaddress._BaseNetwork]:
    nets: list[ipaddress._BaseNetwork] = []
    for c in cidrs:
        try:
            nets.append(ipaddress.ip_network(c, strict=False))
        except ValueError:
            continue
    return nets


def _ip_in_networks(ip: str, networks: list[ipaddress._BaseNetwork]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in net for net in networks)


def _first_valid_ip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        # Strip optional port and brackets
        if token.startswith("[") and "]" in token:
            token = token[1 : token.index("]")]
        elif token.count(":") == 1 and "." in token:
            token = token.split(":", 1)[0]
        try:
            ipaddress.ip_address(token)
            return token
        except ValueError:
            continue
    return None


def get_client_ip(request: Request, trusted_proxies: Iterable[str]) -> str:
    """Return the best-guess client IP.

    Rules:
      1. Determine the *direct peer* (socket) address.
      2. If the peer is NOT in TRUSTED_PROXIES, ignore all forwarded headers
         (prevents spoofing).
      3. If trusted, walk X-Forwarded-For right-to-left skipping trusted hops,
         falling back to X-Real-IP / CF-Connecting-IP.
    """
    peer = request.client.host if request.client else "0.0.0.0"
    nets = _parse_networks(trusted_proxies)

    if not _ip_in_networks(peer, nets):
        # Direct client — do not trust headers.
        return peer

    # X-Forwarded-For: client, proxy1, proxy2 ...
    xff = request.headers.get("x-forwarded-for")
    if xff:
        # Right-to-left, skipping trusted proxies, return first untrusted.
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        for candidate in reversed(parts):
            try:
                ipaddress.ip_address(candidate)
            except ValueError:
                continue
            if not _ip_in_networks(candidate, nets):
                return candidate
        # All hops trusted — take the leftmost valid IP.
        for candidate in parts:
            try:
                ipaddress.ip_address(candidate)
                return candidate
            except ValueError:
                continue

    for header in ("cf-connecting-ip", "x-real-ip"):
        val = _first_valid_ip(request.headers.get(header))
        if val:
            return val

    return peer