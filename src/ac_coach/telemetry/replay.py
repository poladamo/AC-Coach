"""Bemutató telemetria-forrás: egy rögzített kört játszik vissza valós időben.

Ugyanazt a felületet adja, mint az `ACSharedMemory`, így játék nélkül is
kipróbálható vele a tanácsadó és a webes felület. Körönként kicsit változtat
a tempón, hogy legyen mit értékelni.
"""

from __future__ import annotations

import random
import time

import numpy as np

from ..laps import Lap
from .sample import SessionInfo, TelemetrySample


class ReplaySource:
    def __init__(self, lap: Lap, session: SessionInfo, pace_spread: float = 0.015, seed: int | None = None):
        self.lap = lap
        self.session = session
        self.pace_spread = pace_spread
        self._rng = random.Random(seed)
        self._t_ref = lap.time_ms.astype(np.float64)
        self._t0: float | None = None
        self._lap_no = 0
        self._lap_start = 0.0
        self._factor = 1.0
        self._last_lap_ms = 0
        self._best_lap_ms = 0
        self._packet = 0

    @property
    def connected(self) -> bool:
        return self._t0 is not None

    def connect(self) -> bool:
        if self._t0 is None:
            self._t0 = self._lap_start = time.perf_counter()
            self._factor = 1.0 + self._rng.uniform(-self.pace_spread, self.pace_spread)
        return True

    def refresh_session(self) -> SessionInfo:
        return self.session

    def read(self) -> TelemetrySample:
        now = time.perf_counter()
        lap_ms = self.lap.lap_time_ms * self._factor
        t = (now - self._lap_start) * 1000
        if t >= lap_ms:
            # kör vége
            self._last_lap_ms = int(lap_ms)
            self._best_lap_ms = min(self._best_lap_ms or self._last_lap_ms, self._last_lap_ms)
            self._lap_no += 1
            self._lap_start += lap_ms / 1000
            self._factor = 1.0 + self._rng.uniform(-self.pace_spread, self.pace_spread)
            t = (now - self._lap_start) * 1000

        d = float(np.interp(t / self._factor, self._t_ref, self.lap.distance_m))
        at = lambda ch: self.lap.at(ch, d)
        self._packet += 1
        return TelemetrySample(
            timestamp=now,
            packet_id=self._packet,
            throttle=at("throttle"),
            brake=at("brake"),
            clutch=0.0,
            steer_angle=at("steer_angle"),
            speed_kmh=at("speed_kmh") / self._factor,
            gear=int(round(at("gear"))),
            rpm=0,
            g_lat=at("g_lat"),
            g_lon=at("g_lon"),
            abs_active=0.0,
            tc_active=0.0,
            tyres_out=0,
            track_pos=d / self.session.track_length_m,
            distance_m=d,
            world_x=at("world_x"),
            world_y=at("world_y"),
            world_z=at("world_z"),
            lap=self._lap_no,
            lap_time_ms=int(t),
            last_lap_ms=self._last_lap_ms,
            best_lap_ms=self._best_lap_ms,
            in_pit=False,
            is_live=True,
        )

    def close(self) -> None:
        self._t0 = None
