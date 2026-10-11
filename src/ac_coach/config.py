"""Beállítások betöltése a projekt gyökerében lévő config.toml-ből."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AC_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\assettocorsa")


@dataclass(frozen=True)
class Config:
    ac_path: Path = DEFAULT_AC_PATH
    data_dir: Path = PROJECT_ROOT / "data"
    resample_step_m: float = 1.0
    max_tyres_out: int = 2
    audio_latency_s: float = 0.08
    web_port: int = 8765


def load_config(path: Path | None = None) -> Config:
    path = path or PROJECT_ROOT / "config.toml"
    if not path.exists():
        return Config()
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    data_dir = Path(raw.get("data_dir", "data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir
    return Config(
        ac_path=Path(raw.get("ac_path", DEFAULT_AC_PATH)),
        data_dir=data_dir,
        resample_step_m=float(raw.get("resample_step_m", 1.0)),
        max_tyres_out=int(raw.get("max_tyres_out", 2)),
        audio_latency_s=float(raw.get("audio_latency_s", 0.08)),
        web_port=int(raw.get("web_port", 8765)),
    )
