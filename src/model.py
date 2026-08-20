from mesa import Model, MultiGrid, RandomActivation, DataCollector

from src.maps import default_map
from src.types import CellName


class GameModel(Model):
    def __init__(self, agents=6, max_steps=50, map_data: list[list[str]] | None = None):
        super().__init__()
        if map_data is None:
            map_data = default_map()

        self.schedule = RandomActivation(self)
        self.steps = 0

        self.victims_killed = 0
        self.victims_rescued = 0

        self.max_steps = max_steps
        self._load_map(map_data)

        self.datacollector = DataCollector(
            model_reporters={
                "steps": lambda model: model.steps,
            },
            agent_reporters={"victims_rescued": lambda agent: agent.victims_rescued},
        )

    def _load_map(self, map_data: list[list[str]]):
        self.height = len(map_data)
        self.width = len(map_data[0]) if self.height else 0
        self.grid = MultiGrid(self.width, self.height, torus=False)

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

    def get_cells_by_name(self, name: CellName | str):
        return [
            {"x": x, "y": y, **self.grid_data[x][y]}
            for x in range(self.width)
            for y in range(self.height)
            if self.grid_data[x][y]["name"] == name
        ]

    def step(self):
        if not self.running:
            return

        self.steps += 1
        self.datacollector.collect(self)

        for agent in self.schedule.agents:
            agent.step()
            agent.reset_action_points()

        if self.victims_rescued >= 7 or self.victims_killed >= 3:
            self.running = False
