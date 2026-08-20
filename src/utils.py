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

    cell_name = model.grid_data[x][y]["name"]

    if action == Action.MOVE:
        if (
            manhattan(from_pos, to_pos) != 1
            or cell_name in (CellName.FIRE, CellName.DOOR, CellName.WALL)
        ):
            return -1
        return 2 if carrying_victim else 1

    if action == Action.EXTINGUISH:
        return 1 if cell_name == CellName.FIRE else -1

    if action == Action.OPEN_DOOR:
        return 1 if cell_name == CellName.DOOR else -1

    if action == Action.CHOP_WALL:
        return 2 if cell_name == CellName.WALL else -1

    return -1


def valid_actions(
    model: GameModel,
    agent: Player,
    to_pos: Coord | None = None,
) -> list[ActionOption]:
    from_pos = agent.pos
    carrying_victim = agent.has_victim

    if to_pos is None:
        x, y = from_pos
        targets = [(x + dx, y + dy) for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))]
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
    grid_data: list[list[dict]],
    start: Coord,
    goal: Coord,
) -> Optional[list[Coord]]:
    """Find shortest path on a 2D grid using A* search.

    Movement is 4-directional (up, down, left, right) with uniform step cost.
    Cells with name FIRE, WALL, or DOOR are impassable.

    Args:
        grid_data: 2D grid of cell dicts (`grid_data[x][y]`) with key "name".
        start: (x, y) starting coordinate.
        goal: (x, y) target coordinate.

    Returns:
        List of (x, y) coordinates from start to goal, or None if no path exists.
    """
    if start == goal:
        return [start]

    width = len(grid_data)
    height = len(grid_data[0]) if width else 0

    impassable = {CellName.FIRE, CellName.WALL, CellName.DOOR}

    def in_bounds(c: Coord) -> bool:
        x, y = c
        return 0 <= x < width and 0 <= y < height

    def passable(c: Coord) -> bool:
        x, y = c
        if not in_bounds(c):
            return False
        return grid_data[x][y]["name"] not in impassable

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

        x, y = current
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            neighbor = (nx, ny)
            if not in_bounds(neighbor) or not passable(neighbor):
                continue
            tentative_g = g_score[current] + 1
            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score = tentative_g + manhattan(neighbor, goal)
                counter += 1
                heapq.heappush(open_set, (f_score, counter, neighbor))

    return None
