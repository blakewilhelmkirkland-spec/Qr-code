from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hit(Base):
    __tablename__ = "hits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False, index=True)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(2048), nullable=False)
    query_string: Mapped[str] = mapped_column(Text, default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)
    referer: Mapped[str] = mapped_column(Text, default="", nullable=False)
    accept_language: Mapped[str] = mapped_column(Text, default="", nullable=False)
    headers_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    asn: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


Index("ix_hits_ip_ts", Hit.ip, Hit.ts)