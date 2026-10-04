# IP Logger

Self-contained IP logging service. `GET /log` returns a 1×1 transparent GIF
and records the request.

## Quickstart

```bash
cp .env.example .env
docker compose up --build
curl -I http://localhost:8000/log
```

## Endpoints

| Method | Path       | Auth            | Description                          |
|--------|------------|-----------------|--------------------------------------|
| GET    | `/log`     | none            | Logs request, returns 1×1 GIF        |
| GET    | `/stats`   | `X-Admin-Token` | Top 20 IPs by hits + totals          |
| GET    | `/healthz` | none            | Liveness                             |

```bash
curl -H "X-Admin-Token: $ADMIN_TOKEN" http://localhost:8000/stats
```

## Client IP resolution

Forwarded headers (`X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP`) are only
trusted when the **direct peer** is inside `TRUSTED_PROXIES` (comma-separated
CIDRs). Otherwise the socket peer address is used, preventing spoofing.

## Storage

- Default: SQLite at `./data/iplogger.db` (`sqlite+aiosqlite:///...`)
- Postgres: set `DATABASE_URL=postgresql+asyncpg://user:pass@host/db`
- Every hit is emitted as a **JSON line** to stdout and inserted into the DB.

## GeoIP

Set `GEOIP_DB=/path/to/GeoLite2-City.mmdb`. Fields populated: `country`,
`city`, `latitude`, `longitude`, `asn`.

## Rate limiting

Fixed-window, per resolved client IP, `RATE_LIMIT_PER_MINUTE` (default 60).
Exceeded requests still receive the GIF but with HTTP 429 and `Retry-After`.

## Security notes

- `/stats` requires `ADMIN_TOKEN`; if left as default the endpoint returns 503.
- No third-party analytics, no external calls, no embedded pixels.
- Deploy behind a reverse proxy and set `TRUSTED_PROXIES` to the proxy CIDRs.