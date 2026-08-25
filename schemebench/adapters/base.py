from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class Trace:
    provider: str
    model: str
    scenario_id: str
    timestamp: str
    latency_ms: float
    text_output: str
    tool_calls: list
    raw_request: dict
    raw_response: dict
    error: str = None


class ModelAdapter(ABC):
    provider: str = "unknown"

    @abstractmethod
    def available(self) -> bool:
        """Return True if this adapter has the credentials it needs."""
        ...

    @abstractmethod
    def run(self, scenario, model: str) -> Trace:
        """Run the scenario's probe against the given model, return a normalized Trace."""
        ...

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _timed(self, fn):
        start = time.monotonic()
        result = fn()
        latency_ms = (time.monotonic() - start) * 1000
        return result, latency_ms
