# AC Coach

Valós idejű vezetési tanácsadó Assetto Corsához (eredeti AC): ideálív, fékezési pont, fékerő.
Visszajelzés hangjelzéssel és második képernyős webes felülettel.

## Telepítés

```
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## Élő telemetria ellenőrzése

```
.venv\Scripts\python scripts\live_telemetry.py
```

Indítsd el, majd ülj be egy menetbe az AC-ben.

## Körök rögzítése

```
.venv\Scripts\python scripts\record_laps.py
```

A teljes köröket a `data/laps.db`-be menti, és élő eltérést mutat a referencia-körhöz
(a szakaszonként legjobb köreidből összerakott elméleti kör).

## Élő tanácsadó (hangjelzés)

```
.venv\Scripts\python scripts\coach.py
```

Rögzít, és a legjobb érvényes köröd féktávjai alapján visszaszámláló hangot ad
(3 rövid + 1 hosszú sípolás, a hosszú a fékezési pont). Minden féktáv után kiírja
az eltérést: fékpont, fékerő, legkisebb sebesség, nyert/vesztett idő.

## Webes felület (második monitor / tablet)

```
.venv\Scripts\python scripts\web.py
```

Ugyanaz, mint a `coach.py` (rögzítés + hangjelzés), plusz böngészős felület:
delta, következő féktáv, pedálok a referenciához képest, sebesség- és pedálgörbe
az autó körüli ~1 km-en, pályatérkép a féktávokkal, féktáv-értékelések.
Indításkor kiírja a címet a gépre és a helyi hálózatra (tablet).

`--demo`: játék nélkül, a legjobb rögzített kör visszajátszása (külön `data/demo_laps.db`).

## Beállítások

`config.toml`: AC telepítési mappa, adatmappa, mintavételi lépés, pályaelhagyási határ.

## Felépítés

- `src/ac_coach/telemetry/` – telemetria-források, közös `TelemetrySample` formátum
  - `ac_shared_memory.py` – AC osztott memória (`acpmf_physics` / `graphics` / `static`)
- `src/ac_coach/track/ai_line.py` – a pálya AI ideálívének beolvasása (ív, pályaszélesség, kanyarsugár)
- `src/ac_coach/laps/` – körrögzítő, SQLite tároló, referencia-kör
