from __future__ import annotations

import json
import os
from collections.abc import Callable

from src.agent import Player
from src.domain import Action, CellName

_RESET = "\x1b[0m"
_BOLD = "\x1b[1m"
_DIM = "\x1b[2m"
_CYAN = "\x1b[36m"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"
_MAGENTA = "\x1b[35m"
_GREY = "\x1b[90m"


def _use_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    try:
        return os.isatty(1)
    except Exception:
        return False


_USE_COLOR = _use_color()


def _c(code: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{code}{text}{_RESET}"


def _agent(agent) -> str:
    return _c(_DIM, f"#{agent.unique_id}@{tuple(agent.pos)}")


def _action_color(action: Action) -> str:
    return {
        Action.MOVE: "",
        Action.OPEN_DOOR: _YELLOW,
        Action.EXTINGUISH: _RED,
        Action.CHOP_WALL: _MAGENTA,
    }.get(action, "")


def _f_step_begin(p: dict) -> str:
    return _c(_BOLD + _CYAN, f"=== step {p['step']} ({p['agents']} agents) ===")


def _f_step_end(p: dict) -> str:
    running = "✓ running" if p["running"] else "✗ stopped"
    extras = f" [{p['end_reason']}]" if p.get("end_reason") else ""
    return _c(
        _GREY,
        f"─── step {p['step']} end (rescued={p['rescued']}, killed={p['killed']}, {running}) ───{extras}",
    )


def _f_agent_turn(p: dict) -> str:
    carry = _c(_YELLOW, "carrying=victim") if p["carrying"] else _c(_GREY, "idle")
    return f"  ▸ agent {_agent(p['agent'])} AP={p['ap']} {carry}"


def _f_reveal(p: dict) -> str:
    hidden = p["hidden"].value
    color = _GREEN if p["picked_victim"] else _GREY
    verb = "VICTIM!" if p["picked_victim"] else hidden
    return f"    ↳ revealed at {p['cell']} → {_c(color, verb)}"


def _f_pickup(p: dict) -> str:
    return f"    ↳ picked up {p['cell_kind']} at {p['cell']}"


def _f_idle(p: dict) -> str:
    target = f" target={p.get('target')}" if p.get("target") is not None else ""
    return f"    ↳ idle ({_c(_GREY, p['reason'])}){target}"


def _f_path(p: dict) -> str:
    return f"    ↳ path {p['mode']} → {p['target']} len={p['length']}"


def _f_target_legacy(p: dict) -> str:  # noqa: D401
    return f"    ↳ target={p['target']} ({p['mode']})"


def _f_action(p: dict) -> str:
    color = _action_color(p["action"])
    name = _c(color, p["action"].value.upper())
    return f"    ▸ {name} → {p['coord']} −{p['cost']}AP"


def _f_burst_done(p: dict) -> str:
    if p["did_act"]:
        return _c(_GREY, f"    ⏎ burst done (AP remaining {p['ap_remaining']})")
    return _c(_GREY, "    ⏎ burst idle (no action taken)")


def _f_rescue(p: dict) -> str:
    return _c(_BOLD + _GREEN, f"  ★ RESCUE @ {p['pos']} (total={p['total']})")


def _f_kill(p: dict) -> str:
    return _c(_BOLD + _RED, f"  ☠ KILL @ {p['pos']} (total={p['total']})")


def _f_spawn(p: dict) -> str:
    return _c(_CYAN, f"  ◇ spawn UNKNOWN @ {p['cell']} hides {p['hidden_kind']}")


def _f_smoke_spawn(p: dict) -> str:
    return _c(_CYAN, f"  ~ smoke_spawn {p['was']}→{p['became']} @ {p['cell']}")


def _f_explode(p: dict) -> str:
    return _c(_BOLD + _RED, f"  💥 explode → fire @ {p['cell']} (origin {p['origin']})")


FORMATTERS: dict[str, Callable[[dict], str]] = {
    "step_begin": _f_step_begin,
    "step_end": _f_step_end,
    "agent_turn": _f_agent_turn,
    "reveal": _f_reveal,
    "pickup": _f_pickup,
    "idle": _f_idle,
    "path": _f_path,
    "target": _f_target_legacy,
    "action": _f_action,
    "burst_done": _f_burst_done,
    "rescue": _f_rescue,
    "kill": _f_kill,
    "spawn": _f_spawn,
    "smoke_spawn": _f_smoke_spawn,
    "explode": _f_explode,
}


def terminal_logger(kind: str, payload: dict) -> None:
    fmt = FORMATTERS.get(kind)
    if fmt is None:
        return
    print(fmt(payload))


def _jsonify(payload: dict) -> dict:
    out: dict = {}
    for k, v in payload.items():
        if isinstance(v, Player):
            out[k] = {
                "unique_id": v.unique_id,
                "pos": list(v.pos),
                "has_victim": v.has_victim,
                "action_points": v.action_points,
            }
        elif isinstance(v, Action):
            out[k] = v.value
        elif isinstance(v, CellName):
            out[k] = v.value
        elif isinstance(v, tuple):
            out[k] = list(v)
        else:
            out[k] = v
    return out


class JsonCollector:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def __call__(self, kind: str, payload: dict) -> None:
        self.events.append({"kind": kind, **_jsonify(payload)})

    def dump(self, result: dict) -> None:
        print(json.dumps({"events": self.events, "result": result}))
