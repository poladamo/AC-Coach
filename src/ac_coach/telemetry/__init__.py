"""Telemetria-források. Mindegyik a közös `TelemetrySample` formátumot adja vissza."""

from .sample import TelemetrySample, SessionInfo
from .ac_shared_memory import ACSharedMemory

__all__ = ["TelemetrySample", "SessionInfo", "ACSharedMemory"]
