"""Hangjelzések: a hangfájlokat egyszer legeneráljuk, aztán aszinkron játsszuk le.

A winsound memóriából nem tud aszinkron játszani, ezért WAV fájlokba írjuk őket.
"""

from __future__ import annotations

import wave
import winsound
from pathlib import Path

import numpy as np

RATE = 44100

# hang neve -> [(kezdés s, frekvencia Hz, hossz s, hangerő 0..1)]
SOUNDS: dict[str, list[tuple[float, float, float, float]]] = {
    # három rövid sípolás negyed másodpercenként, a hosszú a fékezési pont
    "brake_countdown": [
        (0.00, 880, 0.07, 0.5),
        (0.25, 880, 0.07, 0.5),
        (0.50, 880, 0.07, 0.5),
        (0.75, 1320, 0.30, 0.7),
    ],
}


def _render(parts: list[tuple[float, float, float, float]]) -> np.ndarray:
    total = max(start + dur for start, _, dur, _ in parts) + 0.05
    out = np.zeros(int(total * RATE), dtype=np.float64)
    for start, freq, dur, vol in parts:
        t = np.arange(int(dur * RATE)) / RATE
        tone = np.sin(2 * np.pi * freq * t) * vol
        fade = min(len(t) // 2, int(0.005 * RATE))   # kattanásmentes be/kiúsztatás
        env = np.ones_like(t)
        env[:fade] = np.linspace(0, 1, fade)
        env[-fade:] = np.linspace(1, 0, fade)
        i0 = int(start * RATE)
        out[i0:i0 + len(t)] += tone * env
    return (np.clip(out, -1, 1) * 32767).astype("<i2")


class AudioPlayer:
    def __init__(self, cache_dir: Path):
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._files: dict[str, Path] = {}
        for name, parts in SOUNDS.items():
            path = cache_dir / f"{name}.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(RATE)
                w.writeframes(_render(parts).tobytes())
            self._files[name] = path

    def play(self, name: str) -> None:
        winsound.PlaySound(
            str(self._files[name]),
            winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT,
        )
