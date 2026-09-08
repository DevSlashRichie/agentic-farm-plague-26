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


def map_to_json(map_data: dict) -> dict:
    return {
        "width": map_data["columns"],
        "height": map_data["rows"],
        "cells": map_data["matrix"],
        "walls": [list(map(list, w)) for w in map_data["walls"]],
        "doors": [list(map(list, d)) for d in map_data["doors"]],
    }


def agents_to_json(agents) -> list[dict]:
    return [
        {"id": a.unique_id, "pos": list(a.pos), "carrying": a.has_victim}
        for a in agents
    ]


def _cell_key(pos: tuple[int, int]) -> tuple[int, int]:
    return (pos[0], pos[1])


class JsonCollector:
    def __init__(self, map_data: dict, agents) -> None:
        self.map_json = map_to_json(map_data)
        self.agents_json = agents_to_json(agents)

        self._cell_states: dict[tuple[int, int], str] = {}
        for y, row in enumerate(map_data["matrix"]):
            for x, cell_name in enumerate(row):
                self._cell_states[(x, y)] = cell_name

        self._steps: list[dict] = []
        self._current_events: list[dict] = []
        self._current_step: int | None = None
        self._explode_buffer: dict[tuple[int, int], list[list[int]]] = {}
        self._agent_positions: dict[int, tuple[int, int]] = {}
        for a in agents:
            self._agent_positions[a.unique_id] = a.pos

    def __call__(self, kind: str, payload: dict) -> None:
        if kind == "step_begin":
            self._flush_explodes()
            self._current_step = payload["step"]
            return

        if kind == "step_end":
            self._flush_explodes()
            if self._current_step is not None:
                self._steps.append({
                    "step": self._current_step,
                    "events": self._current_events,
                })
                self._current_events = []
                self._current_step = None
            return

        delta = self._transform(kind, payload)
        if delta is None:
            return
        if isinstance(delta, list):
            self._current_events.extend(delta)
        else:
            self._current_events.append(delta)

    def _transform(self, kind: str, payload: dict) -> dict | None:
        if kind == "action":
            return self._transform_action(payload)
        if kind == "reveal":
            return self._transform_reveal(payload)
        if kind == "spawn":
            return self._transform_spawn(payload)
        if kind == "smoke_spawn":
            return self._transform_smoke_spawn(payload)
        if kind == "explode":
            return self._buffer_explode(payload)
        if kind == "pickup":
            return self._transform_pickup(payload)
        if kind == "rescue":
            return self._transform_rescue(payload)
        if kind == "kill":
            return self._transform_kill(payload)
        return None

    def _transform_action(self, p: dict) -> dict:
        action: Action = p["action"]
        coord: tuple[int, int] = p["coord"]
        agent_id: int = p["agent"].unique_id

        if action == Action.MOVE:
            prev = self._agent_positions.get(agent_id, p["agent"].pos)
            self._agent_positions[agent_id] = coord
            return {
                "type": "move",
                "agent": agent_id,
                "from": list(prev),
                "to": list(coord),
                "ap_remaining": p["agent"].action_points,
            }
        if action == Action.EXTINGUISH:
            key = _cell_key(coord)
            from_state = self._cell_states.get(key, "fire")
            self._cell_states[key] = "none"
            return [
                {"type": "cell_change", "pos": list(coord), "from": from_state, "to": "none"},
                {
                    "type": "extinguish",
                    "agent": agent_id,
                    "pos": list(coord),
                    "ap_remaining": p["agent"].action_points,
                },
            ]
        if action == Action.OPEN_DOOR:
            return {
                "type": "door_open",
                "agent": agent_id,
                "from": list(p["agent"].pos),
                "to": list(coord),
                "ap_remaining": p["agent"].action_points,
            }
        if action == Action.CHOP_WALL:
            return {
                "type": "wall_chop",
                "agent": agent_id,
                "from": list(p["agent"].pos),
                "to": list(coord),
                "ap_remaining": p["agent"].action_points,
            }
        return {
            "type": action.value,
            "agent": agent_id,
            "pos": list(coord),
            "ap_remaining": p["agent"].action_points,
        }

    def _transform_reveal(self, p: dict) -> dict:
        cell: tuple[int, int] = p["cell"]
        hidden: CellName = p["hidden"]
        key = _cell_key(cell)
        from_state = self._cell_states.get(key, "unknown")
        self._cell_states[key] = hidden.value
        return {"type": "cell_change", "pos": list(cell), "from": from_state, "to": hidden.value}

    def _transform_spawn(self, p: dict) -> dict:
        cell: tuple[int, int] = p["cell"]
        key = _cell_key(cell)
        from_state = self._cell_states.get(key, "none")
        self._cell_states[key] = "unknown"
        return {"type": "cell_change", "pos": list(cell), "from": from_state, "to": "unknown"}

    def _transform_smoke_spawn(self, p: dict) -> dict | None:
        cell: tuple[int, int] = p["cell"]
        was: str = p["was"]
        became: str = p["became"]

        if became == "fire_explode":
            return None

        key = _cell_key(cell)
        self._cell_states[key] = became
        return {"type": "cell_change", "pos": list(cell), "from": was, "to": became}

    def _buffer_explode(self, p: dict) -> None:
        origin: tuple[int, int] = p["origin"]
        cell: tuple[int, int] = p["cell"]
        key = _cell_key(cell)
        self._cell_states[key] = "fire"

        if origin not in self._explode_buffer:
            self._explode_buffer[origin] = []
        self._explode_buffer[origin].append(list(cell))
        return None

    def _flush_explodes(self) -> None:
        for origin, cells in self._explode_buffer.items():
            self._current_events.append({
                "type": "fire_spread",
                "origin": list(origin),
                "cells": cells,
            })
        self._explode_buffer.clear()

    def _transform_pickup(self, p: dict) -> dict:
        return {
            "type": "pickup",
            "agent": p["agent"].unique_id,
            "pos": list(p["cell"]),
            "kind": p["cell_kind"],
            "ap_remaining": p["agent"].action_points,
        }

    def _transform_rescue(self, p: dict) -> dict:
        return {
            "type": "rescue",
            "agent": p["agent"].unique_id,
            "pos": list(p["pos"]),
            "total": p["total"],
            "ap_remaining": p["agent"].action_points,
        }

    def _transform_kill(self, p: dict) -> list[dict]:
        pos: tuple[int, int] = p["pos"]
        key = _cell_key(pos)
        self._cell_states[key] = "fire"
        return [
            {"type": "cell_change", "pos": list(pos), "from": "victim", "to": "fire"},
            {"type": "kill", "pos": list(pos), "total": p["total"]},
        ]

    def to_dict(self, result: dict) -> dict:
        self._flush_explodes()
        return {
            "map": self.map_json,
            "agents": self.agents_json,
            "steps": self._steps,
            "result": result,
        }

    def dump(self, result: dict) -> None:
        print(json.dumps(self.to_dict(result)))
