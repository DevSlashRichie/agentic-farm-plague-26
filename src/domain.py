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


class MapData(TypedDict):
    rows: int
    columns: int
    matrix: list[list[str]]
    walls: list[tuple[Coord, Coord]]
    doors: list[tuple[Coord, Coord]]


Coord = tuple[int, int]
