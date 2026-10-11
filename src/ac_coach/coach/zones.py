"""Féktávok kinyerése egy referencia-körből."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..laps import Lap

BRAKE_ON = 0.10          # e fölött számít fékezésnek
MERGE_GAP_M = 20.0       # ennél közelebbi fékezések egy féktávnak számítanak
MIN_ZONE_M = 10.0        # ennél rövidebb fékezést nem tekintünk féktávnak
THROTTLE_ON = 0.5        # gázadás pontja: ezt átlépő gáz a legkisebb sebesség után
EXIT_SEARCH_M = 300.0    # a féktáv vége után ennyi méterig keressük a legkisebb sebességet


@dataclass(frozen=True)
class BrakeZone:
    index: int               # 1-től számozva a pálya mentén
    brake_m: float           # fékezés kezdete
    brake_end_m: float       # fékezés vége
    entry_speed_kmh: float
    peak_brake: float
    min_speed_kmh: float
    min_speed_m: float
    throttle_m: float        # újra gáz


def find_brake_zones(lap: Lap) -> list[BrakeZone]:
    step = lap.step_m
    brake = lap.channels["brake"]
    speed = lap.channels["speed_kmh"]
    throttle = lap.channels["throttle"]
    n = len(lap)

    # összefüggő fékezési szakaszok
    on = brake > BRAKE_ON
    edges = np.diff(on.astype(np.int8), prepend=0, append=0)
    starts = list(np.flatnonzero(edges == 1))
    ends = list(np.flatnonzero(edges == -1))

    runs: list[list[int]] = []
    for s, e in zip(starts, ends):
        if runs and (s - runs[-1][1]) * step < MERGE_GAP_M:
            runs[-1][1] = e
        else:
            runs.append([s, e])
    runs = [r for r in runs if (r[1] - r[0]) * step >= MIN_ZONE_M]

    zones = []
    for i, (s, e) in enumerate(runs):
        next_start = runs[i + 1][0] if i + 1 < len(runs) else n
        search_end = min(n, e + int(EXIT_SEARCH_M / step), next_start)
        apex = s + int(np.argmin(speed[s:search_end]))
        after = np.flatnonzero(throttle[apex:search_end] > THROTTLE_ON)
        thr = apex + int(after[0]) if len(after) else search_end - 1
        zones.append(BrakeZone(
            index=len(zones) + 1,
            brake_m=s * step,
            brake_end_m=e * step,
            entry_speed_kmh=float(speed[s]),
            peak_brake=float(brake[s:e].max()),
            min_speed_kmh=float(speed[apex]),
            min_speed_m=apex * step,
            throttle_m=thr * step,
        ))
    return zones
