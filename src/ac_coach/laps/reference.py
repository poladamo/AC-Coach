"""Referencia-kör: a legjobb kör, vagy szakaszonként a legjobbakból összerakott kör."""

from __future__ import annotations

import numpy as np

from .lap import Lap


def composite_lap(laps: list[Lap], segment_m: float = 50.0) -> Lap | None:
    """Elméleti legjobb kör: minden `segment_m` hosszú szakaszra a leggyorsabb kör adatai.

    A köröknek ugyanarról az autóról, pályáról és azonos rácsról kell szólniuk.
    A szakaszhatárokon a csatornák (pl. sebesség) kicsit ugorhatnak.
    """
    laps = [l for l in laps if l.valid]
    if not laps:
        return None
    if len(laps) == 1:
        return laps[0]

    step = laps[0].step_m
    n = min(len(l) for l in laps)
    seg = max(1, int(round(segment_m / step)))
    bounds = list(range(0, n, seg)) + [n]

    out = {k: np.empty(n, dtype=np.float32) for k in laps[0].channels}
    t_start = 0.0
    for i0, i1 in zip(bounds[:-1], bounds[1:]):
        best, best_dt = None, np.inf
        for lap in laps:
            t = lap.time_ms
            t_end = lap.lap_time_ms if i1 == n else t[i1]
            dt = t_end - t[i0]
            if 0 < dt < best_dt:
                best, best_dt = lap, dt
        for k in out:
            out[k][i0:i1] = best.channels[k][i0:i1]
        out["lap_time_ms"][i0:i1] = t_start + (best.time_ms[i0:i1] - best.time_ms[i0])
        t_start += best_dt

    return Lap(
        car=laps[0].car,
        track=laps[0].track,
        lap_time_ms=int(round(t_start)),
        valid=True,
        step_m=step,
        channels=out,
    )
