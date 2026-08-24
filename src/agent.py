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
        """Burst loop that yields control after each AP-consuming action and after
        every discovery (UNKNOWN reveal / VICTIM pickup / FAKE pickup).

        Discovery is checked at TWO sites so that an agent moving onto an
        UNKNOWN (or VICTIM/FAKE) cell on its LAST action point still gets a
        frame for the discovery:

          1. **Spawn time**: ``yield from self._discover_once()`` once before
             any actions fire. Handles agents placed on UNKNOWN/VICTIM/FAKE
             cells at startup.

          2. **Post-action**: after each ``emit_action`` we yield, then
             ``yield from self._discover_once()``. This catches the
             MOVE-onto-UNKNOWN-on-last-AP case (the loop guard
             ``while self.action_points > 0`` would otherwise exit before any
             top-of-iter discovery could run).
        """
        did_act = False
        self.model.log(
            "agent_turn",
            agent=self,
            ap=self.action_points,
            pos=self.pos,
            carrying=self.has_victim,
        )

        # Spawn-time discovery: agent starts on UNKNOWN / VICTIM / FAKE.
        yield from self._discover_once()

        while self.action_points > 0:
            # Top-of-iter discovery: catch the case where the agent is standing
            # on a VICTIM/FAKE that was revealed previously and not yet picked
            # up. Without this, target == self.pos would short-circuit the
            # loop and leave the VICTIM stranded (fire can then kill it).
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
                # Already at the target cell. The top-of-iter discovery
                # above may have picked up a VICTIM here; if so, fall through
                # so the next iteration computes a new target (nearest EXIT).
                if self.has_victim or cdata not in {CellName.UNKNOWN, CellName.VICTIM, CellName.FAKE}:
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

            # Post-action discovery: catches MOVE-onto-UNKNOWN-on-last-AP.
            yield from self._discover_once()

        self.model._try_deliver(self)
        self.model.log(
            "burst_done",
            agent=self,
            did_act=did_act,
            ap_remaining=self.action_points,
        )
        self.reset_action_points()

    def _discover_once(self) -> Iterator[None]:
        """Discover current cell; yield exactly once if anything was discovered.

        Sub-iterator pattern used with ``yield from`` in :meth:`step_generator`.
        Yields once when a discovery happens (UNKNOWN reveal, VICTIM pickup,
        or FAKE pickup) and returns nothing otherwise.

        ``UNKNOWN`` reveals are pure exposure: the cell adopts its hidden
        value (VICTIM, FAKE, …) but ``self.has_victim`` stays False. Other
        agents can plan against the now-visible VICTIM; the revealing
        agent decides later whether to pick it up via the VICTIM pickup
        branch on a subsequent iteration.
        """
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
