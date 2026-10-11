"""Webszerver: a tanácsadó adatait WebSocketen küldi a böngészőnek.

A tanácsadó külön szálon fut; az eseményeket a `WebHub` teszi át az asyncio ciklusba.
Üzenetek (JSON, "type" mező szerint):
  status    – kapcsolat állapota (vár a játékra / menetben)
  session   – autó, pálya, pályahossz, AI ív (térképhez)
  reference – referencia-kör nyomvonalai és féktávjai (vagy null)
  tick      – élő adatok, ~20/s
  lap       – befejezett kör
  zone      – féktáv-értékelés
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import threading
import time
from collections import deque
from dataclasses import asdict
from pathlib import Path

import numpy as np
from aiohttp import WSMsgType, web

from ..app import CoachListener, CoachRunner
from ..config import Config, load_config
from ..laps import LapStore
from ..telemetry import SessionInfo
from ..telemetry.replay import ReplaySource
from ..track import find_ai_line, load_ai_line

STATIC_DIR = Path(__file__).parent / "static"
TICK_HZ = 20
TRACE_STEP_M = 5.0
MAP_STEP_M = 10.0


def _r(x, nd=2):
    return None if x is None else round(float(x), nd)


def _arr(a, nd=1):
    return [round(float(v), nd) for v in a]


class WebHub(CoachListener):
    def __init__(self, cfg: Config, loop: asyncio.AbstractEventLoop):
        self.cfg = cfg
        self.loop = loop
        self.clients: set[web.WebSocketResponse] = set()
        # az új klienseknek visszajátszott állapot
        self.status_msg = {"type": "status", "state": "waiting"}
        self.session_msg: dict | None = None
        self.reference_msg: dict | None = None
        self.history: deque[dict] = deque(maxlen=60)
        self._last_tick = 0.0

    # --- küldés -------------------------------------------------------------

    def _emit(self, msg: dict) -> None:
        data = json.dumps(msg, separators=(",", ":"))
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self.loop)

    async def _broadcast(self, data: str) -> None:
        for ws in list(self.clients):
            try:
                await ws.send_str(data)
            except (ConnectionError, RuntimeError):
                self.clients.discard(ws)

    async def add_client(self, ws: web.WebSocketResponse) -> None:
        self.clients.add(ws)
        for msg in (self.status_msg, self.session_msg, self.reference_msg, *self.history):
            if msg:
                await ws.send_str(json.dumps(msg, separators=(",", ":")))

    # --- CoachListener --------------------------------------------------------

    def on_waiting(self):
        if self.status_msg["state"] != "waiting":
            self.status_msg = {"type": "status", "state": "waiting"}
            self._emit(self.status_msg)

    def on_session(self, sess):
        self.status_msg = {"type": "status", "state": "connected"}
        self._emit(self.status_msg)
        msg = {
            "type": "session",
            "car": sess.car,
            "track": sess.track_id,
            "length": round(sess.track_length_m, 1),
            "map": None,
        }
        path = find_ai_line(self.cfg.ac_path, sess.track, sess.track_layout)
        if path:
            ai = load_ai_line(path)
            idx = np.searchsorted(ai.distance_m, np.arange(0, ai.length_m, MAP_STEP_M))
            idx = np.clip(idx, 0, len(ai) - 1)
            msg["map"] = {"x": _arr(ai.position[idx, 0]), "z": _arr(ai.position[idx, 2])}
        self.session_msg = msg
        self.history.clear()
        self._emit(msg)

    def on_reference(self, coach, best, theo):
        if coach is None:
            msg = {"type": "reference", "ref": None}
        else:
            k = max(1, int(round(TRACE_STEP_M / best.step_m)))
            ch = best.channels
            msg = {
                "type": "reference",
                "ref": {
                    "best_ms": best.lap_time_ms,
                    "theo_ms": theo.lap_time_ms if theo else None,
                    "step": best.step_m * k,
                    "speed": _arr(ch["speed_kmh"][::k]),
                    "brake": _arr(ch["brake"][::k], 2),
                    "throttle": _arr(ch["throttle"][::k], 2),
                    "x": _arr(ch["world_x"][::k]),
                    "z": _arr(ch["world_z"][::k]),
                    "zones": [asdict(z) for z in coach.zones],
                },
            }
        self.reference_msg = msg
        self._emit(msg)

    def on_lap(self, lap):
        msg = {"type": "lap", "ms": lap.lap_time_ms, "valid": lap.valid}
        self.history.append(msg)
        self._emit(msg)

    def on_zone_result(self, r):
        msg = {
            "type": "zone",
            "index": r.zone.index,
            "time_diff": _r(r.time_diff_s),
            "brake_diff": _r(r.brake_diff_m, 1),
            "peak": _r(r.peak_brake),
            "ref_peak": _r(r.zone.peak_brake),
            "min_speed": _r(r.min_speed_kmh, 1),
            "min_speed_diff": _r(r.min_speed_diff_kmh, 1),
        }
        self.history.append(msg)
        self._emit(msg)

    def on_tick(self, s, coach, lap_invalid):
        now = time.perf_counter()
        if now - self._last_tick < 1.0 / TICK_HZ:
            return
        self._last_tick = now
        msg = {
            "type": "tick",
            "live": s.is_live,
            "pit": s.in_pit,
            "lap": s.lap + 1,
            "lap_ms": s.lap_time_ms,
            "last_ms": s.last_lap_ms,
            "best_ms": s.best_lap_ms,
            "d": _r(s.distance_m, 1),
            "speed": _r(s.speed_kmh, 1),
            "thr": _r(s.throttle),
            "brk": _r(s.brake),
            "gear": s.gear,
            "rpm": s.rpm,
            "x": _r(s.world_x, 1),
            "z": _r(s.world_z, 1),
            "invalid": lap_invalid,
            "delta": None,
            "next": None,
        }
        if coach and s.is_live and not s.in_pit and s.lap_time_ms > 0:
            msg["delta"] = _r(coach.delta_s(s))
            nz = coach.next_zone(s.distance_m)
            if nz:
                msg["next"] = {"index": nz[0].index, "dist": _r(nz[1], 0)}
        self._emit(msg)


# --- HTTP / WebSocket ---------------------------------------------------------


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(STATIC_DIR / "index.html")


async def websocket(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=10)
    await ws.prepare(request)
    hub: WebHub = request.app["hub"]
    await hub.add_client(ws)
    try:
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                break
    finally:
        hub.clients.discard(ws)
    return ws


def _lan_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))   # nem küld csomagot, csak kiválasztja a kimenő interfészt
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def _demo_setup(cfg: Config) -> dict:
    """Bemutató mód: a legjobb rögzített kör visszajátszása, külön adatbázissal."""
    real = LapStore(cfg.data_dir / "laps.db")
    rows = real._db.execute(
        "SELECT car, track FROM laps WHERE valid = 1 ORDER BY lap_time_ms LIMIT 1").fetchall()
    if not rows:
        raise SystemExit("Bemutató módhoz legalább egy érvényes rögzített kör kell.")
    car, track = rows[0]
    lap = real.best_lap(car, track)
    real.close()

    track_name, _, layout = track.partition("/")
    session = SessionInfo(car=car, track=track_name, track_layout=layout,
                          track_length_m=lap.step_m * len(lap), max_rpm=0)
    demo_db = cfg.data_dir / "demo_laps.db"
    demo_db.unlink(missing_ok=True)
    demo = LapStore(demo_db)
    lap.id = None
    demo.save(lap)
    demo.close()
    print(f"BEMUTATÓ MÓD: {car} @ {track}, {lap.lap_time_ms / 1000:.3f} s-os kör visszajátszása")
    return {"source": ReplaySource(lap, session), "store_path": demo_db, "audio": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="AC Coach webes felület")
    parser.add_argument("--demo", action="store_true",
                        help="játék nélkül: a legjobb rögzített kör visszajátszása")
    args = parser.parse_args()

    cfg = load_config()
    runner_kw = _demo_setup(cfg) if args.demo else {}
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket)
    app.router.add_static("/static", STATIC_DIR)

    async def start_coach(app: web.Application) -> None:
        hub = WebHub(cfg, asyncio.get_running_loop())
        runner = CoachRunner(cfg, hub, **runner_kw)
        app["hub"], app["runner"] = hub, runner
        thread = threading.Thread(target=runner.run, name="coach", daemon=True)
        thread.start()
        app["thread"] = thread

    async def stop_coach(app: web.Application) -> None:
        app["runner"].stop_event.set()
        await asyncio.to_thread(app["thread"].join, 2.0)
        for ws in list(app["hub"].clients):
            await ws.close()

    app.on_startup.append(start_coach)
    app.on_shutdown.append(stop_coach)

    print("AC Coach webes felület:")
    print(f"  ezen a gépen:    http://localhost:{cfg.web_port}")
    print(f"  tableten / LAN:  http://{_lan_ip()}:{cfg.web_port}")
    print("Ctrl+C a kilépéshez.")
    web.run_app(app, host="0.0.0.0", port=cfg.web_port, print=None)


if __name__ == "__main__":
    main()
