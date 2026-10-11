"""A tanácsadó fő ciklusa: telemetria -> körrögzítés -> tanácsadó -> hang.

A kimenet (konzol, webes felület) egy `CoachListener`-en keresztül kapja az eseményeket.
A ciklus blokkol; webes módban külön szálon fut.
"""

from __future__ import annotations

import ctypes
import threading
import time
from pathlib import Path

from .coach import BrakeCue, Coach, ZoneResult
from .coach.audio import AudioPlayer
from .config import Config
from .laps import Lap, LapRecorder, LapStore, composite_lap
from .telemetry import ACSharedMemory, SessionInfo, TelemetrySample


class CoachListener:
    """Eseménykezelő; a metódusok a tanácsadó szálán hívódnak."""

    def on_waiting(self) -> None: ...
    def on_session(self, session: SessionInfo) -> None: ...
    def on_reference(self, coach: Coach | None, best: Lap | None, theo: Lap | None) -> None: ...
    def on_lap(self, lap: Lap) -> None: ...
    def on_zone_result(self, result: ZoneResult) -> None: ...
    def on_tick(self, s: TelemetrySample, coach: Coach | None, lap_invalid: bool) -> None: ...


class CoachRunner:
    def __init__(
        self,
        cfg: Config,
        listener: CoachListener,
        poll_hz: int = 120,
        audio: bool = True,
        source=None,
        store_path: Path | None = None,
    ):
        """
        source:     telemetria-forrás (alapból az AC osztott memória; pl. ReplaySource bemutatóhoz)
        store_path: körök adatbázisa (alapból data/laps.db)
        """
        self.cfg = cfg
        self.listener = listener
        self.poll_hz = poll_hz
        self.audio = AudioPlayer(cfg.data_dir / "sounds") if audio else None
        self.source = source or ACSharedMemory()
        self.store_path = store_path or cfg.data_dir / "laps.db"
        self.stop_event = threading.Event()
        self.session: SessionInfo | None = None

    def run(self) -> None:
        cfg = self.cfg
        ctypes.windll.winmm.timeBeginPeriod(1)   # pontosabb time.sleep
        store = LapStore(self.store_path)
        ac = self.source
        recorder: LapRecorder | None = None
        coach: Coach | None = None

        def load_reference() -> Coach | None:
            sess = recorder.session
            best = store.best_lap(sess.car, sess.track_id)
            theo = composite_lap(store.laps(sess.car, sess.track_id, limit=20)) if best else None
            c = Coach(best, theo, latency_s=cfg.audio_latency_s) if best else None
            self.listener.on_reference(c, best, theo)
            return c

        try:
            while not self.stop_event.is_set():
                if not ac.connect():
                    self.listener.on_waiting()
                    self.stop_event.wait(1.0)
                    continue

                s = ac.read()
                if recorder is None or not s.is_live:
                    sess = ac.refresh_session()
                    if sess and (recorder is None or recorder.session != sess):
                        self.session = sess
                        self.listener.on_session(sess)
                        recorder = LapRecorder(sess, cfg.resample_step_m, cfg.max_tyres_out)
                        coach = load_reference()
                if recorder is None:
                    self.stop_event.wait(0.5)
                    continue

                lap = recorder.push(s)
                if lap:
                    store.save(lap)
                    self.listener.on_lap(lap)
                    if lap.valid:
                        best = store.best_lap(lap.car, lap.track)
                        if coach is None or best.id == lap.id:
                            coach = load_reference()

                if coach:
                    for ev in coach.on_sample(s):
                        if isinstance(ev, BrakeCue):
                            if self.audio:
                                self.audio.play("brake_countdown")
                        elif isinstance(ev, ZoneResult):
                            self.listener.on_zone_result(ev)

                self.listener.on_tick(s, coach, recorder.current_lap_invalid)
                time.sleep(1.0 / self.poll_hz)
        finally:
            ctypes.windll.winmm.timeEndPeriod(1)
            ac.close()
            store.close()
