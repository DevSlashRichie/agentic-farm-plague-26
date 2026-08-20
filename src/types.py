from __future__ import annotations

from enum import StrEnum
from typing import TypedDict


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


class _Door(TypedDict):
    between: list[list[int]]


class _Exit(TypedDict):
    cell: list[int]
    side: str


class MapData(TypedDict):
    rows: int
    columns: int
    matrix: list[list[str]]
    doors: list[_Door]
    exits: list[_Exit]


Coord = tuple[int, int]
