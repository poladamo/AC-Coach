"""Élő tanácsadó webes felülettel (második monitor / tablet) és hangjelzéssel.

    python scripts\\web.py          – élő, az Assetto Corsából
    python scripts\\web.py --demo   – játék nélkül, a legjobb rögzített kör visszajátszása
"""

from ac_coach.web.server import main

if __name__ == "__main__":
    main()
