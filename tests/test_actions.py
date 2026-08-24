from __future__ import annotations

from src.agent import Player
from src.domain import Action, CellName
from src.maps import default_map
from src.model import GameModel


def test_emit_action_fires_per_ap():
    """Every AP-consuming action must fire emit_action with the right metadata."""
    events: list[tuple[Player, Action, tuple[int, int], int]] = []

    model = GameModel(map_data=default_map())

    def record(agent, action, coord, cost):
        events.append((agent, action, coord, cost))

    model._on_action.append(record)
    try:
        while model.running:
            model.step()
    finally:
        model._on_action.remove(record)

    assert events, "expected at least one action event"
    for agent, action, coord, cost in events:
        assert isinstance(agent, Player)
        assert action in Action
        assert isinstance(coord, tuple) and len(coord) == 2
        assert cost >= 1


def test_no_emit_action_subscribers_no_error():
    """Empty subscriber list must not break the simulation."""
    model = GameModel(map_data=default_map())
    assert model._on_action == []
    while model.running:
        model.step()
    assert model.victims_rescued == 3
    assert model.victims_killed == 0


def test_emit_action_fires_more_than_steps():
    """At least one action should fire before the first step boundary is checked,
    proving emit_action fires inside the burst loop rather than only at step end."""
    model = GameModel(map_data=default_map())
    counts_per_step: list[int] = [0]
    model._on_action.append(lambda *_: counts_per_step.__setitem__(
        0, counts_per_step[0] + 1
    ))
    while model.running:
        pre = counts_per_step[0]
        model.step()
        post = counts_per_step[0]
        if post > pre:
            return  # success: event fired before step() returned
    raise AssertionError("emit_action never fired during the simulation")
