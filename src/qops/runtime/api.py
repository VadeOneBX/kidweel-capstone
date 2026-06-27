from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from qops.runtime.redis_bus import RedisBus
from qops.runtime.settings import settings

router = APIRouter()


class TriggerRequest(BaseModel):
    name: str = "status"
    dry_run: bool = True
    source: str = "api"
    payload: dict[str, Any] = {}


@router.get("/health")
def health() -> dict[str, Any]:
    bus = RedisBus()
    redis_ok = False
    try:
        redis_ok = bus.ping()
    except Exception:
        redis_ok = False
    return {
        "ok": True,
        "service": "qops-api",
        "runtime_mode": settings.qops_runtime_mode,
        "paper_only": settings.qops_paper_only,
        "redis_ok": redis_ok,
    }


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ok": True,
        "paper_only": settings.qops_paper_only,
        "runtime_mode": settings.qops_runtime_mode,
        "mobile_notify_enabled": settings.qops_mobile_notify_enabled,
        "mobile_notify_channel": settings.qops_mobile_notify_channel,
    }


@router.post("/trigger")
def trigger(req: TriggerRequest) -> dict[str, Any]:
    if not settings.qops_paper_only:
        raise HTTPException(status_code=403, detail="PAPER_ONLY_REQUIRED")
    bus = RedisBus()
    bus.publish(
        "qops.trigger",
        {
            "name": req.name,
            "dry_run": req.dry_run,
            "source": req.source,
            "payload": req.payload,
        },
    )
    return {
        "ok": True,
        "accepted": True,
        "name": req.name,
        "dry_run": req.dry_run,
        "source": req.source,
    }


@router.get("/bus/{topic}")
def bus_tail(topic: str, limit: int = 10) -> dict[str, Any]:
    bus = RedisBus()
    return {
        "ok": True,
        "topic": topic,
        "items": bus.tail(topic, limit=limit),
    }
