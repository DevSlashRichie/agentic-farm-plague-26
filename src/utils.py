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
        return 2 if _edge(from_pos, to_pos) in model.walls else -1

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


def a_star(
    model: GameModel,
    start: Coord,
    goal: Coord,
) -> Optional[list[Coord]]:
    """Find shortest path on a 2D grid using A* search.

    Movement is 4-directional. Walls and closed doors are passable with extra cost
    (CHOP_WALL = 2 AP, OPEN_DOOR = 1 AP) — the agent follows the returned path and
    chops/opens as it goes. Fire cells remain impassable.

    Edge costs:
        clear edge      = 1  (MOVE)
        closed-door     = 2  (OPEN_DOOR + MOVE)
        wall            = 3  (CHOP_WALL + MOVE)

    Args:
        model: GameModel holding the grid, walls, doors.
        start: (x, y) starting coordinate.
        goal: (x, y) target coordinate.

    Returns:
        List of (x, y) coordinates from start to goal, or None if fire-surrounded.
    """
    if start == goal:
        return [start]

    width = model.width
    height = model.height

    def edge_cost(c: Coord, neighbor: Coord) -> int:
        edge = _edge(c, neighbor)
        cost = 1
        if edge in model.doors and not model.doors[edge]:
            cost += 1
        if edge in model.walls:
            cost += 2
        return cost

    def in_bounds(c: Coord) -> bool:
        x, y = c
        return 0 <= x < width and 0 <= y < height

    def neighbors_of(c: Coord) -> list[Coord]:
        x, y = c
        return [(x + dx, y + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]

    open_set: list[tuple[int, int, Coord]] = []
    counter = 0
    heapq.heappush(open_set, (manhattan(start, goal), counter, start))

    g_score: dict[Coord, int] = {start: 0}
    came_from: dict[Coord, Coord] = {}
    closed: set[Coord] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current == goal:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            return path[::-1]

        if current in closed:
            continue
        closed.add(current)

        for neighbor in neighbors_of(current):
            if not in_bounds(neighbor):
                continue
            if model.get_cell_name(*neighbor) == CellName.FIRE:
                continue
            tentative_g = g_score[current] + edge_cost(current, neighbor)
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + manhattan(neighbor, goal)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    return None
