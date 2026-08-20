from mesa import Model, MultiGrid, RandomActivation, DataCollector

from src.maps import default_map
from src.types import CellName, MapData


class GameModel(Model):
    def __init__(self, agents=6, max_steps=50, map_data: MapData | None = None):
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

    def _load_map(self, map_data: MapData):
        self.width = map_data["columns"]
        self.height = map_data["rows"]
        self.grid = MultiGrid(self.width, self.height, torus=False)

        self.grid_data = [
            [{"name": CellName.NONE} for _ in range(self.height)]
            for __ in range(self.width)
        ]

        for y, row in enumerate(map_data["matrix"]):
            for x, cell_name in enumerate(row):
                self.grid_data[x][y] = {"name": CellName(cell_name)}

        for door in map_data["doors"]:
            r, c = door["between"][0]
            self.grid_data[c - 1][r - 1] = {"name": CellName.DOOR}

        for exit in map_data["exits"]:
            r, c = exit["cell"]
            self.grid_data[c - 1][r - 1] = {"name": CellName.EXIT}

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
