from mesa import Agent

from src.types import CellName, Coord
from src.model import GameModel
from src.utils import a_star, manhattan, valid_actions


class Player(Agent):
    def __init__(self, model: GameModel):
        super().__init__(model)

        self.model: GameModel = self.model
        self.victims_rescued = 0
        self.visited = 0
        self.action_points = 4
        self.has_victim = False

    def step(self):
        while self.action_points > 0:
            x, y = self.pos
            cdata = self.model.grid_data[x][y]

            if cdata["name"] == CellName.UNKNOWN:
                real = cdata["hidden"]
                self.model.grid_data[x][y] = {"name": real}
                if real == CellName.VICTIM:
                    self.has_victim = True
                    self.victims_rescued += 1
                continue

            if not self.has_victim:
                if cdata["name"] == CellName.VICTIM:
                    self.model.grid_data[x][y] = {"name": CellName.NONE}
                    self.has_victim = True
                    self.victims_rescued += 1
                    continue
                if cdata["name"] == CellName.FAKE:
                    self.model.grid_data[x][y] = {"name": CellName.NONE}
                    continue

            target = self._find_exit() if self.has_victim else self._nearest(CellName.UNKNOWN)

            if target is None:
                break

            path = self._path_to(target)
            if not path or len(path) < 2:
                break

            next_pos = path[1]
            actions = valid_actions(self.model, self, to_pos=next_pos)

            if not actions:
                break

            ap = min(a["cost"] for a in actions)
            self.pos = next_pos
            self.action_points -= ap

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
        return a_star(self.model.grid_data, self.pos, target)
