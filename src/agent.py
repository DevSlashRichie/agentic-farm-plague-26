from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from mesa import Agent

from src.domain import CHOP_DAMAGE, Action, CellName, Coord
from src.utils import (
    _action_cost,
    _edge,
    _edge_blocked,
    _extinguish_cost,
    dijkstra,
    manhattan,
)

if TYPE_CHECKING:
    from src.model import GameModel


class Player(Agent):
    def __init__(self, model: GameModel, pos: Coord, spawn_pos: Coord | None = None):
        super().__init__(model)

        self.model: GameModel = self.model
        self.pos: Coord | None = pos
        # Initial EXIT cell. Used as respawn point after ambulance.
        self.spawn_pos: Coord = spawn_pos if spawn_pos is not None else pos
        # Ambulance state: agent is off the coords grid (pos is None).
        self.in_ambulance: bool = False
        # Personal turns to skip while in ambulance ("miss one agent turn").
        self.ambulance_cooldown: int = 0
        self.victims_rescued = 0
        self.visited = 0
        self.action_points = 4
        self.has_victim = False

    def step(self) -> None:
        for _ in self.step_generator():
            pass

    def step_generator(self) -> Iterator[None]:
        did_act = False
        self.model.log(
            "agent_turn",
            agent=self,
            ap=self.action_points,
            pos=self.pos,
            carrying=self.has_victim,
        )

        # Ambulance handling: agent is off the grid (pos is None).
        if self.in_ambulance:
            if self.ambulance_cooldown > 0:
                self.ambulance_cooldown -= 1
                self.model.log(
                    "ambulance_hold",
                    agent=self,
                    cooldown=self.ambulance_cooldown,
                )
                self._reset_action_points()
                return
            if not self.model._try_respawn(self):
                self.model.log(
                    "respawn_wait",
                    agent=self,
                    spawn=self.spawn_pos,
                )
                self._reset_action_points()
                return
            # Respawned: fall through and act this turn.
            self.model.log(
                "agent_turn",
                agent=self,
                ap=self.action_points,
                pos=self.pos,
                carrying=self.has_victim,
            )

        # Fire-touch trigger: standing on a FIRE cell at turn start.
        if self.pos is not None and self.model.get_cell_name(*self.pos) == CellName.FIRE:
            self.model._send_to_ambulance(self)
            return

        if self.pos is None or self.in_ambulance:
            return

        yield from self._discover_once()

        while self.action_points > 0:
            if self.pos is None or self.in_ambulance:
                break
            yield from self._discover_once()

            x, y = self.pos
            cdata = self.model.get_cell_name(x, y)

            # Burn rule: 2+ reachable FIRE/SMOKE cells at/around the agent
            # get turned off before smoke converts and fire spreads. Fires
            # first at 2 AP, smokes at 1 AP. One per pass; recounts next
            # pass until fewer than 2 remain.
            burn = self._nearby_burn(x, y)
            if len(burn) >= 2:
                cell = next(
                    (c for c in burn if self.action_points >= _extinguish_cost(self.model, c)),
                    None,
                )
                if cell is not None:
                    ecost = _extinguish_cost(self.model, cell)
                    self.model.set_cell_name(cell[0], cell[1], CellName.NONE)
                    self.action_points -= ecost
                    self.model.emit_action(self, Action.EXTINGUISH, cell, ecost)
                    did_act = True
                    yield
                    yield from self._discover_once()
                    continue

            if self.has_victim:
                target = self._find_exit()
            else:
                nearest_victim = self._nearest(CellName.VICTIM)
                nearest_unknown = self._nearest(CellName.UNKNOWN)
                if nearest_victim is not None and (
                    nearest_unknown is None
                    or manhattan(self.pos, nearest_victim)
                    < manhattan(self.pos, nearest_unknown)
                ):
                    target = nearest_victim
                else:
                    target = nearest_unknown
            if target is None:
                self.model.log("idle", agent=self, reason="no_target")
                break

            if target == self.pos:
                if self.has_victim or cdata not in {CellName.UNKNOWN, CellName.VICTIM, CellName.FAKE}:
                    break

            path = self._path_to(target)
            if not path:
                self.model.log("idle", agent=self, reason="no_path", target=target)
                break

            self.model.log(
                "path",
                agent=self,
                target=target,
                length=len(path),
                mode="carry" if self.has_victim else "explore",
            )

            action_target, action = path[0]
            if action == Action.EXTINGUISH:
                cost = _extinguish_cost(self.model, action_target)
            else:
                cost = _action_cost(action, self.has_victim)

            if action == Action.MOVE:
                self.pos = action_target
            elif action == Action.OPEN_DOOR:
                self.model.doors[_edge(self.pos, action_target)] = True
            elif action == Action.EXTINGUISH:
                self.model.set_cell_name(action_target[0], action_target[1], CellName.NONE)
            elif action == Action.CHOP_WALL:
                edge = _edge(self.pos, action_target)
                if edge in self.model.walls:
                    self.model.walls.discard(edge)
                    self.model.add_structural_damage(
                        CHOP_DAMAGE,
                        reason="chop",
                        pos=action_target,
                        edge=edge,
                    )

            self.action_points -= cost
            self.model.emit_action(self, action, action_target, cost)
            self.model._try_deliver(self)
            did_act = True
            yield

            yield from self._discover_once()

        self.model._try_deliver(self)
        self.model.log(
            "burst_done",
            agent=self,
            did_act=did_act,
            ap_remaining=self.action_points,
        )
        self._reset_action_points()

    def _discover_once(self) -> Iterator[None]:
        if self.pos is None or self.in_ambulance:
            return
        x, y = self.pos
        cdata = self.model.get_cell_name(x, y)
        if cdata == CellName.UNKNOWN:
            real = self.model.get_hidden(x, y)
            self.model.set_cell_name(x, y, real)
            self.model.log(
                "reveal",
                agent=self,
                cell=(x, y),
                hidden=real,
                picked_victim=False,
            )
            yield
        elif not self.has_victim and cdata == CellName.VICTIM:
            self.model.set_cell_name(x, y, CellName.NONE)
            self.has_victim = True
            self.model.log("pickup", agent=self, cell=(x, y), cell_kind="victim")
            yield
        elif cdata == CellName.FAKE:
            self.model.set_cell_name(x, y, CellName.NONE)
            self.model.log("pickup", agent=self, cell=(x, y), cell_kind="fake")
            yield

    def _reset_action_points(self):
        self.action_points = 4

    def _nearest(self, name: CellName) -> Coord | None:
        if self.pos is None or self.in_ambulance:
            return None
        cells = self.model.get_cells_by_name(name)
        if not cells:
            return None
        nearest = min(cells, key=lambda c: manhattan((c["x"], c["y"]), self.pos))
        return (nearest["x"], nearest["y"])

    def _nearby_burn(self, x: int, y: int) -> list[Coord]:
        """Reachable FIRE/SMOKE cells on the agent's cell plus 8 neighbors.

        Walls and closed doors block reach: orthogonal cells need their
        shared edge open; diagonals need either corner path open. Fires
        come first so the more dangerous cells are cleared first.
        """
        if self.pos is None:
            return []
        here: Coord = (x, y)
        fires: list[Coord] = []
        smokes: list[Coord] = []

        def _collect(cell: Coord) -> None:
            name = self.model.get_cell_name(*cell)
            if name == CellName.FIRE:
                fires.append(cell)
            elif name == CellName.SMOKE:
                smokes.append(cell)

        _collect(here)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nbr = (x + dx, y + dy)
            if not (0 <= nbr[0] < self.model.width and 0 <= nbr[1] < self.model.height):
                continue
            if _edge_blocked(self.model, here, nbr):
                continue
            _collect(nbr)
        for dx, dy in ((-1, -1), (-1, 1), (1, -1), (1, 1)):
            nbr = (x + dx, y + dy)
            if not (0 <= nbr[0] < self.model.width and 0 <= nbr[1] < self.model.height):
                continue
            via_x = (x + dx, y)
            via_y = (x, y + dy)
            if _edge_blocked(self.model, here, via_x) and _edge_blocked(
                self.model, here, via_y
            ):
                continue
            _collect(nbr)
        return fires + smokes

    def _find_exit(self) -> Coord | None:
        return self._nearest(CellName.EXIT)

    def _path_to(self, target: Coord) -> list[tuple[Coord, Action]] | None:
        if self.pos is None or self.in_ambulance:
            return None
        return dijkstra(
            self.model,
            self.pos,
            target,
            carrying=self.has_victim,
        )
