"""Körök rögzítése az élő telemetriából.

A mintákat körönként gyűjti, a kör végén (amikor a játék körszámlálója lép)
egyenletes távolságrácsra mintavételezi őket, és `Lap`-ot ad vissza.

Nem ad vissza kört, ha az nem teljes: menet közben indultunk, újraindult a menet,
visszaugrottunk a boxba, vagy a minták nem fedik le a teljes pályát.
Érvénytelen (de visszaadott) a kör, ha közben boxban jártunk, vagy túl sok kerék
hagyta el a pályát.
"""

from __future__ import annotations

import numpy as np

from ..telemetry import SessionInfo, TelemetrySample
from .lap import CHANNELS, Lap

# Ennyi méter hiányozhat a kör elejéről / végéről (ritka mintavétel miatt).
_COVERAGE_TOLERANCE_M = 30.0


class LapRecorder:
    def __init__(self, session: SessionInfo, step_m: float = 1.0, max_tyres_out: int = 2):
        self.session = session
        self.step_m = step_m
        self.max_tyres_out = max_tyres_out
        self._lap_no: int | None = None
        self._samples: list[TelemetrySample] = []
        self._partial = True      # az első, félbe kezdett kört eldobjuk
        self._invalid = False
        self._last_packet: int | None = None

    @property
    def current_lap_invalid(self) -> bool:
        return self._invalid

    def push(self, s: TelemetrySample) -> Lap | None:
        """Új minta. Ha egy teljes kör véget ért, visszaadja azt."""
        if not s.is_live or s.packet_id == self._last_packet:
            return None
        self._last_packet = s.packet_id

        finished = None
        if self._lap_no is None:
            self._start_lap(s, partial=True)
        elif s.lap == self._lap_no + 1:
            finished = self._finish_lap(s.last_lap_ms)
            self._start_lap(s, partial=False)
        elif s.lap != self._lap_no:
            # menet-újraindítás vagy ugrás a körszámlálóban
            self._start_lap(s, partial=True)
        elif self._samples and s.lap_time_ms + 500 < self._samples[-1].lap_time_ms:
            # a köridő visszaugrott (pl. vissza a boxba) – ez a kör már nem teljes
            self._partial = True

        if s.in_pit:
            self._invalid = True
        if s.tyres_out > self.max_tyres_out:
            self._invalid = True
        self._samples.append(s)
        return finished

    def _start_lap(self, s: TelemetrySample, partial: bool) -> None:
        self._lap_no = s.lap
        self._samples = []
        self._partial = partial
        self._invalid = False

    def _finish_lap(self, lap_time_ms: int) -> Lap | None:
        if self._partial or len(self._samples) < 10 or lap_time_ms <= 0:
            return None
        channels = resample_lap(self._samples, self.session.track_length_m, self.step_m)
        if channels is None:
            return None
        return Lap(
            car=self.session.car,
            track=self.session.track_id,
            lap_time_ms=lap_time_ms,
            valid=not self._invalid,
            step_m=self.step_m,
            channels=channels,
        )


def resample_lap(
    samples: list[TelemetrySample], track_length_m: float, step_m: float
) -> dict[str, np.ndarray] | None:
    """Egy kör mintái egyenletes távolságrácsra. None, ha nem fedik le a pályát."""
    L = track_length_m
    raw = np.array([s.track_pos for s in samples], dtype=np.float64) * L

    # Átfordulás kezelése: a pozíció a célvonal körül 1 -> 0 ugrik, és a
    # körszámláló nem pontosan ugyanott lép, mint a pozíció.
    dist = np.empty_like(raw)
    offset = -L if raw[0] > 0.5 * L else 0.0
    prev = raw[0] + offset
    dist[0] = prev
    for i in range(1, len(raw)):
        d = raw[i] + offset
        if d - prev < -0.5 * L:
            offset += L
            d += L
        elif d - prev > 0.5 * L:
            offset -= L
            d -= L
        dist[i] = d
        prev = d

    # Csak a szigorúan előre haladó mintákat tartjuk meg (megállás, tolatás ki).
    keep = np.zeros(len(dist), dtype=bool)
    running = -np.inf
    for i, d in enumerate(dist):
        if d > running:
            keep[i] = True
            running = d
    dist = dist[keep]

    if dist[0] > _COVERAGE_TOLERANCE_M or dist[-1] < L - _COVERAGE_TOLERANCE_M:
        return None

    grid = np.arange(0.0, L, step_m)
    kept = [s for s, k in zip(samples, keep) if k]
    out: dict[str, np.ndarray] = {}
    for name in CHANNELS:
        values = np.array([getattr(s, name) for s in kept], dtype=np.float64)
        out[name] = np.interp(grid, dist, values).astype(np.float32)
    # A fokozat egész szám: interpoláció helyett a legközelebbi mintát vesszük.
    idx = np.clip(np.searchsorted(dist, grid), 0, len(kept) - 1)
    out["gear"] = np.array([kept[i].gear for i in idx], dtype=np.float32)
    return out
