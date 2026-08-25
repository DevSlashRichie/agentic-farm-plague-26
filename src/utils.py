from __future__ import annotations

import heapq
from typing import TYPE_CHECKING, Optional, TypedDict

from src.domain import Action, CellName, Coord

if TYPE_CHECKING:
    from src.agent import Player
    from src.model import GameModel


class ActionOption(TypedDict):
    action: Action
    coord: Coord
    cost: int


def manhattan(a: Coord, b: Coord) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


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
    from_pos = agent.pos
    carrying_victim = agent.has_victim

    if to_pos is None:
        fx, fy = from_pos
        targets = [(fx + dx, fy + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
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
    """AP cost of a single action. MOVE costs 2 if carrying a victim."""
    if action == Action.MOVE:
        return 2 if carrying else 1
    return {
        Action.OPEN_DOOR: 1,
        Action.CHOP_WALL: 4,
        Action.EXTINGUISH: 2,
    }.get(action, 1)


def _edge_actions(model: GameModel, c: Coord, neighbor: Coord, carrying: bool) -> list[Action]:
    """Action sequence to traverse from cell ``c`` to adjacent cell ``neighbor``.

    Order: edge-prep (CHOP_WALL or OPEN_DOOR if needed) → MOVE → EXTINGUISH
    if the destination cell is on fire.
    """
    actions: list[Action] = []
    edge = _edge(c, neighbor)
    if edge in model.walls:
        actions.append(Action.CHOP_WALL)
    elif edge in model.doors and not model.doors[edge]:
        actions.append(Action.OPEN_DOOR)
    actions.append(Action.MOVE)
    if model.get_cell_name(*neighbor) == CellName.FIRE:
        actions.append(Action.EXTINGUISH)
    return actions


def dijkstra(
    model: GameModel,
    start: Coord,
    goal: Coord,
    *,
    carrying: bool = False,
) -> Optional[list[tuple[Coord, Action]]]:
    """Find shortest action sequence from ``start`` to ``goal``.

    Returns a list of ``(target_coord, action)`` tuples — one per agent action.
    ``target_coord`` is the cell the action affects: the neighbor for
    ``OPEN_DOOR`` / ``CHOP_WALL`` / ``EXTINGUISH`` (the agent stays at
    ``c``), or the destination for ``MOVE``. The agent's position updates to
    ``target_coord`` after ``MOVE`` and is unchanged for the others.

    Empty list means ``start == goal``. ``None`` means unreachable.

    Args:
        model: GameModel holding the grid, walls, doors.
        start: (x, y) starting coordinate.
        goal: (x, y) target coordinate.
        carrying: whether the agent is carrying a victim (MOVE = 2 AP).

    Returns:
        List of (target_coord, action) tuples, or None.
    """
    if start == goal:
        return []

    width = model.width
    height = model.height

    def in_bounds(c: Coord) -> bool:
        x, y = c
        return 0 <= x < width and 0 <= y < height

    def neighbors_of(c: Coord) -> list[Coord]:
        x, y = c
        return [(x + dx, y + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]

    def edge_cost_total(c: Coord, neighbor: Coord) -> int:
        return sum(_action_cost(a, carrying) for a in _edge_actions(model, c, neighbor, carrying))

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
            # target = nbr for every action: the cell the action affects
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

        for neighbor in neighbors_of(current):
            if not in_bounds(neighbor):
                continue
            tentative_g = g_score[current] + edge_cost_total(current, neighbor)
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                counter += 1
                heapq.heappush(open_set, (tentative_g, counter, neighbor))

    return None
