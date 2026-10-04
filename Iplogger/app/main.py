from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from sqlalchemy import desc, func, select

from .client_ip import get_client_ip
from .config import get_settings
from .db import dispose_db, get_sessionmaker, init_db
from .geoip import get_geoip
from .logging_utils import configure_logging, headers_to_dict
from .models import Hit
from .ratelimit import RateLimiter
from .schemas import StatsOut, TopIP

# 1x1 transparent GIF (43 bytes)
TRANSPARENT_GIF = bytes.fromhex(
    "47494638396101000100800000ffffff00000021f90401000000002c00000000"
    "010001000002024401003b"
)

access_logger = logging.getLogger("iplogger.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    await init_db()
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.state.settings = settings
    try:
        yield
    finally:
        get_geoip().close()
        await dispose_db()


app = FastAPI(title="IP Logger", version="1.0.0", lifespan=lifespan)


def _require_admin(
    request: Request,
    authorization: str | None = Header(default=None),
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    settings: object = request.app.state.settings
    expected = getattr(settings, "admin_token", None)
    if not expected or expected == "change-me-please":
        # Refuse to serve admin endpoints if token not configured.
        if expected == "change-me-please":
            raise HTTPException(status_code=503, detail="ADMIN_TOKEN not configured")
    provided = x_admin_token
    if not provided and authorization and authorization.lower().startswith("bearer "):
        provided = authorization[7:].strip()
    if not provided or provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@app.get("/log")
async def log_hit(request: Request) -> Response:
    settings = request.app.state.settings
    client_ip = get_client_ip(request, settings.trusted_proxy_list)

    limiter: RateLimiter = request.app.state.rate_limiter
    allowed, retry_after = limiter.check(client_ip)
    if not allowed:
        return Response(
            content=TRANSPARENT_GIF,
            media_type="image/gif",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after), "Cache-Control": "no-store"},
        )

    headers = headers_to_dict(request)
    ua = request.headers.get("user-agent", "")
    referer = request.headers.get("referer", "")
    accept_language = request.headers.get("accept-language", "")
    query_string = request.url.query or ""
    ts = datetime.now(timezone.utc)

    geo = get_geoip().lookup(client_ip) if get_geoip().enabled else {}

    record = Hit(
        ts=ts,
        ip=client_ip,
        method=request.method,
        path=request.url.path,
        query_string=query_string,
        user_agent=ua,
        referer=referer,
        accept_language=accept_language,
        headers_json=json.dumps(headers, separators=(",", ":"), ensure_ascii=False),
        country=geo.get("country"),
        city=geo.get("city"),
        latitude=geo.get("latitude"),
        longitude=geo.get("longitude"),
        asn=geo.get("asn"),
    )

    # Persist
    sessionmaker = get_sessionmaker()
    try:
        async with sessionmaker() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
    except Exception as exc:  # noqa: BLE001
        # Never break tracking pixel delivery due to DB failure.
        access_logger.error(
            "db_insert_failed",
            extra={"extra_fields": {"ip": client_ip, "error": str(exc)}},
        )

    # Structured JSON-lines to stdout
    access_logger.info(
        "hit",
        extra={
            "extra_fields": {
                "id": record.id,
                "ts": ts.isoformat(),
                "ip": client_ip,
                "method": request.method,
                "path": request.url.path,
                "query_string": query_string,
                "user_agent": ua,
                "referer": referer,
                "accept_language": accept_language,
                "country": geo.get("country"),
                "city": geo.get("city"),
                "asn": geo.get("asn"),
                "headers": headers,
            }
        },
    )

    return Response(
        content=TRANSPARENT_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, private",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/stats", response_model=StatsOut, dependencies=[Depends(_require_admin)])
async def stats(request: Request) -> StatsOut:
    now = datetime.now(timezone.utc)
    window_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        total = (await session.execute(select(func.count(Hit.id)))).scalar_one()
        unique = (await session.execute(select(func.count(func.distinct(Hit.ip))))).scalar_one()
        rows = (
            await session.execute(
                select(Hit.ip, func.count(Hit.id).label("hits"))
                .group_by(Hit.ip)
                .order_by(desc("hits"))
                .limit(20)
            )
        ).all()

    top = [TopIP(ip=r[0], hits=int(r[1])) for r in rows]
    return StatsOut(
        total_hits=int(total),
        unique_ips=int(unique),
        top_ips=top,
        window_started_at=window_start,
        window_ended_at=now,
    )


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}