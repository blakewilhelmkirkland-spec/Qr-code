from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class HitOut(BaseModel):
    id: int
    ts: datetime
    ip: str
    method: str
    path: str
    query_string: str
    user_agent: str
    referer: str
    accept_language: str
    country: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    asn: Optional[int] = None

    model_config = {"from_attributes": True}


class TopIP(BaseModel):
    ip: str
    hits: int


class StatsOut(BaseModel):
    total_hits: int
    unique_ips: int
    top_ips: list[TopIP]
    window_started_at: datetime
    window_ended_at: datetime