"""Egy rögzített kör, a pálya mentén egyenletes távolságrácsra mintavételezve."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

# Csatornák, amelyeket körönként rögzítünk (TelemetrySample mezőnevek).
CHANNELS = (
    "lap_time_ms",
    "speed_kmh",
    "throttle",
    "brake",
    "steer_angle",
    "gear",
    "g_lat",
    "g_lon",
    "world_x",
    "world_y",
    "world_z",
)


@dataclass
class Lap:
    car: str
    track: str
    lap_time_ms: int
    valid: bool
    step_m: float
    channels: dict[str, np.ndarray]   # mind azonos hosszú, index = távolság / step_m
    recorded_at: datetime = field(default_factory=datetime.now)
    id: int | None = None

    @property
    def distance_m(self) -> np.ndarray:
        return np.arange(len(self)) * self.step_m

    @property
    def time_ms(self) -> np.ndarray:
        return self.channels["lap_time_ms"]

    def __len__(self) -> int:
        return len(self.channels["lap_time_ms"])

    def at(self, channel: str, distance_m: float) -> float:
        """Egy csatorna értéke tetszőleges távolságnál (lineáris interpoláció)."""
        return float(np.interp(distance_m, self.distance_m, self.channels[channel]))

    def to_bytes(self) -> bytes:
        buf = io.BytesIO()
        np.savez_compressed(buf, **self.channels)
        return buf.getvalue()

    @staticmethod
    def channels_from_bytes(blob: bytes) -> dict[str, np.ndarray]:
        with np.load(io.BytesIO(blob)) as npz:
            return {k: npz[k] for k in npz.files}
