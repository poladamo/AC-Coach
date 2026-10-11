"""Körök tárolása SQLite-ban (autó + pálya szerint)."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from .lap import Lap

_SCHEMA = """
CREATE TABLE IF NOT EXISTS laps (
    id          INTEGER PRIMARY KEY,
    car         TEXT NOT NULL,
    track       TEXT NOT NULL,
    lap_time_ms INTEGER NOT NULL,
    valid       INTEGER NOT NULL,
    step_m      REAL NOT NULL,
    recorded_at TEXT NOT NULL,
    data        BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS laps_car_track ON laps (car, track, valid, lap_time_ms);
"""


class LapStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path)
        self._db.executescript(_SCHEMA)

    def save(self, lap: Lap) -> int:
        cur = self._db.execute(
            "INSERT INTO laps (car, track, lap_time_ms, valid, step_m, recorded_at, data)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (lap.car, lap.track, lap.lap_time_ms, int(lap.valid), lap.step_m,
             lap.recorded_at.isoformat(timespec="seconds"), lap.to_bytes()),
        )
        self._db.commit()
        lap.id = cur.lastrowid
        return lap.id

    def laps(self, car: str, track: str, valid_only: bool = True, limit: int | None = None) -> list[Lap]:
        """A körök köridő szerint növekvő sorrendben."""
        sql = "SELECT * FROM laps WHERE car = ? AND track = ?"
        if valid_only:
            sql += " AND valid = 1"
        sql += " ORDER BY lap_time_ms"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self._row_to_lap(r) for r in self._db.execute(sql, (car, track))]

    def best_lap(self, car: str, track: str) -> Lap | None:
        laps = self.laps(car, track, valid_only=True, limit=1)
        return laps[0] if laps else None

    def close(self) -> None:
        self._db.close()

    @staticmethod
    def _row_to_lap(r: tuple) -> Lap:
        id_, car, track, lap_time_ms, valid, step_m, recorded_at, data = r
        return Lap(
            car=car,
            track=track,
            lap_time_ms=lap_time_ms,
            valid=bool(valid),
            step_m=step_m,
            channels=Lap.channels_from_bytes(data),
            recorded_at=datetime.fromisoformat(recorded_at),
            id=id_,
        )
