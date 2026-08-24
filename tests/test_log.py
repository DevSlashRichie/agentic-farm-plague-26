from __future__ import annotations

from src.agent import Player
from src.maps import default_map
from src.model import GameModel


def _drain(model: GameModel, logger=None) -> list[tuple[str, dict]]:
    """Drive the model until running flips False. Optionally attach a collector."""
    if logger is not None:
        model._log_subscribers.append(logger)
    try:
        while model.running:
            model.step()
    finally:
        if logger is not None:
            try:
                model._log_subscribers.remove(logger)
            except ValueError:
                pass
    return []


def test_log_subscribers_receive_expected_kinds():
    """Full-run: certain kinds must fire at least once across the default sim."""
    seen: list[str] = []

    def collect(kind: str, _payload: dict) -> None:
        seen.append(kind)

    model = GameModel()
    _drain(model, collect)

    expected = {"step_begin", "step_end", "agent_turn", "action", "burst_done"}
    missing = expected - set(seen)
    assert not missing, f"missing kinds: {missing}"


def test_log_rescue_event_fires_when_victim_delivered():
    """A rescue event with payload['total'] == 1 must fire when an agent delivers."""
    seen: list[dict] = []

    def collect(kind: str, payload: dict) -> None:
        if kind == "rescue":
            seen.append(payload)

    model = GameModel()
    Player(model, (5, 0)).__class__  # force module load (no-op)
    model._log_subscribers.append(collect)

    # Place an agent carrying a victim directly on an EXIT cell so step()#1 will deliver.
    exit_cells = model.get_cells_by_name("exit")
    ex, ey = exit_cells[0]["x"], exit_cells[0]["y"]
    carrier = Player(model, (ex, ey))
    carrier.has_victim = True
    model._log_subscribers.append(collect)
    try:
        model.step()
    finally:
        try:
            model._log_subscribers.remove(collect)
        except ValueError:
            pass

    assert seen, "expected a rescue event"
    assert seen[0]["total"] == 1


def test_log_kill_event_fires_on_fire_propagation():
    """A VICTIM cell adjacent to FIRE triggers a kill event on the next step."""
    seen: list[dict] = []

    def collect(kind: str, payload: dict) -> None:
        if kind == "kill":
            seen.append(payload)

    minimal_map = {
        "rows": 3,
        "columns": 3,
        "matrix": [
            ["fire", "victim", "none"],
            ["none", "none", "none"],
            ["none", "none", "exit"],
        ],
        "walls": [],
        "doors": [],
    }
    model = GameModel(agents=0, map_data=minimal_map)
    model._log_subscribers.append(collect)
    try:
        model.step()
    finally:
        try:
            model._log_subscribers.remove(collect)
        except ValueError:
            pass

    assert seen, "expected a kill event"
    assert seen[0]["total"] == 1
    assert seen[0]["pos"] == (1, 0)


def test_log_emitted_inside_burst_loop():
    """Reveal/pickup/target/path/idle events fire before step() returns (inside the burst)."""
    saw_inside: list[str] = []

    def collect(kind: str, _payload: dict) -> None:
        saw_inside.append(kind)

    model = GameModel()
    model._log_subscribers.append(collect)

    pre_total = 0
    try:
        while model.running:
            pre = len(saw_inside)
            model.step()
            post = len(saw_inside)
            new = saw_inside[pre:post]
            pre_total += len(new)
            if any(k in {"reveal", "pickup", "target", "path", "idle"} for k in new):
                return  # success: an in-burst event appeared before this step() returned
    finally:
        try:
            model._log_subscribers.remove(collect)
        except ValueError:
            pass

    raise AssertionError(
        f"no in-burst event (reveal/pickup/target/path/idle) ever fired; total events={pre_total}"
    )


def test_idle_logged_when_no_target():
    """Agent on a NONE cell with no UNKNOWNs anywhere -> idle( no_target ).

    Uses a minimal 2x2 map (no UNKNOWNs, no EXITs) so the agent has no target
    to seek and must idle. Spawn-on-rescue doesn't apply because no rescue
    can happen (no EXITs).
    """
    seen: list[dict] = []

    def collect(kind: str, payload: dict) -> None:
        if kind == "idle":
            seen.append(payload)

    minimal_map = {
        "rows": 2,
        "columns": 2,
        "matrix": [
            ["none", "none"],
            ["none", "none"],
        ],
        "walls": [],
        "doors": [],
    }
    model = GameModel(agents=0, map_data=minimal_map)
    player = Player(model, (0, 0))
    assert not player.has_victim

    model._log_subscribers.append(collect)
    try:
        model.step()
    finally:
        try:
            model._log_subscribers.remove(collect)
        except ValueError:
            pass

    assert seen, "expected an idle event"
    assert any(p.get("reason") == "no_target" for p in seen), \
        f"expected reason='no_target', got {[p.get('reason') for p in seen]}"
