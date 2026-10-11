import numpy as np
import pytest

from ac_coach.coach import BrakeCue, Coach, ZoneResult, find_brake_zones
from ac_coach.coach.audio import SOUNDS, _render
from ac_coach.laps import Lap
from ac_coach.telemetry import TelemetrySample

L = 2000


def make_lap(brake_at=(500, 1500), brake_len=100, min_speeds=None):
    """2 km-es kör féktávokkal: 200 km/h-ról (alapból) 80 km/h-ra, utána gyorsítás."""
    min_speeds = min_speeds or [80] * len(brake_at)
    speed = np.full(L, 200.0)
    brake = np.zeros(L)
    throttle = np.ones(L)
    for b, vmin in zip(brake_at, min_speeds):
        speed[b:b + brake_len] = np.linspace(200, vmin, brake_len)
        speed[b + brake_len:b + brake_len + 150] = np.linspace(vmin, 200, 150)
        brake[b:b + brake_len] = 0.9
        throttle[b:b + brake_len + 20] = 0.0
    t = np.concatenate([[0], np.cumsum(1 / (speed[:-1] / 3.6))]) * 1000
    ch = {"lap_time_ms": t, "speed_kmh": speed, "brake": brake, "throttle": throttle}
    return Lap("c", "t", int(t[-1] + 18), True, 1.0, {k: v.astype(np.float32) for k, v in ch.items()})


def sample(d, speed, lap=1, brake=0.0, throttle=1.0, t_ms=10_000, packet=0, ts=0.0):
    return TelemetrySample(
        timestamp=ts, packet_id=packet, throttle=throttle, brake=brake, clutch=0.0, steer_angle=0.0,
        speed_kmh=speed, gear=3, rpm=6000, g_lat=0.0, g_lon=0.0, abs_active=0.0, tc_active=0.0,
        tyres_out=0, track_pos=d / L, distance_m=d, world_x=0.0, world_y=0.0, world_z=0.0,
        lap=lap, lap_time_ms=t_ms, last_lap_ms=0, best_lap_ms=0, in_pit=False, is_live=True,
    )


def test_find_brake_zones():
    zones = find_brake_zones(make_lap())
    assert [z.brake_m for z in zones] == [500, 1500]
    z = zones[0]
    assert z.peak_brake == pytest.approx(0.9)
    assert z.min_speed_kmh == pytest.approx(80, abs=1)
    assert 590 <= z.min_speed_m <= 600
    assert z.throttle_m == pytest.approx(620)


def test_cue_fires_once_at_lead_time():
    coach = Coach(make_lap(), countdown_s=0.75, latency_s=0.05)
    speed = 200.0                       # 55.6 m/s -> 0.8 s = 44.4 m
    cues = []
    for d in range(300, 500):
        cues += [e for e in coach.on_sample(sample(d, speed)) if isinstance(e, BrakeCue)]
    assert len(cues) == 1
    assert cues[0].zone.index == 1
    assert cues[0].distance_to_brake_m == pytest.approx(44.4, abs=1.0)


def test_cue_for_zone_after_start_line():
    lap = make_lap(brake_at=(20, 1000))
    coach = Coach(lap, countdown_s=0.75, latency_s=0.05)
    cues = []
    for d in list(range(1900, 2000)) + list(range(0, 20)):
        lap_no = 1 if d >= 1900 else 2
        cues += [e for e in coach.on_sample(sample(d, 200, lap=lap_no)) if isinstance(e, BrakeCue)]
    assert len(cues) == 1 and cues[0].zone.index == 1


def test_zone_result_reports_late_braking():
    ref = make_lap()
    coach = Coach(ref)
    results = []
    # 10 m-rel később fékezünk, ugyanazzal a sebességprofillal eltolva
    for d in range(340, 800):
        r = d - 10
        speed = float(ref.at("speed_kmh", r))
        brake = float(ref.at("brake", r))
        thr = float(ref.at("throttle", r))
        t = ref.at("lap_time_ms", d) - 50
        results += [e for e in coach.on_sample(sample(d, speed, brake=brake, throttle=thr, t_ms=int(t),
                                                      ts=t / 1000))
                    if isinstance(e, ZoneResult)]
    assert len(results) == 1
    res = results[0]
    assert res.brake_diff_m == pytest.approx(10, abs=1)
    assert res.peak_brake == pytest.approx(0.9)
    assert res.time_diff_s == pytest.approx(0, abs=0.02)


def test_min_speed_ignores_previous_corner_exit():
    # két közeli féktáv: a 2. előtti szakaszon még lassú az autó az 1. kanyar után
    ref = make_lap(brake_at=(500, 720), min_speeds=[80, 150])
    coach = Coach(ref)
    results = []
    for d in range(340, 1100):
        s = sample(d, float(ref.at("speed_kmh", d)), brake=float(ref.at("brake", d)),
                   throttle=float(ref.at("throttle", d)), ts=ref.at("lap_time_ms", d) / 1000)
        results += [e for e in coach.on_sample(s) if isinstance(e, ZoneResult)]
    assert [r.zone.index for r in results] == [1, 2]
    assert results[1].min_speed_diff_kmh == pytest.approx(0, abs=2)


def test_zone_time_across_start_line():
    ref = make_lap(brake_at=(30, 1000))
    coach = Coach(ref)
    lap_s = ref.lap_time_ms / 1000
    results = []
    # 2 %-kal lassabban, mint a referencia, a célvonalon át
    for d in list(range(1900, 2000)) + list(range(0, 300)):
        t_ref = ref.at("lap_time_ms", d) / 1000 + (0 if d >= 1900 else lap_s)
        lap_no = 1 if d >= 1900 else 2
        s = sample(d, float(ref.at("speed_kmh", d)), lap=lap_no, brake=float(ref.at("brake", d)),
                   throttle=float(ref.at("throttle", d)), ts=t_ref * 1.02)
        results += [e for e in coach.on_sample(s) if isinstance(e, ZoneResult)]
    assert len(results) == 1
    res = results[0]
    assert res.zone.index == 1
    # a figyelt szakasz kb. 150 + 30 + 100 + 20 m, ~5 s -> 2 % ≈ +0.1 s
    assert 0.05 < res.time_diff_s < 0.2


def test_countdown_sound_renders():
    pcm = _render(SOUNDS["brake_countdown"])
    assert pcm.dtype == np.dtype("<i2") and len(pcm) > 0.75 * 44100
