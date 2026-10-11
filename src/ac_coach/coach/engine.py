"""Valós idejű tanácsadó: hangjelzés a fékezési pont előtt, értékelés a féktáv után.

Az `on_sample` eseményeket ad vissza; a hang lejátszása és a kiírás a hívó dolga,
így a logika játék és hangkártya nélkül is tesztelhető.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..laps import Lap
from ..telemetry import TelemetrySample
from .zones import BRAKE_ON, THROTTLE_ON, BrakeZone, find_brake_zones

WATCH_BEFORE_M = 150.0   # ennyivel a referencia fékpont előtt kezdjük figyelni a féktávot
MIN_CUE_SPEED_KMH = 40.0


@dataclass(frozen=True)
class BrakeCue:
    """Indítsd a visszaszámláló hangot: a hosszú sípolás a fékezési pontra esik."""
    zone: BrakeZone
    distance_to_brake_m: float


@dataclass(frozen=True)
class ZoneResult:
    zone: BrakeZone
    brake_diff_m: float | None   # + = később fékeztél, mint a referencia; None = nem fékeztél
    peak_brake: float
    min_speed_kmh: float
    time_diff_s: float | None    # + = lassabb volt a féktáv a referenciánál

    @property
    def peak_brake_diff(self) -> float:
        return self.peak_brake - self.zone.peak_brake

    @property
    def min_speed_diff_kmh(self) -> float:
        return self.min_speed_kmh - self.zone.min_speed_kmh


class _ZoneWatch:
    def __init__(self, zone: BrakeZone, start_ts: float, start_d: float):
        self.zone = zone
        self.start_ts = start_ts
        self.start_d = start_d
        self.brake_m: float | None = None
        self.peak = 0.0
        self.min_speed = float("inf")
        self.min_speed_m = 0.0


class Coach:
    def __init__(
        self,
        zone_lap: Lap,
        delta_lap: Lap | None = None,
        countdown_s: float = 0.75,
        latency_s: float = 0.08,
    ):
        """
        zone_lap:    ebből jönnek a fékezési pontok (legjobb tényleges kör)
        delta_lap:   ehhez mérjük az időt (pl. elméleti legjobb kör); alapból zone_lap
        countdown_s: a visszaszámláló hang eleje és a hosszú sípolás közötti idő
        latency_s:   hanglejátszás + reakció késleltetése, ennyivel korábban indítjuk
        """
        self.zones = find_brake_zones(zone_lap)
        self.track_length = zone_lap.step_m * len(zone_lap)
        self.delta_lap = delta_lap or zone_lap
        self.lead_s = countdown_s + latency_s
        self._cued: set[tuple[int, int]] = set()
        self._watch: _ZoneWatch | None = None

    def delta_s(self, s: TelemetrySample) -> float:
        return (s.lap_time_ms - self.delta_lap.at("lap_time_ms", s.distance_m)) / 1000

    def next_zone(self, distance_m: float) -> tuple[BrakeZone, float] | None:
        """A következő féktáv és a távolság a fékezési pontjáig."""
        if not self.zones:
            return None
        best = None
        for z in self.zones:
            ahead = (z.brake_m - distance_m) % self.track_length
            if best is None or ahead < best[1]:
                best = (z, ahead)
        return best

    def on_sample(self, s: TelemetrySample) -> list[BrakeCue | ZoneResult]:
        events: list[BrakeCue | ZoneResult] = []
        if not s.is_live or s.in_pit or not self.zones:
            self._watch = None
            return events
        d = s.distance_m

        # --- hangjelzés ------------------------------------------------------
        nz = self.next_zone(d)
        if nz and s.speed_kmh >= MIN_CUE_SPEED_KMH:
            zone, ahead = nz
            time_to_brake = ahead / (s.speed_kmh / 3.6)
            # a kulcs: melyik körben éri el az autó a fékpontot
            key = (s.lap + (1 if zone.brake_m < d else 0), zone.index)
            if time_to_brake <= self.lead_s and key not in self._cued:
                self._cued.add(key)
                events.append(BrakeCue(zone, ahead))

        # --- féktáv figyelése -----------------------------------------------
        w = self._watch
        if w is None:
            if nz and nz[1] <= WATCH_BEFORE_M:
                self._watch = w = _ZoneWatch(nz[0], s.timestamp, d)
        if w is not None:
            z = w.zone
            rel = self._rel(d, z.brake_m)          # fékponthoz képest, méterben
            if s.brake > BRAKE_ON and w.brake_m is None:
                w.brake_m = rel
            w.peak = max(w.peak, s.brake)
            # legkisebb sebesség csak a fékezéstől (különben az előző kanyar kijárata számítana)
            braking_started = w.brake_m is not None or rel >= 0
            if braking_started and s.speed_kmh < w.min_speed:
                w.min_speed, w.min_speed_m = s.speed_kmh, rel
            exit_rel = z.throttle_m - z.brake_m
            past_exit = rel > exit_rel and s.throttle > THROTTLE_ON
            if past_exit or rel > exit_rel + 200 or rel < -WATCH_BEFORE_M - 50:
                # A szakasz tényleges ideje a referencia ugyanazon szakaszához mérve.
                # (A delta különbsége rossz lenne, ha a féktáv átnyúlik a célvonalon.)
                actual = s.timestamp - w.start_ts
                ref = self._ref_time_s(w.start_d, d)
                time_diff = actual - ref if actual > 0 else None
                events.append(ZoneResult(z, w.brake_m, w.peak, w.min_speed, time_diff))
                self._watch = None
        return events

    def _rel(self, d: float, ref: float) -> float:
        """d - ref, a pálya körbeérését figyelembe véve (-L/2 .. L/2)."""
        L = self.track_length
        return (d - ref + L / 2) % L - L / 2

    def _ref_time_s(self, d0: float, d1: float) -> float:
        """A referencia ideje d0-tól d1-ig, a célvonalon átnyúlva is."""
        ref = self.delta_lap
        t = (ref.at("lap_time_ms", d1) - ref.at("lap_time_ms", d0)) / 1000
        if d1 < d0:
            t += ref.lap_time_ms / 1000
        return t
