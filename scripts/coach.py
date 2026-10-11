"""Élő tanácsadó konzolos kimenettel: körrögzítés + hangjelzés + féktáv-értékelés.

A fékezési pontok a legjobb érvényes körödből jönnek, az élő eltérés az elméleti
legjobb (szakaszonként összerakott) körhöz mér. Amíg nincs érvényes kör az adott
autóval és pályán, csak rögzít. Ctrl+C a kilépéshez.
"""

import sys
import time

from ac_coach.app import CoachListener, CoachRunner
from ac_coach.coach import ZoneResult
from ac_coach.config import load_config

PRINT_HZ = 10


def fmt_ms(ms: float) -> str:
    if ms <= 0:
        return "--:--.---"
    m, rest = divmod(int(ms), 60_000)
    return f"{m}:{rest / 1000:06.3f}"


def describe(r: ZoneResult) -> str:
    z = r.zone
    if r.brake_diff_m is None:
        brake = "nem fékeztél"
    elif abs(r.brake_diff_m) < 3:
        brake = "fékpont pontos"
    else:
        brake = f"{abs(r.brake_diff_m):.0f} m-rel {'később' if r.brake_diff_m > 0 else 'korábban'} fékeztél"
    t = f"{r.time_diff_s:+.2f} s" if r.time_diff_s is not None else "?"
    return (f"{z.index:2d}. féktáv: {t} | {brake} | fékerő {r.peak_brake:.0%} (ref {z.peak_brake:.0%}) | "
            f"min. {r.min_speed_kmh:.0f} km/h ({r.min_speed_diff_kmh:+.0f})")


class ConsoleListener(CoachListener):
    def __init__(self):
        self._last_print = 0.0

    def on_waiting(self):
        print("\rVárakozás az Assetto Corsára...            ", end="", flush=True)

    def on_session(self, sess):
        print(f"\n== {sess.car} @ {sess.track_id} ({sess.track_length_m:.0f} m)")

    def on_reference(self, coach, best, theo):
        if coach is None:
            print("Még nincs érvényes kör ezzel az autóval ezen a pályán – most csak rögzítek.")
            return
        print(f"Referencia: legjobb kör {fmt_ms(best.lap_time_ms)}, elméleti legjobb {fmt_ms(theo.lap_time_ms)}")
        print(f"{len(coach.zones)} féktáv:")
        for z in coach.zones:
            print(f"  {z.index:2d}. fék {z.brake_m:6.0f} m-nél, {z.entry_speed_kmh:3.0f} -> {z.min_speed_kmh:3.0f} km/h,"
                  f" fékerő {z.peak_brake:4.0%}, gáz {z.throttle_m:6.0f} m-nél")

    def on_lap(self, lap):
        print(f"\nKör kész: {fmt_ms(lap.lap_time_ms)}  {'érvényes' if lap.valid else 'ÉRVÉNYTELEN'}")

    def on_zone_result(self, r):
        print("\n" + describe(r))

    def on_tick(self, s, coach, lap_invalid):
        now = time.perf_counter()
        if now - self._last_print < 1.0 / PRINT_HZ:
            return
        self._last_print = now
        info = ""
        if coach and s.is_live and not s.in_pit:
            nz = coach.next_zone(s.distance_m)
            nxt = f"következő fék: {nz[0].index}. ({nz[1]:4.0f} m)" if nz else ""
            info = f"delta {coach.delta_s(s):+6.2f} s | {nxt}"
        flag = " ÉRVÉNYTELEN" if lap_invalid else ""
        print(f"\rkör {s.lap + 1}  {fmt_ms(s.lap_time_ms)} | {s.speed_kmh:5.0f} km/h | {info}{flag}          ",
              end="", flush=True)


def main() -> None:
    runner = CoachRunner(load_config(), ConsoleListener())
    try:
        runner.run()
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    sys.exit(main())
