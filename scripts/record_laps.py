"""Körök rögzítése élőben, élő eltéréssel a referencia-körhöz.

Indítsd el, majd ülj be egy menetbe. Minden teljes kör a data/laps.db-be kerül.
A referencia a szakaszonként legjobb köreidből összerakott elméleti kör.
Ctrl+C a kilépéshez.
"""

import sys
import time

from ac_coach.config import load_config
from ac_coach.laps import LapRecorder, LapStore, composite_lap
from ac_coach.telemetry import ACSharedMemory
from ac_coach.track import find_ai_line, load_ai_line

POLL_HZ = 60
PRINT_HZ = 10


def fmt_ms(ms: float) -> str:
    if ms <= 0:
        return "--:--.---"
    m, rest = divmod(int(ms), 60_000)
    return f"{m}:{rest / 1000:06.3f}"


def main() -> None:
    cfg = load_config()
    store = LapStore(cfg.data_dir / "laps.db")
    ac = ACSharedMemory()
    recorder = None
    reference = None
    last_print = 0.0

    def load_reference():
        laps = store.laps(recorder.session.car, recorder.session.track_id, limit=20)
        return composite_lap(laps)

    try:
        while True:
            if not ac.connect():
                print("\rVárakozás az Assetto Corsára...            ", end="", flush=True)
                time.sleep(1.0)
                continue

            s = ac.read()
            if recorder is None or not s.is_live:
                sess = ac.refresh_session()
                if sess and (recorder is None or recorder.session != sess):
                    recorder = LapRecorder(sess, cfg.resample_step_m, cfg.max_tyres_out)
                    reference = load_reference()
                    ai = find_ai_line(cfg.ac_path, sess.track, sess.track_layout)
                    ai_info = f"AI ív: {len(load_ai_line(ai))} pont" if ai else "AI ív: nincs"
                    ref_info = f"referencia: {fmt_ms(reference.lap_time_ms)}" if reference else "referencia: még nincs"
                    print(f"\n== {sess.car} @ {sess.track_id} ({sess.track_length_m:.0f} m) | {ai_info} | {ref_info}")
            if recorder is None:
                time.sleep(0.5)
                continue

            lap = recorder.push(s)
            if lap:
                store.save(lap)
                ref_txt = ""
                if reference:
                    ref_txt = f"  ({(lap.lap_time_ms - reference.lap_time_ms) / 1000:+.3f} a referenciához)"
                print(f"\nKör kész: {fmt_ms(lap.lap_time_ms)}  {'érvényes' if lap.valid else 'ÉRVÉNYTELEN'}{ref_txt}")
                if lap.valid:
                    old = reference.lap_time_ms if reference else None
                    reference = load_reference()
                    if reference and reference.lap_time_ms != old:
                        print(f"Új referencia (elméleti legjobb): {fmt_ms(reference.lap_time_ms)}")

            now = time.perf_counter()
            if now - last_print >= 1.0 / PRINT_HZ:
                last_print = now
                delta = ""
                if reference and s.is_live and not s.in_pit:
                    d = (s.lap_time_ms - reference.at("lap_time_ms", s.distance_m)) / 1000
                    delta = f"delta {d:+6.2f} s | ref {reference.at('speed_kmh', s.distance_m):5.0f} km/h | "
                flag = " ÉRVÉNYTELEN" if recorder.current_lap_invalid else ""
                print(
                    f"\rkör {s.lap + 1}  {fmt_ms(s.lap_time_ms)} | {s.distance_m:6.0f} m | "
                    f"{s.speed_kmh:5.0f} km/h | {delta}{flag}          ",
                    end="", flush=True,
                )
            time.sleep(1.0 / POLL_HZ)
    except KeyboardInterrupt:
        print()
    finally:
        ac.close()
        store.close()


if __name__ == "__main__":
    sys.exit(main())
