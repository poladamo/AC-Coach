"""Az AC pályák AI ideálív fájljának (ai/fast_lane.ai) beolvasása.

Fájlszerkezet (little-endian):
  fejléc:   int32 version (7), int32 pontszám N, int32, int32
  N pont:   float32 x, y, z, float32 távolság a pálya mentén, int32 id
  int32 N:  kiegészítő adatok száma
  N × 18 float32:
     0 speed      – a felvételkori sebesség (m/s); NEM célsebesség, használhatatlan
     1 gas, 2 brake – a felvételkori pedálállás; szintén használhatatlan
     3 obsoleteLatG, 4 radius (kanyarsugár, m)
     5 sideLeft, 6 sideRight (pályaszélesség az ívtől, m)
     7 camber, 8 direction, 9-11 normal, 12 length, 13-15 forward, 16 tag, 17 grade
  ezután további blokkok (rács, egyéb), ezeket nem használjuk.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_POINT = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("dist", "<f4"), ("id", "<i4")])
_EXTRA_FLOATS = 18


@dataclass(frozen=True)
class AILine:
    position: np.ndarray      # (N, 3) világkoordináták
    distance_m: np.ndarray    # (N,) távolság a pálya mentén
    radius_m: np.ndarray      # (N,) kanyarsugár
    width_left_m: np.ndarray  # (N,) pályaszél balra az ívtől
    width_right_m: np.ndarray # (N,) pályaszél jobbra az ívtől
    forward: np.ndarray       # (N, 3) haladási irány

    @property
    def length_m(self) -> float:
        return float(self.distance_m[-1])

    def __len__(self) -> int:
        return len(self.distance_m)


def load_ai_line(path: Path) -> AILine:
    data = path.read_bytes()
    version, n, _, _ = struct.unpack_from("<4i", data, 0)
    if version != 7:
        raise ValueError(f"Ismeretlen fast_lane.ai verzió: {version} ({path})")
    if n < 2:
        raise ValueError(f"Üres AI ív: {path}")

    pts = np.frombuffer(data, dtype=_POINT, count=n, offset=16)
    off = 16 + _POINT.itemsize * n
    (n_extra,) = struct.unpack_from("<i", data, off)
    if n_extra != n:
        raise ValueError(f"Pontszám eltérés ({n} vs {n_extra}): {path}")
    ex = np.frombuffer(data, dtype="<f4", count=n * _EXTRA_FLOATS, offset=off + 4)
    ex = ex.reshape(n, _EXTRA_FLOATS).astype(np.float64)

    return AILine(
        position=np.column_stack([pts["x"], pts["y"], pts["z"]]).astype(np.float64),
        distance_m=pts["dist"].astype(np.float64),
        radius_m=ex[:, 4],
        width_left_m=ex[:, 5],
        width_right_m=ex[:, 6],
        forward=ex[:, 13:16],
    )


def find_ai_line(ac_path: Path, track: str, layout: str = "") -> Path | None:
    """A pálya (és változat) fast_lane.ai fájljának helye, ha létezik."""
    base = ac_path / "content" / "tracks" / track
    candidates = [base / layout / "ai" / "fast_lane.ai"] if layout else []
    candidates.append(base / "ai" / "fast_lane.ai")
    for c in candidates:
        if c.exists() and c.stat().st_size > 16:
            return c
    return None
