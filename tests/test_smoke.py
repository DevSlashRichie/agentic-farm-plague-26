from __future__ import annotations

from src.maps import default_map
from src.model import GameModel


def _drain(model: GameModel) -> None:
    """Drive the model until running flips to False."""
    while model.running:
        model.step()


def test_default_map_runs_to_completion():
    """Default config must end within max_steps with no exceptions."""
    model = GameModel(map_data=default_map(), seed=42)
    _drain(model)
    assert model.steps <= model.max_steps
    assert not model.running


def test_default_match_predicted_baseline():
    """Regression: default_map + seed=42 produces deterministic rescued/killed/steps.

    Spawn-on-rescue + per-step smoke spawn are both enabled. With seed=42
    the run terminates via the win condition ``rescued >= 7``.
    """
    model = GameModel(map_data=default_map(), seed=42)
    _drain(model)
    assert model.victims_rescued == 7, f"got {model.victims_rescued}"
    assert model.victims_killed == 0, f"got {model.victims_killed}"


def test_max_steps_cap_respected():
    """When no end condition fires (max_steps not reached, no rescue, no kill),
    run stops at max_steps. With spawn-on-rescue + win condition, this is
    only reachable if agents fail to rescue and the win condition never
    fires. We assert no crash on the deterministic seeded path instead."""
    model = GameModel(map_data=default_map(), seed=42)
    _drain(model)
    # With seed=42 the win condition (rescued >= 7) fires before max_steps.
    assert model.steps < model.max_steps
    assert model.victims_rescued >= 7


def test_steps_time_aligned_under_default_schedule():
    """With the inherited 1.0-interval default schedule, model.steps == int(model.time)."""
    model = GameModel(map_data=default_map(), seed=42)
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
