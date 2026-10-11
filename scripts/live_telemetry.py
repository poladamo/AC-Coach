"""Élő telemetria kiírása a konzolra – a telemetria-olvasó ellenőrzésére.

Indítsd el, majd ülj be az AC-ben egy menetbe. Ctrl+C a kilépéshez.
"""

import sys
import time

from ac_coach.telemetry import ACSharedMemory

POLL_HZ = 60


def fmt_ms(ms: int) -> str:
    if ms <= 0 or ms >= 2**31 - 1:
        return "--:--.---"
    m, rest = divmod(ms, 60_000)
    return f"{m}:{rest / 1000:06.3f}"


def main() -> None:
    ac = ACSharedMemory()
    last_packet = None
    stale_since = time.perf_counter()
    rate_count, rate_t0, rate = 0, time.perf_counter(), 0.0

    try:
        while True:
            if not ac.connect():
                print("\rVárakozás az Assetto Corsára...            ", end="", flush=True)
                time.sleep(1.0)
                continue

            s = ac.read()
            now = time.perf_counter()

            if s.packet_id != last_packet:
                last_packet = s.packet_id
                stale_since = now
                rate_count += 1
            if now - rate_t0 >= 1.0:
                rate, rate_count, rate_t0 = rate_count / (now - rate_t0), 0, now

            if ac.session is None or (now - stale_since > 0.5 and not s.is_live):
                ac.refresh_session()

            sess = ac.session
            head = f"{sess.car} @ {sess.track_id} ({sess.track_length_m:.0f} m)" if sess else "nincs menet"
            gear = {-1: "R", 0: "N"}.get(s.gear, str(s.gear))
            line = (
                f"{head} | {'LIVE' if s.is_live else 'nem él'} | {rate:5.1f} Hz | "
                f"{s.speed_kmh:6.1f} km/h  {gear:>2}  {s.rpm:5d} rpm | "
                f"gáz {s.throttle:4.2f}  fék {s.brake:4.2f}  kormány {s.steer_angle:+5.2f} | "
                f"Glat {s.g_lat:+5.2f}  Glon {s.g_lon:+5.2f} | "
                f"poz {s.track_pos:6.4f} = {s.distance_m:7.1f} m | "
                f"kör {s.lap}  {fmt_ms(s.lap_time_ms)}  (best {fmt_ms(s.best_lap_ms)})"
                f"{'  BOX' if s.in_pit else ''}"
            )
            print("\r" + line, end="", flush=True)
            time.sleep(1.0 / POLL_HZ)
    except KeyboardInterrupt:
        print()
    finally:
        ac.close()


if __name__ == "__main__":
    sys.exit(main())
