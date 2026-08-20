from __future__ import annotations

from enum import StrEnum


class CellName(StrEnum):
    VICTIM = "victim"
    FAKE = "fake"
    FIRE = "fire"
    SMOKE = "smoke"
    NONE = "none"
    DOOR = "door"
    WALL = "wall"
    EXIT = "exit"
    UNKNOWN = "unknown"


class Action(StrEnum):
    MOVE = "move"
    EXTINGUISH = "extinguish"
    OPEN_DOOR = "open_door"
    CHOP_WALL = "chop_wall"


Coord = tuple[int, int]
