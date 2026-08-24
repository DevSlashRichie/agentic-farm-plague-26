from __future__ import annotations

from src.maps import default_map
from src.model import GameModel


def _drain(model: GameModel) -> None:
    """Drive the model until running flips to False."""
    while model.running:
        model.step()


def test_default_map_runs_to_completion():
    """Default config must end within max_steps with no exceptions."""
    model = GameModel(map_data=default_map())
    _drain(model)
    assert model.steps <= model.max_steps
    assert not model.running


def test_default_match_predicted_baseline():
    """Regression: default_map + default agents produces 3 rescued / 0 killed / 50 steps."""
    model = GameModel(map_data=default_map())
    _drain(model)
    assert model.victims_rescued == 3, f"got {model.victims_rescued}"
    assert model.victims_killed == 0, f"got {model.victims_killed}"


def test_max_steps_cap_respected():
    """When no end condition fires, run stops at max_steps."""
    model = GameModel(map_data=default_map())
    _drain(model)
    assert model.steps == model.max_steps


def test_steps_time_aligned_under_default_schedule():
    """With the inherited 1.0-interval default schedule, model.steps == int(model.time)."""
    model = GameModel(map_data=default_map())
    _drain(model)
    assert model.steps == int(model.time)


def test_grid_replaces_legacy_grid_data():
    """After migration: no more grid_data attribute; cells accessible via grid + cell_type."""
    model = GameModel(map_data=default_map())
    assert not hasattr(model, "grid_data")
    assert hasattr(model, "grid")
    cell = model.grid[(0, 0)]
    assert cell.cell_type >= 0


def test_walls_and_doors_preserved():
    """Walls and doors survive migration as model attributes."""
    model = GameModel(map_data=default_map())
    assert isinstance(model.walls, set)
    assert isinstance(model.doors, dict)


def test_agent_count_default():
    model = GameModel(map_data=default_map())
    assert len(model.agents) == 6
