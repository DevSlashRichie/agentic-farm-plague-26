from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, Optional, TypedDict

from src.domain import (
    CHOP_AP_COST,
    FIRE_EXTINGUISH_COST,
    SMOKE_EXTINGUISH_COST,
    Action,
    CellName,
    Coord,
)

if TYPE_CHECKING:
    from src.agent import Player
    from src.model import GameModel


class ActionOption(TypedDict):
    action: Action
    coord: Coord
    cost: int


def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


_ORTHOGONAL_OFFSETS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_DIAGONAL_OFFSETS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
_MOORE_OFFSETS = _ORTHOGONAL_OFFSETS + _DIAGONAL_OFFSETS

_OFFSETS_BY_MODE = {
    "orthogonal": _ORTHOGONAL_OFFSETS,
    "diagonal": _DIAGONAL_OFFSETS,
    "moore": _MOORE_OFFSETS,
}


def get_neighbors(
    pos: Coord,
    mode: str = "orthogonal",
    width: int | None = None,
    height: int | None = None,
) -> list[Coord]:
    try:
        offsets = _OFFSETS_BY_MODE[mode]
    except KeyError:
        raise ValueError(f"unknown mode={mode!r}, expected one of {sorted(_OFFSETS_BY_MODE)}")
    x, y = pos
    cells = [(x + dx, y + dy) for dx, dy in offsets]
    if width is not None and height is not None:
        cells = [c for c in cells if 0 <= c[0] < width and 0 <= c[1] < height]
    return cells


def _edge(a: Coord, b: Coord) -> tuple[Coord, Coord]:
    return (a, b) if a < b else (b, a)


def _edge_blocked(model: GameModel, from_pos: Coord, to_pos: Coord) -> bool:
    edge = _edge(from_pos, to_pos)
    if edge in model.walls:
        return True
    if edge in model.doors and not model.doors[edge]:
        return True
    return False


def calc_action_score(
    model: GameModel,
    action: Action,
    from_pos: Coord,
    to_pos: Coord,
    carrying_victim: bool,
) -> int:
    x, y = to_pos

    if not (0 <= x < model.width and 0 <= y < model.height):
        return -1

    cell_name = model.get_cell_name(x, y)

    if action == Action.MOVE:
        if manhattan(from_pos, to_pos) != 1 or cell_name == CellName.FIRE:
            return -1
        if _edge_blocked(model, from_pos, to_pos):
            return -1
        return 2 if carrying_victim else 1

    if action == Action.EXTINGUISH:
        return 1 if cell_name == CellName.FIRE else -1

    if action == Action.OPEN_DOOR:
        edge = _edge(from_pos, to_pos)
        if edge in model.doors and not model.doors[edge]:
            return 1
        return -1

    if action == Action.CHOP_WALL:
        return 4 if _edge(from_pos, to_pos) in model.walls else -1

    return -1


def valid_actions(
    model: GameModel,
    agent: Player,
    to_pos: Coord | None = None,
) -> list[ActionOption]:
    if agent.pos is None or agent.in_ambulance:
        return []
    from_pos = agent.pos
    carrying_victim = agent.has_victim

    if to_pos is None:
        targets = get_neighbors(from_pos, mode="orthogonal")
    else:
        targets = [to_pos]

    results: list[ActionOption] = []
    for target in targets:
        for action in Action:
            score = calc_action_score(model, action, from_pos, target, carrying_victim)
            if score >= 0:
                results.append({"action": action, "coord": target, "cost": score})
    return results


def _action_cost(action: Action, carrying: bool) -> int:
    if action == Action.MOVE:
        return 2 if carrying else 1
    return {
        Action.OPEN_DOOR: 1,
        Action.CHOP_WALL: CHOP_AP_COST,
        Action.EXTINGUISH: 1,
    }.get(action, 1)


def _extinguish_cost(model: GameModel, coord: Coord) -> int:
    """AP cost to extinguish a cell by what is actually on it."""
    if model.get_cell_name(*coord) == CellName.FIRE:
        return FIRE_EXTINGUISH_COST
    return SMOKE_EXTINGUISH_COST


def _edge_actions(model: GameModel, c: Coord, neighbor: Coord, carrying: bool) -> list[Action]:
    actions: list[Action] = []
    edge = _edge(c, neighbor)
    if edge in model.walls:
        actions.append(Action.CHOP_WALL)
    elif edge in model.doors and not model.doors[edge]:
        actions.append(Action.OPEN_DOOR)
    if model.get_cell_name(*neighbor) == CellName.FIRE:
        actions.append(Action.EXTINGUISH)
    actions.append(Action.MOVE)
    return actions


def dijkstra(
    model: GameModel,
    start: Coord,
    goal: Coord,
    *,
    carrying: bool = False,
) -> Optional[list[tuple[Coord, Action]]]:
    if start == goal:
        return []

    width = model.width
    height = model.height

    def edge_cost_total(c: Coord, neighbor: Coord) -> int:
        total = 0
        for a in _edge_actions(model, c, neighbor, carrying):
            if a == Action.EXTINGUISH:
                total += _extinguish_cost(model, neighbor)
            else:
                total += _action_cost(a, carrying)
        return total

    counter = 0
    open_set: list[tuple[int, int, Coord]] = []
    heapq.heappush(open_set, (0, counter, start))

    g_score: dict[Coord, int] = {start: 0}
    came_from: dict[Coord, Coord] = {}
    closed: set[Coord] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal:
            # Reconstruct position path.
            pos_path = [current]
            while current in came_from:
                current = came_from[current]
                pos_path.append(current)
            pos_path.reverse()
            # Expand each cell-to-cell transition into its action sequence.
            # target = ngbr for every action: the cell the action affects
            # (destination for MOVE; neighbor for OPEN_DOOR/CHOP_WALL/EXTINGUISH).
            action_seq: list[tuple[Coord, Action]] = []
            for i in range(len(pos_path) - 1):
                c, nbr = pos_path[i], pos_path[i + 1]
                for action in _edge_actions(model, c, nbr, carrying):
                    action_seq.append((nbr, action))
            return action_seq

        if current in closed:
            continue
        closed.add(current)

        for neighbor in get_neighbors(current, mode="orthogonal", width=width, height=height):
            tentative_g = g_score[current] + edge_cost_total(current, neighbor)
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                counter += 1
                heapq.heappush(open_set, (tentative_g, counter, neighbor))

    return None
