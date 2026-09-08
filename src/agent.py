from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from mesa import Agent

from src.domain import Action, CellName, Coord
from src.utils import _action_cost, _edge, dijkstra, manhattan

if TYPE_CHECKING:
    from src.model import GameModel


class Player(Agent):
    def __init__(self, model: GameModel, pos: Coord):
        super().__init__(model)

        self.model: GameModel = self.model
        self.pos: Coord = pos
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

        yield from self._discover_once()

        while self.action_points > 0:
            yield from self._discover_once()

            x, y = self.pos
            cdata = self.model.get_cell_name(x, y)

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
                        2,
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
        cells = self.model.get_cells_by_name(name)
        if not cells:
            return None
        nearest = min(cells, key=lambda c: manhattan((c["x"], c["y"]), self.pos))
        return (nearest["x"], nearest["y"])

    def _find_exit(self) -> Coord | None:
        return self._nearest(CellName.EXIT)

    def _path_to(self, target: Coord) -> list[tuple[Coord, Action]] | None:
        return dijkstra(
            self.model,
            self.pos,
            target,
            carrying=self.has_victim,
        )
