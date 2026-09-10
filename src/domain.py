from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


class CellName(StrEnum):
    VICTIM = "victim"
    FAKE = "fake"
    FIRE = "fire"
    SMOKE = "smoke"
    NONE = "none"
    EXIT = "exit"
    UNKNOWN = "unknown"


class Action(StrEnum):
    MOVE = "move"
    EXTINGUISH = "extinguish"
    OPEN_DOOR = "open_door"
    CHOP_WALL = "chop_wall"


# Wall-breaking penalty. Chopping costs more than a full burst of AP and
# deals heavy structural damage, so agents only do it when no door/detour
# path exists.
CHOP_AP_COST = 6
CHOP_DAMAGE = 2

# POI deck composition: 12 real victims, 6 empty (false alarm) markers.
# The deck is shuffled at game start (and reshuffled when exhausted);
# every new POI pops one marker off it.
POI_DECK_REALS = 12
POI_DECK_EMPTIES = 6


class MapData(TypedDict):
    rows: int
    columns: int
    matrix: list[list[str]]
    walls: list[tuple[Coord, Coord]]
    doors: list[tuple[Coord, Coord]]


Coord = tuple[int, int]
