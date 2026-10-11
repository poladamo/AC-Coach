"""Játékfüggetlen telemetria-formátum.

A tanácsadó többi része csak ezeket a típusokat látja, így később más játék
(ACC, AC EVO) is beköthető egy újabb forrással.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionInfo:
    car: str
    track: str
    track_layout: str
    track_length_m: float
    max_rpm: int

    @property
    def track_id(self) -> str:
        return f"{self.track}/{self.track_layout}" if self.track_layout else self.track


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    timestamp: float          # time.perf_counter() a mintavételkor
    packet_id: int            # a játék fizikai csomagszámlálója

    # vezetői bemenetek (0..1, kormány radiánban)
    throttle: float
    brake: float
    clutch: float
    steer_angle: float

    # autó állapota
    speed_kmh: float
    gear: int                 # -1 = R, 0 = N, 1.. = fokozat
    rpm: int
    g_lat: float              # oldalirányú gyorsulás (g)
    g_lon: float              # hosszirányú gyorsulás (g)
    abs_active: float
    tc_active: float
    tyres_out: int            # pályán kívüli kerekek száma

    # pozíció
    track_pos: float          # 0..1 a pálya mentén
    distance_m: float         # track_pos * pályahossz
    world_x: float
    world_y: float
    world_z: float

    # kör
    lap: int                  # befejezett körök száma
    lap_time_ms: int
    last_lap_ms: int
    best_lap_ms: int
    in_pit: bool
    is_live: bool             # menetben van (nem replay / pause / menü)
