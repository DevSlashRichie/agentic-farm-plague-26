from mesa import Model, DataCollector

from src.agent import Player
from src.maps import default_map
from src.types import CellName


class GameModel(Model):
    def __init__(self, agents=6, max_steps=50, map_data: list[list[str]] | None = None):
        super().__init__()
        if map_data is None:
            map_data = default_map()

        self.steps = 0

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

    def _load_map(self, map_data: list[list[str]]):
        self.height = len(map_data)
        self.width = len(map_data[0]) if self.height else 0

        self.grid_data = [
            [{"name": CellName.NONE} for _ in range(self.height)]
            for __ in range(self.width)
        ]

        for y, row in enumerate(map_data):
            for x, cell_name in enumerate(row):
                self.grid_data[x][y] = {"name": CellName(cell_name)}

        for x in range(self.width):
            for y in range(self.height):
                if self.grid_data[x][y]["name"] == CellName.UNKNOWN:
                    self.grid_data[x][y]["hidden"] = CellName.VICTIM

    def _spawn_agents(self, count: int):
        exits = self.get_cells_by_name(CellName.EXIT)
        if not exits:
            return
        for i in range(count):
            exit_cell = exits[i % len(exits)]
            Player(self, (exit_cell["x"], exit_cell["y"]))

    def _kill_victims_in_fire(self):
        for x in range(self.width):
            for y in range(self.height):
                if self.grid_data[x][y]["name"] != CellName.VICTIM:
                    continue
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        if self.grid_data[nx][ny]["name"] == CellName.FIRE:
                            self.grid_data[x][y] = {"name": CellName.FIRE}
                            self.victims_killed += 1
                            break

    def get_cells_by_name(self, name: CellName | str):
        return [
            {"x": x, "y": y, **self.grid_data[x][y]}
            for x in range(self.width)
            for y in range(self.height)
            if self.grid_data[x][y]["name"] == name
        ]

    def _is_end_condition_met(self):
        if self.victims_rescued >= 3:
            return "3 victims rescued"
        if self.victims_killed >= 1:
            return "victim killed by fire"
        if self.steps >= self.max_steps:
            return "max steps reached"
        return None

    def step(self):
        if not self.running:
            return

        for agent in self.agents:
            agent.step()
            agent.reset_action_points()

        self._kill_victims_in_fire()
        self.datacollector.collect(self)

        reason = self._is_end_condition_met()
        if reason:
            print(reason)
            self.running = False

        self.steps += 1
