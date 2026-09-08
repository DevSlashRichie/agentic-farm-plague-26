from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING

from mesa import DataCollector, Model
from mesa.discrete_space import OrthogonalVonNeumannGrid

from src.agent import Player
from src.domain import CellName, Coord, MapData
from src.maps import default_map

if TYPE_CHECKING:
    from src.domain import Action


class GameModel(Model):
    STRUCTURAL_LIMIT = 24

    def __init__(
        self,
        agents=6,
        max_steps=50,
        map_data: MapData | None = None,
        seed: float | int | None = None,
    ):
        super().__init__(seed=seed)
        if map_data is None:
            map_data = default_map()

        self.victims_killed = 0
        self.victims_rescued = 0
        self.structural_damage = 0

        self.max_steps = max_steps
        self._load_map(map_data)
        self._spawn_agents(agents)

        self.datacollector = DataCollector(
            model_reporters={
                "steps": lambda model: model.steps,
                "victims_rescued": lambda model: model.victims_rescued,
                "victims_killed": lambda model: model.victims_killed,
                "structural_damage": lambda model: model.structural_damage,
            },
        )

        self._on_action: list[Callable[[Player, Action, Coord, int], None]] = []
        self._log_subscribers: list[Callable[[str, dict], None]] = []
        self._step_state: list[tuple[Player, Iterator[None]]] | None = None
        self._in_user_step: bool = False

    @property
    def _type_value(self) -> dict[CellName, int]:
        return {
            CellName.NONE: 0,
            CellName.VICTIM: 1,
            CellName.FAKE: 2,
            CellName.FIRE: 3,
            CellName.SMOKE: 4,
            CellName.EXIT: 5,
            CellName.UNKNOWN: 6,
        }

    @property
    def _reverse_type_value(self) -> dict[int, CellName]:
        return {v: k for k, v in self._type_value.items()}

    def _edge(self, a: Coord, b: Coord) -> tuple[Coord, Coord]:
        return (a, b) if a < b else (b, a)

    def _load_map(self, map_data: MapData):
        self.width = map_data["columns"]
        self.height = map_data["rows"]

        self.grid = OrthogonalVonNeumannGrid(
            dimensions=(self.height, self.width),
            torus=False,
            random=self.random,
        )
        self.grid.create_property_layer(
            "cell_type",
            default_value=self._type_value[CellName.NONE],
            dtype=int,
        )
        self.grid.create_property_layer(
            "hidden_type",
            default_value=self._type_value[CellName.NONE],
            dtype=int,
        )

        tv = self._type_value
        matrix = map_data["matrix"]
        for y, row in enumerate(matrix):
            for x, cell_name in enumerate(row):
                cell = self.grid[(y, x)]
                name = CellName(cell_name)
                cell.cell_type = tv[name]
                if name == CellName.UNKNOWN:
                    cell.hidden_type = tv[CellName.VICTIM]

        self.walls: set[tuple[Coord, Coord]] = set()
        for a, b in map_data["walls"]:
            self.walls.add(self._edge(a, b))

        self.doors: dict[tuple[Coord, Coord], bool] = {}
        for a, b in map_data["doors"]:
            self.doors[self._edge(a, b)] = False

    def _spawn_agents(self, count: int):
        exits = self.get_cells_by_name(CellName.EXIT)
        if not exits:
            return
        for i in range(count):
            exit_cell = exits[i % len(exits)]
            Player(self, (exit_cell["x"], exit_cell["y"]))

    def get_cell_name(self, x: int, y: int) -> CellName:
        return self._reverse_type_value[self.grid[(y, x)].cell_type]

    def set_cell_name(self, x: int, y: int, name: CellName) -> None:
        self.grid[(y, x)].cell_type = self._type_value[name]

    def get_hidden(self, x: int, y: int) -> CellName:
        return self._reverse_type_value[self.grid[(y, x)].hidden_type]

    def set_hidden(self, x: int, y: int, name: CellName) -> None:
        self.grid[(y, x)].hidden_type = self._type_value[name]

    def _try_deliver(self, agent: Player) -> None:
        if not agent.has_victim:
            return
        x, y = agent.pos
        if self.get_cell_name(x, y) != CellName.EXIT:
            return
        agent.has_victim = False
        self.victims_rescued += 1
        self.log(
            "rescue",
            agent=agent,
            pos=(x, y),
            total=self.victims_rescued,
        )
        self._spawn_unknowns_to_maintain_three()

    def _count_alive_victims(self) -> int:
        count = 0
        for cell in self.grid.all_cells:
            if self._reverse_type_value[cell.cell_type] == CellName.VICTIM:
                count += 1
        for agent in self.agents:
            if agent.has_victim:
                count += 1
        return count

    def _spawn_unknowns_to_maintain_three(self) -> None:
        target = max(0, 3 - self._count_alive_victims())
        if target == 0:
            return
        candidates = self.get_cells_by_name(CellName.NONE)
        if not candidates:
            return
        n = min(target, len(candidates))
        sample = self.random.sample(candidates, n)
        for cell_data in sample:
            x, y = cell_data["x"], cell_data["y"]
            kind = CellName.VICTIM if self.random.random() < 0.5 else CellName.FAKE
            self.set_cell_name(x, y, CellName.UNKNOWN)
            self.set_hidden(x, y, kind)
            self.log("spawn", cell=(x, y), hidden_kind=kind.value)

    def emit_action(self, agent: Player, action: Action, coord: Coord, cost: int) -> None:
        for cb in self._on_action:
            cb(agent, action, coord, cost)
        self.log("action", agent=agent, action=action, coord=coord, cost=cost)

    def add_structural_damage(
        self,
        amount: int,
        *,
        reason: str,
        pos: Coord | None = None,
        edge: tuple[Coord, Coord] | None = None,
    ) -> None:
        self.structural_damage += amount
        self.log(
            "structural_damage",
            amount=amount,
            reason=reason,
            total=self.structural_damage,
            pos=pos,
            edge=edge,
        )
        if self.structural_damage >= self.STRUCTURAL_LIMIT:
            self.log("collapse", total=self.structural_damage)

    def log(self, kind: str, **payload) -> None:
        for cb in self._log_subscribers:
            cb(kind, payload)

    def _kill_victims_in_fire(self):
        tv = self._type_value
        fire_v = tv[CellName.FIRE]
        victim_v = tv[CellName.VICTIM]
        for cell in self.grid.all_cells:
            if cell.cell_type != victim_v:
                continue
            for neighbor in cell.connections.values():
                if neighbor.cell_type == fire_v:
                    cell.cell_type = fire_v
                    self.victims_killed += 1
                    row, col = cell.coordinate
                    self.log(
                        "kill",
                        pos=(col, row),
                        total=self.victims_killed,
                    )
                    break

    def _smoke_spawn_step(self) -> None:
        x = self.random.randrange(self.width)
        y = self.random.randrange(self.height)
        cell = self.grid[(y, x)]
        was = self._reverse_type_value[cell.cell_type]

        if was == CellName.FIRE:
            self.log(
                "smoke_spawn",
                cell=(x, y),
                was="fire",
                became="fire_explode",
            )
            self._explode_at(x, y)
            return

        became = CellName.FIRE if was == CellName.SMOKE else CellName.SMOKE
        cell.cell_type = self._type_value[became]
        self.log(
            "smoke_spawn",
            cell=(x, y),
            was=was.value,
            became=became.value,
        )

    def _explode_at(self, fx: int, fy: int) -> None:
        from src.utils import _edge

        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            prev = (fx, fy)
            cx, cy = fx + dx, fy + dy
            while 0 <= cx < self.width and 0 <= cy < self.height:
                cur = (cx, cy)
                if _edge(prev, cur) in self.walls:
                    self.add_structural_damage(
                        1,
                        reason="explosion",
                        pos=cur,
                        edge=_edge(prev, cur),
                    )
                    break
                if self.get_cell_name(cx, cy) == CellName.FIRE:
                    prev = cur
                    cx += dx
                    cy += dy
                    continue
                self.set_cell_name(cx, cy, CellName.FIRE)
                self.log(
                    "explode",
                    cell=(cx, cy),
                    origin=(fx, fy),
                    direction=(dx, dy),
                )
                break

    def get_cells_by_name(self, name: CellName | str):
        if isinstance(name, str):
            name = CellName(name)
        target = self._type_value[name]
        return [
            {"x": c.coordinate[1], "y": c.coordinate[0]}
            for c in self.grid.all_cells
            if c.cell_type == target
        ]

    def _is_end_condition_met(self):
        if self.victims_rescued >= 7:
            return "7 victims rescued"
        if self.victims_killed >= 3:
            return "victim killed by fire"
        if self.structural_damage >= self.STRUCTURAL_LIMIT:
            return "structural collapse (damage >= 24)"
        if self.steps >= self.max_steps:
            return "max steps reached"
        return None

    def step(self):
        self._in_user_step = True
        try:
            while self.advance():
                pass
        finally:
            self._in_user_step = False

    def advance(self) -> bool:
        if not self.running:
            return False

        if self._step_state is None:
            if not self._in_user_step:
                self.steps += 1

            self.log("step_begin", step=self.steps, agents=len(self.agents))
            self._step_state = [(a, a.step_generator()) for a in self.agents]

        while self._step_state:
            agent, gen = self._step_state[0]
            try:
                next(gen)
                return True
            except StopIteration:
                self._step_state.pop(0)
                continue

        self._kill_victims_in_fire()
        self._smoke_spawn_step()
        self.datacollector.collect(self)
        reason = self._is_end_condition_met()
        self.log(
            "step_end",
            step=self.steps,
            rescued=self.victims_rescued,
            killed=self.victims_killed,
            structural_damage=self.structural_damage,
            running=self.running,
            end_reason=reason,
        )
        if reason:
            self.running = False
        self._step_state = None
        return False
