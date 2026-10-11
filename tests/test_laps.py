import numpy as np
import pytest

from ac_coach.config import load_config
from ac_coach.laps import Lap, LapRecorder, LapStore, composite_lap, resample_lap
from ac_coach.telemetry import SessionInfo, TelemetrySample
from ac_coach.track import find_ai_line, load_ai_line

L = 1000.0
SESSION = SessionInfo(car="test_car", track="test_track", track_layout="", track_length_m=L, max_rpm=8000)


def sample(packet, pos, lap, t_ms, speed=100.0, **kw):
    base = dict(
        timestamp=0.0, packet_id=packet, throttle=1.0, brake=0.0, clutch=0.0, steer_angle=0.0,
        speed_kmh=speed, gear=3, rpm=6000, g_lat=0.0, g_lon=0.0, abs_active=0.0, tc_active=0.0,
        tyres_out=0, track_pos=pos, distance_m=pos * L, world_x=0.0, world_y=0.0, world_z=0.0,
        lap=lap, lap_time_ms=t_ms, last_lap_ms=0, best_lap_ms=0, in_pit=False, is_live=True,
    )
    base.update(kw)
    return TelemetrySample(**base)


def drive(recorder, laps, lap_ms=40_000, n=400, start_packet=0, **kw):
    """Szimulált vezetés: `laps` darab teljes kör, egyenletes sebességgel."""
    out, packet = [], start_packet
    for lap in range(laps):
        for i in range(n):
            pos = (i / n + 0.995) % 1.0          # a pozíció kicsit a körszámláló előtt fordul át
            packet += 1
            r = recorder.push(sample(packet, pos, lap, int(lap_ms * i / n),
                                     last_lap_ms=lap_ms if lap else 0, **kw))
            if r:
                out.append(r)
    packet += 1
    r = recorder.push(sample(packet, 0.996, laps, 0, last_lap_ms=lap_ms))
    if r:
        out.append(r)
    return out


def test_first_partial_lap_is_dropped_and_full_laps_recorded():
    rec = LapRecorder(SESSION, step_m=1.0)
    laps = drive(rec, 3)
    # Az első kör „menet közben” indult, ezért 2 teljes kör marad.
    assert len(laps) == 2
    lap = laps[0]
    assert lap.valid and lap.lap_time_ms == 40_000
    assert len(lap) == 1000
    # egyenletes haladásnál a köridő a távolsággal arányos
    assert lap.at("lap_time_ms", 500) == pytest.approx(20_000 + 0.005 * 40_000, abs=150)


def test_tyres_out_invalidates_lap():
    rec = LapRecorder(SESSION, step_m=1.0, max_tyres_out=2)
    laps = drive(rec, 2, tyres_out=3)
    assert len(laps) == 1 and not laps[0].valid


def test_resample_rejects_incomplete_coverage():
    samples = [sample(i, i / 100 * 0.5, 0, i * 100) for i in range(100)]
    assert resample_lap(samples, L, 1.0) is None


def _lap(times, lap_time):
    n = len(times)
    ch = {"lap_time_ms": np.array(times, np.float32), "speed_kmh": np.zeros(n, np.float32)}
    return Lap("c", "t", lap_time, True, 1.0, ch)


def test_composite_takes_best_segment_from_each_lap():
    # 100 m-es kör, két 50 m-es szakasz. A: gyors első fele, B: gyors második fele.
    a = _lap(np.r_[np.linspace(0, 5000, 50, endpoint=False), np.linspace(5000, 15000, 50, endpoint=False)], 15000)
    b = _lap(np.r_[np.linspace(0, 8000, 50, endpoint=False), np.linspace(8000, 12000, 50, endpoint=False)], 12000)
    ref = composite_lap([a, b], segment_m=50)
    assert ref.lap_time_ms == 5000 + 4000


def test_store_roundtrip(tmp_path):
    store = LapStore(tmp_path / "laps.db")
    laps = drive(LapRecorder(SESSION), 2, lap_ms=50_000) + drive(LapRecorder(SESSION), 2, lap_ms=45_000)
    for lap in laps:
        store.save(lap)
    best = store.best_lap("test_car", "test_track")
    assert best.lap_time_ms == 45_000
    np.testing.assert_array_equal(best.channels["speed_kmh"], laps[-1].channels["speed_kmh"])
    store.close()


def test_ai_line_from_installed_game():
    cfg = load_config()
    path = find_ai_line(cfg.ac_path, "imola")
    if path is None:
        pytest.skip("Assetto Corsa / imola nincs telepítve")
    ai = load_ai_line(path)
    assert len(ai) > 1000
    assert 4700 < ai.length_m < 5000
    assert np.all(ai.width_left_m >= 0) and np.all(ai.width_right_m >= 0)
