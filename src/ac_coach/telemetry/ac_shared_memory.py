"""Assetto Corsa (eredeti) osztott memória olvasó.

Az AC három nevesített memórialapot tesz közzé, amíg egy menet fut:
  Local\\acpmf_physics  – autófizika, nagy frissítési gyakoriság
  Local\\acpmf_graphics – pálya-pozíció, köridők, állapot
  Local\\acpmf_static   – autó, pálya, menetenként állandó adatok

A struktúrák a hivatalos SharedFileOut.h elejét követik (4 bájtos illesztés).
Csak az elejüket írjuk le: a mező-eltolások így is egyeznek, a végükön lévő
mezőkre pedig nincs szükségünk.
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from .sample import SessionInfo, TelemetrySample

# --- struktúrák ---------------------------------------------------------------

F4 = ctypes.c_float * 4
F3 = ctypes.c_float * 3


class Physics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("gas", ctypes.c_float),
        ("brake", ctypes.c_float),
        ("fuel", ctypes.c_float),
        ("gear", ctypes.c_int),
        ("rpms", ctypes.c_int),
        ("steerAngle", ctypes.c_float),
        ("speedKmh", ctypes.c_float),
        ("velocity", F3),
        ("accG", F3),
        ("wheelSlip", F4),
        ("wheelLoad", F4),
        ("wheelsPressure", F4),
        ("wheelAngularSpeed", F4),
        ("tyreWear", F4),
        ("tyreDirtyLevel", F4),
        ("tyreCoreTemperature", F4),
        ("camberRAD", F4),
        ("suspensionTravel", F4),
        ("drs", ctypes.c_float),
        ("tc", ctypes.c_float),
        ("heading", ctypes.c_float),
        ("pitch", ctypes.c_float),
        ("roll", ctypes.c_float),
        ("cgHeight", ctypes.c_float),
        ("carDamage", ctypes.c_float * 5),
        ("numberOfTyresOut", ctypes.c_int),
        ("pitLimiterOn", ctypes.c_int),
        ("abs", ctypes.c_float),
        ("kersCharge", ctypes.c_float),
        ("kersInput", ctypes.c_float),
        ("autoShifterOn", ctypes.c_int),
        ("rideHeight", ctypes.c_float * 2),
        ("turboBoost", ctypes.c_float),
        ("ballast", ctypes.c_float),
        ("airDensity", ctypes.c_float),
        ("airTemp", ctypes.c_float),
        ("roadTemp", ctypes.c_float),
        ("localAngularVel", F3),
        ("finalFF", ctypes.c_float),
        ("performanceMeter", ctypes.c_float),
        ("engineBrake", ctypes.c_int),
        ("ersRecoveryLevel", ctypes.c_int),
        ("ersPowerLevel", ctypes.c_int),
        ("ersHeatCharging", ctypes.c_int),
        ("ersIsCharging", ctypes.c_int),
        ("kersCurrentKJ", ctypes.c_float),
        ("drsAvailable", ctypes.c_int),
        ("drsEnabled", ctypes.c_int),
        ("brakeTemp", F4),
        ("clutch", ctypes.c_float),
        ("tyreTempI", F4),
        ("tyreTempM", F4),
        ("tyreTempO", F4),
        ("isAIControlled", ctypes.c_int),
        ("tyreContactPoint", F3 * 4),
        ("tyreContactNormal", F3 * 4),
        ("tyreContactHeading", F3 * 4),
        ("brakeBias", ctypes.c_float),
        ("localVelocity", F3),
    ]


class Graphics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("packetId", ctypes.c_int),
        ("status", ctypes.c_int),       # 0 OFF, 1 REPLAY, 2 LIVE, 3 PAUSE
        ("session", ctypes.c_int),
        ("currentTime", ctypes.c_wchar * 15),
        ("lastTime", ctypes.c_wchar * 15),
        ("bestTime", ctypes.c_wchar * 15),
        ("split", ctypes.c_wchar * 15),
        ("completedLaps", ctypes.c_int),
        ("position", ctypes.c_int),
        ("iCurrentTime", ctypes.c_int),
        ("iLastTime", ctypes.c_int),
        ("iBestTime", ctypes.c_int),
        ("sessionTimeLeft", ctypes.c_float),
        ("distanceTraveled", ctypes.c_float),
        ("isInPit", ctypes.c_int),
        ("currentSectorIndex", ctypes.c_int),
        ("lastSectorTime", ctypes.c_int),
        ("numberOfLaps", ctypes.c_int),
        ("tyreCompound", ctypes.c_wchar * 33),
        ("replayTimeMultiplier", ctypes.c_float),
        ("normalizedCarPosition", ctypes.c_float),
        ("carCoordinates", F3),
        ("penaltyTime", ctypes.c_float),
        ("flag", ctypes.c_int),
        ("idealLineOn", ctypes.c_int),
        ("isInPitLane", ctypes.c_int),
        ("surfaceGrip", ctypes.c_float),
    ]


class Static(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ("smVersion", ctypes.c_wchar * 15),
        ("acVersion", ctypes.c_wchar * 15),
        ("numberOfSessions", ctypes.c_int),
        ("numCars", ctypes.c_int),
        ("carModel", ctypes.c_wchar * 33),
        ("track", ctypes.c_wchar * 33),
        ("playerName", ctypes.c_wchar * 33),
        ("playerSurname", ctypes.c_wchar * 33),
        ("playerNick", ctypes.c_wchar * 33),
        ("sectorCount", ctypes.c_int),
        ("maxTorque", ctypes.c_float),
        ("maxPower", ctypes.c_float),
        ("maxRpm", ctypes.c_int),
        ("maxFuel", ctypes.c_float),
        ("suspensionMaxTravel", F4),
        ("tyreRadius", F4),
        ("maxTurboBoost", ctypes.c_float),
        ("deprecated_1", ctypes.c_float),
        ("deprecated_2", ctypes.c_float),
        ("penaltiesEnabled", ctypes.c_int),
        ("aidFuelRate", ctypes.c_float),
        ("aidTireRate", ctypes.c_float),
        ("aidMechanicalDamage", ctypes.c_float),
        ("aidAllowTyreBlankets", ctypes.c_int),
        ("aidStability", ctypes.c_float),
        ("aidAutoClutch", ctypes.c_int),
        ("aidAutoBlip", ctypes.c_int),
        ("hasDRS", ctypes.c_int),
        ("hasERS", ctypes.c_int),
        ("hasKERS", ctypes.c_int),
        ("kersMaxJ", ctypes.c_float),
        ("engineBrakeSettingsCount", ctypes.c_int),
        ("ersPowerControllerCount", ctypes.c_int),
        ("trackSPlineLength", ctypes.c_float),
        ("trackConfiguration", ctypes.c_wchar * 33),
    ]


AC_LIVE = 2

# --- Win32 hozzáférés ---------------------------------------------------------

_FILE_MAP_READ = 0x0004
_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
_k32.OpenFileMappingW.restype = wintypes.HANDLE
_k32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                               wintypes.DWORD, ctypes.c_size_t]
_k32.MapViewOfFile.restype = wintypes.LPVOID
_k32.UnmapViewOfFile.argtypes = [wintypes.LPCVOID]
_k32.UnmapViewOfFile.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_k32.CloseHandle.restype = wintypes.BOOL


class _Page:
    """Egy meglévő nevesített memórialap csak olvasható nézete.

    Szándékosan Open-t használunk (nem Create-et), hogy ne mi hozzuk létre
    a lapot, ha a játék még nem fut.
    """

    def __init__(self, name: str, struct_type: type[ctypes.Structure]):
        self.struct_type = struct_type
        self.size = ctypes.sizeof(struct_type)
        self._handle = _k32.OpenFileMappingW(_FILE_MAP_READ, False, name)
        if not self._handle:
            raise FileNotFoundError(name)
        self._view = _k32.MapViewOfFile(self._handle, _FILE_MAP_READ, 0, 0, self.size)
        if not self._view:
            err = ctypes.get_last_error()
            _k32.CloseHandle(self._handle)
            raise OSError(err, f"MapViewOfFile failed for {name}")

    def read(self):
        out = self.struct_type()
        ctypes.memmove(ctypes.addressof(out), self._view, self.size)
        return out

    def close(self) -> None:
        if self._view:
            _k32.UnmapViewOfFile(self._view)
            self._view = None
        if self._handle:
            _k32.CloseHandle(self._handle)
            self._handle = None


# --- olvasó -------------------------------------------------------------------


class ACSharedMemory:
    """Az AC telemetriát `TelemetrySample` formában adja.

    Használat:
        with ACSharedMemory() as ac:
            if ac.connect():
                sample = ac.read()
    """

    def __init__(self) -> None:
        self._physics: _Page | None = None
        self._graphics: _Page | None = None
        self._static: _Page | None = None
        self.session: SessionInfo | None = None

    @property
    def connected(self) -> bool:
        return self._physics is not None

    def connect(self) -> bool:
        """Megnyitja a memórialapokat. False, ha az AC nem fut."""
        if self.connected:
            return True
        try:
            self._physics = _Page("Local\\acpmf_physics", Physics)
            self._graphics = _Page("Local\\acpmf_graphics", Graphics)
            self._static = _Page("Local\\acpmf_static", Static)
        except FileNotFoundError:
            self.close()
            return False
        self.refresh_session()
        return True

    def refresh_session(self) -> SessionInfo | None:
        """Újraolvassa a statikus lapot (autó, pálya). Menetváltáskor hívandó."""
        if not self._static:
            return None
        s = self._static.read()
        if not s.track:
            self.session = None
        else:
            self.session = SessionInfo(
                car=s.carModel,
                track=s.track,
                track_layout=s.trackConfiguration,
                track_length_m=s.trackSPlineLength,
                max_rpm=s.maxRpm,
            )
        return self.session

    def read(self) -> TelemetrySample | None:
        if not self.connected:
            return None
        # A fizikai lapot kétszer olvassuk, ha olvasás közben frissült.
        p = self._physics.read()
        g = self._graphics.read()
        p2 = self._physics.read()
        if p2.packetId != p.packetId:
            p = p2
        ts = time.perf_counter()

        track_len = self.session.track_length_m if self.session else 0.0
        pos = g.normalizedCarPosition
        return TelemetrySample(
            timestamp=ts,
            packet_id=p.packetId,
            throttle=p.gas,
            brake=p.brake,
            clutch=p.clutch,
            steer_angle=p.steerAngle,
            speed_kmh=p.speedKmh,
            gear=p.gear - 1,
            rpm=p.rpms,
            g_lat=p.accG[0],
            g_lon=p.accG[2],
            abs_active=p.abs,
            tc_active=p.tc,
            tyres_out=p.numberOfTyresOut,
            track_pos=pos,
            distance_m=pos * track_len,
            world_x=g.carCoordinates[0],
            world_y=g.carCoordinates[1],
            world_z=g.carCoordinates[2],
            lap=g.completedLaps,
            lap_time_ms=g.iCurrentTime,
            last_lap_ms=g.iLastTime,
            best_lap_ms=g.iBestTime,
            in_pit=bool(g.isInPit or g.isInPitLane),
            is_live=g.status == AC_LIVE,
        )

    def close(self) -> None:
        for page in (self._physics, self._graphics, self._static):
            if page:
                page.close()
        self._physics = self._graphics = self._static = None
        self.session = None

    def __enter__(self) -> ACSharedMemory:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
