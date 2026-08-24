from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from mesa import Agent

from src.domain import Action, CellName, Coord
from src.utils import _edge, a_star, manhattan, valid_actions

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
        """Drain the burst loop synchronously (legacy behavior, used by agents.do('step'))."""
        for _ in self.step_generator():
            pass

    def step_generator(self) -> Iterator[None]:
        """Burst loop that yields control after each AP-consuming action.

        Used by ``GameModel.advance()`` to drive the simulation AP-by-AP so
        matplotlib (or other consumers) can render one decision at a time.
        A bare ``yield None`` is emitted immediately after ``emit_action``,
        before the next decision iteration begins.
        """
        did_act = False
        self.model.log(
            "agent_turn",
            agent=self,
            ap=self.action_points,
            pos=self.pos,
            carrying=self.has_victim,
        )
        while self.action_points > 0:
            x, y = self.pos
            cdata = self.model.get_cell_name(x, y)

            if cdata == CellName.UNKNOWN:
                real = self.model.get_hidden(x, y)
                if real == CellName.VICTIM:
                    self.model.set_cell_name(x, y, CellName.NONE)
                    self.has_victim = True
                else:
                    self.model.set_cell_name(x, y, real)
                self.model.log(
                    "reveal",
                    agent=self,
                    cell=(x, y),
                    hidden=real,
                    picked_victim=(real == CellName.VICTIM),
                )
                yield
                continue

            if not self.has_victim:
                if cdata == CellName.VICTIM:
                    self.model.set_cell_name(x, y, CellName.NONE)
                    self.has_victim = True
                    self.model.log("pickup", agent=self, cell=(x, y), kind="victim")
                    yield
                    continue
                if cdata == CellName.FAKE:
                    self.model.set_cell_name(x, y, CellName.NONE)
                    self.model.log("pickup", agent=self, cell=(x, y), kind="fake")
                    yield
                    continue

            target = self._find_exit() if self.has_victim else self._nearest(CellName.UNKNOWN)
            if target is None or target == self.pos:
                if target is None:
                    self.model.log("idle", agent=self, reason="no_target")
                break

            path = self._path_to(target)
            if not path or len(path) < 2:
                self.model.log("idle", agent=self, reason="no_path", target=target)
                break

            self.model.log(
                "path",
                agent=self,
                target=target,
                length=len(path),
                mode="carry" if self.has_victim else "explore",
            )

            next_pos = path[1]
            actions = valid_actions(self.model, self, to_pos=next_pos)
            if not actions:
                self.model.log("idle", agent=self, reason="blocked", target=target)
                break

            option = actions[0]
            action = option["action"]
            coord = option["coord"]
            cost = option["cost"]

            if action == Action.MOVE:
                self.pos = coord
            elif action == Action.OPEN_DOOR:
                self.model.doors[_edge(self.pos, coord)] = True
            elif action == Action.EXTINGUISH:
                self.model.set_cell_name(coord[0], coord[1], CellName.NONE)
            elif action == Action.CHOP_WALL:
                self.model.walls.discard(_edge(self.pos, coord))

            self.action_points -= cost
            self.model.emit_action(self, action, coord, cost)
            self.model._try_deliver(self)
            did_act = True
            yield

        self.model._try_deliver(self)
        self.model.log(
            "burst_done",
            agent=self,
            did_act=did_act,
            ap_remaining=self.action_points,
        )
        self.reset_action_points()

    def reset_action_points(self):
        self.action_points = 4

    def _nearest(self, name: CellName) -> Coord | None:
        cells = self.model.get_cells_by_name(name)
        if not cells:
            return None
        nearest = min(cells, key=lambda c: manhattan((c["x"], c["y"]), self.pos))
        return (nearest["x"], nearest["y"])

    def _find_exit(self) -> Coord | None:
        return self._nearest(CellName.EXIT)

    def _path_to(self, target: Coord) -> list[Coord] | None:
        return a_star(self.model, self.pos, target)
