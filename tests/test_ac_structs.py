"""A struktúrák mező-eltolásainak ellenőrzése a SharedFileOut.h szerint."""

import ctypes

from ac_coach.telemetry.ac_shared_memory import Graphics, Physics, Static


def test_physics_offsets():
    assert Physics.packetId.offset == 0
    assert Physics.gas.offset == 4
    assert Physics.brake.offset == 8
    assert Physics.gear.offset == 16
    assert Physics.speedKmh.offset == 28
    assert Physics.accG.offset == 44


def test_graphics_offsets():
    # 3 int + 4 * 15 wchar (2 bájt) = 12 + 120
    assert Graphics.completedLaps.offset == 132
    assert ctypes.sizeof(ctypes.c_wchar) == 2


def test_static_offsets():
    # 2 * 15 wchar = 60, + 2 int = 68
    assert Static.carModel.offset == 68
    assert Static.track.offset == 68 + 66


def test_connect_without_game_returns_false():
    from ac_coach.telemetry import ACSharedMemory

    ac = ACSharedMemory()
    # Ha a játék épp fut, ez True – mindkét eset érvényes, csak ne dobjon kivételt.
    assert ac.connect() in (True, False)
    ac.close()
