from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

import redis

from qops.runtime.settings import settings


@dataclass(frozen=True)
class BusMessage:
    topic: str
    payload: dict[str, Any]
    ts: float


class RedisBus:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url or settings.redis_url
        self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)

    def ping(self) -> bool:
        return bool(self.client.ping())

    def publish(self, topic: str, payload: dict[str, Any]) -> int:
        message = BusMessage(topic=topic, payload=payload, ts=time.time())
        encoded = json.dumps(message.__dict__, default=str)
        self.client.lpush(f"qops:bus:{topic}", encoded)
        self.client.ltrim(f"qops:bus:{topic}", 0, 99)
        return int(self.client.publish(topic, encoded))

    def tail(self, topic: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.client.lrange(f"qops:bus:{topic}", 0, max(limit - 1, 0))
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row))
            except json.JSONDecodeError:
                out.append({"raw": row})
        return out
