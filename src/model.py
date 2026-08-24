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
    def __init__(self, agents=6, max_steps=50, map_data: MapData | None = None):
        super().__init__()
        if map_data is None:
            map_data = default_map()

        self.victims_killed = 0
        self.victims_rescued = 0

        self.max_steps = max_steps
        self._load_map(map_data)
        self._spawn_agents(agents)

        self.datacollector = DataCollector(
            model_reporters={
                "steps": lambda model: model.steps,
                "victims_rescued": lambda model: model.victims_rescued,
                "victims_killed": lambda model: model.victims_killed,
            },
        )

        self._on_action: list[Callable[[Player, Action, Coord, int], None]] = []
        self._log_subscribers: list[Callable[[str, dict], None]] = []
        self._step_state: list[tuple[Player, Iterator[None]]] | None = None

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

    def emit_action(self, agent: Player, action: Action, coord: Coord, cost: int) -> None:
        """Fan out an action event to all subscribed callbacks.

        Fired once per action-point-consuming decision inside ``Player.step``
        (i.e. after each MOVE / OPEN_DOOR / EXTINGUISH / CHOP_WALL). Free
        actions like revealing UNKNOWN or picking up a victim do not emit.
        """
        for cb in self._on_action:
            cb(agent, action, coord, cost)
        self.log("action", agent=agent, action=action, coord=coord, cost=cost)

    def log(self, kind: str, **payload) -> None:
        """Fan out a narrative event to log subscribers.

        ``kind`` is a stable tag (e.g. ``"step_begin"``, ``"rescue"``).
        Subscribers receive ``(kind, payload_dict)``.
        Unknown kinds are forward-compatible (subscribers may ignore them).
        """
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
        if self.victims_killed >= 1:
            return "victim killed by fire"
        if self.steps >= self.max_steps:
            return "max steps reached"
        return None

    def step(self):
        """Run one full step synchronously by draining advance() to completion."""
        while self.advance():
            pass

    def advance(self) -> bool:
        """Advance the simulation by one action point, across all agents.

        Returns ``True`` if more actions remain in the current step
        (``fire`` propagation, ``datacollector``, end-condition check not
        yet executed). Returns ``False`` once the step is finalized.

        Continuous calls drive the simulation AP-by-AP: agent 1 AP-N,
        agent 2 AP-N, …, agent K AP-N, then agent 1 AP-(N+1), etc.
        Each call yields control after firing ``emit_action``, ``_try_deliver``,
        and any ``log()`` callbacks.
        """
        if not self.running:
            return False

        if self._step_state is None:
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
        self.datacollector.collect(self)
        reason = self._is_end_condition_met()
        self.log(
            "step_end",
            step=self.steps,
            rescued=self.victims_rescued,
            killed=self.victims_killed,
            running=self.running,
            end_reason=reason,
        )
        if reason:
            self.running = False
            print(reason)
        self._step_state = None
        return False
