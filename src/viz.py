from __future__ import annotations

import os
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch, Rectangle

from src.maps import DEFAULT_MAP
from src.domain import Action, CellName, Coord, MapData

if TYPE_CHECKING:
    from matplotlib.animation import Animation
    from matplotlib.figure import Figure

    from src.agent import Player
    from src.model import GameModel


_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_RED = "\x1b[31m"
_YELLOW = "\x1b[33m"
_MAGENTA = "\x1b[35m"
_GREEN = "\x1b[32m"


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


_ACTION_COLOR = {
    Action.MOVE: "",
    Action.OPEN_DOOR: _YELLOW,
    Action.EXTINGUISH: _RED,
    Action.CHOP_WALL: _MAGENTA,
}


def quiet_log(kind: str, _payload: dict) -> None:
    """One-line-per-event debug log: actions, reveals, pickups, rescues, kills.

    Skips noisiest kinds (agent_turn, path, idle, burst_done).
    """
    if kind == "action":
        agent = _payload["agent"]
        a: Action = _payload["action"]
        color = _ACTION_COLOR.get(a, "")
        step_num = agent.model.steps
        step_label = _c(_DIM, f"step {step_num}")
        agent_label = f"#{agent.unique_id}@{tuple(agent.pos)}"
        action_label = _c(color, a.value.upper())
        print(
            f"{step_label}  {agent_label}  "
            f"{action_label} -> {_payload['coord']} -{_payload['cost']}AP"
        )
    elif kind == "reveal":
        cell = _payload["cell"]
        hidden = _payload["hidden"].value
        picked = " (picked up!)" if _payload["picked_victim"] else ""
        print(_c(_GREEN, f"  ↪ reveal {cell} → {hidden}{picked}"))
    elif kind == "pickup":
        agent = _payload["agent"]
        cell = _payload["cell"]
        cell_kind = _payload["cell_kind"]
        step_num = agent.model.steps
        step_label = _c(_DIM, f"step {step_num}")
        agent_label = f"#{agent.unique_id}@{tuple(agent.pos)}"
        print(_c(_GREEN, f"{step_label}  {agent_label}  picked up {cell_kind} at {cell}"))
    elif kind == "rescue":
        print(_c(_GREEN, f"  ★ RESCUE @ {_payload['pos']} total={_payload['total']}"))
    elif kind == "kill":
        print(_c(_RED, f"  ☠ KILL @ {_payload['pos']} total={_payload['total']}"))


CELL_STYLE: dict[CellName, dict] = {
    CellName.NONE: {"color": "#ECECEC", "glyph": "\u00B7", "text_color": "#555555"},
    CellName.FIRE: {"color": "#E74C3C", "glyph": "F", "text_color": "white"},
    CellName.SMOKE: {"color": "#9AA0A6", "glyph": "S", "text_color": "white"},
    CellName.EXIT: {"color": "#2ECC71", "glyph": "E", "text_color": "white"},
    CellName.VICTIM: {"color": "#F1C40F", "glyph": "V", "text_color": "black"},
    CellName.FAKE: {"color": "#FFE066", "glyph": "f", "text_color": "#7A6600"},
    CellName.UNKNOWN: {"color": "#4B4B4B", "glyph": "?", "text_color": "white"},
}

WALL_COLOR = "#2C2C2C"
DOOR_CLOSED_COLOR = "#8B5A2B"
DOOR_OPEN_COLOR = "#D4B896"
EDGE_LINEWIDTH = 4
OPEN_LINEWIDTH = 2

AGENT_CMAP = plt.get_cmap("tab10")


def agent_color(unique_id: int) -> str:
    return AGENT_CMAP(unique_id % 10)


def _edge(a: Coord, b: Coord) -> tuple[Coord, Coord]:
    return (a, b) if a < b else (b, a)


def _edges_from_map(
    map_data: MapData,
) -> tuple[set[tuple[Coord, Coord]], dict[tuple[Coord, Coord], bool]]:
    walls: set[tuple[Coord, Coord]] = set()
    for a, b in map_data.get("walls", []):
        walls.add(_edge(a, b))

    doors: dict[tuple[Coord, Coord], bool] = {}
    for a, b in map_data.get("doors", []):
        doors[_edge(a, b)] = False
    return walls, doors


def _new_axes(width: int, height: int, figsize: tuple[float, float]):
    fig = plt.figure(figsize=figsize, constrained_layout=True)
    gs = fig.add_gridspec(1, 2, width_ratios=[max(1, width), 2.2], wspace=0.05)
    ax = fig.add_subplot(gs[0, 0])
    ax_legend = fig.add_subplot(gs[0, 1])
    ax_legend.axis("off")

    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.invert_yaxis()
    ax.set_aspect("equal")
    ax.set_xticks(np.arange(0, width + 1, 1))
    ax.set_yticks(np.arange(0, height + 1, 1))
    ax.set_xticklabels([])
    ax.set_yticklabels([])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.grid(which="both", color="white", linewidth=1.5)
    return fig, ax, ax_legend


def _cell_artists(width: int, height: int):
    """Create one Rectangle per cell, return as 2D arrays."""
    tiles = [[None] * height for _ in range(width)]
    glyphs = [[None] * height for _ in range(width)]
    for y in range(height):
        for x in range(width):
            tiles[x][y] = Rectangle(
                (x, y), 1, 1,
                facecolor=CELL_STYLE[CellName.NONE]["color"],
                edgecolor="#1A1A1A",
                linewidth=0.6,
            )
            glyphs[x][y] = None
    return tiles, glyphs


def _apply_grid(tiles, glyphs, grid_data, width: int, height: int):
    """Update each tile's facecolor and (re)create its glyph text to match grid_data."""
    for y in range(height):
        for x in range(width):
            cell = grid_data[x][y]
            name = cell["name"]
            style = CELL_STYLE.get(name, CELL_STYLE[CellName.NONE])
            tile = tiles[x][y]
            tile.set_facecolor(style["color"])
            glyph = glyphs[x][y]
            if glyph is None:
                glyphs[x][y] = tile.axes.text(
                    x + 0.5, y + 0.5,
                    style["glyph"],
                    ha="center", va="center",
                    color=style["text_color"],
                    fontweight="bold", fontsize=11,
                    zorder=2,
                )
            else:
                glyph.set_text(style["glyph"])
                glyph.set_color(style["text_color"])


def _edge_segment(edge: tuple[Coord, Coord]) -> tuple[list[float], list[float]]:
    """Return ((x1, x2), (y1, y2)) for the Line2D plotting the shared boundary."""
    (x1, y1), (x2, y2) = edge
    if x1 == x2:
        y = max(y1, y2)
        return [min(x1, x2), max(x1, x2) + 1], [y, y]
    x = max(x1, x2)
    return [x, x], [min(y1, y2), max(y1, y2) + 1]


def _make_edge_artists(
    walls: set[tuple[Coord, Coord]],
    doors: dict[tuple[Coord, Coord], bool],
    ax,
) -> tuple[dict[tuple[Coord, Coord], Line2D], dict[tuple[Coord, Coord], Line2D]]:
    """Create wall and door Line2D artists, keyed by edge for stable identity tracking."""
    wall_lines: dict[tuple[Coord, Coord], Line2D] = {}
    for edge in sorted(walls):
        xs, ys = _edge_segment(edge)
        line = Line2D(xs, ys, color=WALL_COLOR, linewidth=EDGE_LINEWIDTH,
                      solid_capstyle="butt", zorder=5)
        ax.add_line(line)
        wall_lines[edge] = line

    door_lines: dict[tuple[Coord, Coord], Line2D] = {}
    for edge in sorted(doors):
        xs, ys = _edge_segment(edge)
        line = Line2D(xs, ys, color=DOOR_CLOSED_COLOR, linewidth=EDGE_LINEWIDTH,
                      solid_capstyle="butt", zorder=5)
        ax.add_line(line)
        door_lines[edge] = line

    return wall_lines, door_lines


def _refresh_edges(
    walls: set[tuple[Coord, Coord]],
    doors: dict[tuple[Coord, Coord], bool],
    wall_lines: dict[tuple[Coord, Coord], Line2D],
    door_lines: dict[tuple[Coord, Coord], Line2D],
) -> None:
    """Sync artists with current walls/doors state (chopped walls hidden, open doors faded)."""
    for edge, line in wall_lines.items():
        line.set_visible(edge in walls)

    for edge, line in door_lines.items():
        if edge not in doors:
            line.set_visible(False)
            continue
        is_open = doors[edge]
        line.set_visible(True)
        if is_open:
            line.set_color(DOOR_OPEN_COLOR)
            line.set_linewidth(OPEN_LINEWIDTH)
            line.set_alpha(0.6)
        else:
            line.set_color(DOOR_CLOSED_COLOR)
            line.set_linewidth(EDGE_LINEWIDTH)
            line.set_alpha(1.0)


def _legend_handles():
    handles = [
        Patch(facecolor=CELL_STYLE[name]["color"], edgecolor="#1A1A1A", label=name.value)
        for name in CellName
    ]
    handles.append(Patch(facecolor=agent_color(0), edgecolor="#1A1A1A", label="player"))
    handles.append(
        Patch(facecolor=agent_color(0), edgecolor="white", linewidth=2.5, label="carrying victim")
    )
    handles.append(Patch(facecolor=WALL_COLOR, edgecolor="#1A1A1A", label="wall"))
    handles.append(Patch(facecolor=DOOR_CLOSED_COLOR, edgecolor="#1A1A1A", label="door (closed)"))
    handles.append(Patch(facecolor=DOOR_OPEN_COLOR, edgecolor="#1A1A1A", label="door (open)"))
    return handles


def _set_agent_marker(marker, pos, carrying: bool, color: str):
    marker.center = (pos[0] + 0.5, pos[1] + 0.5)
    marker.set_facecolor(color)
    marker.set_edgecolor("white" if carrying else "#1A1A1A")
    marker.set_linewidth(2.5 if carrying else 0.8)


def render_map(
    map_data: MapData | None = None,
    *,
    show: bool = True,
    save_path: str | None = None,
    title: str | None = None,
) -> Figure:
    if map_data is None:
        map_data = DEFAULT_MAP

    width = map_data["columns"]
    height = map_data["rows"]
    matrix = map_data["matrix"]

    grid_data = [
        [{"name": CellName(matrix[y][x])} for y in range(height)]
        for x in range(width)
    ]

    walls, doors = _edges_from_map(map_data)

    fig, ax, ax_legend = _new_axes(width, height, figsize=(max(6, width * 0.9 + 3), max(4, height * 0.9 + 1)))

    tiles, glyphs = _cell_artists(width, height)
    for x in range(width):
        for y in range(height):
            ax.add_patch(tiles[x][y])

    wall_lines, door_lines = _make_edge_artists(walls, doors, ax)
    _apply_grid(tiles, glyphs, grid_data, width, height)

    ax.set_title(
        title or f"Flashpoint map \u2014 {height}\u00D7{width}",
        fontsize=12, pad=10,
    )

    ax_legend.legend(
        handles=_legend_handles(),
        title="Legend",
        loc="upper left",
        frameon=False,
        fontsize=10,
        title_fontsize=11,
    )

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    return fig


def animate_simulation(
    model: GameModel,
    *,
    interval_ms: int = 250,
    show: bool = True,
    save_path: str | None = None,
) -> Animation:
    """Animate the simulation live: each matplotlib frame drives one AP.

    Live mode (not pre-run): the matplotlib timer ticks at ``interval_ms`` and
    each tick advances the model by one action point (``model.advance()`` call).
    Log subscribers fire inline as the model advances, so terminal output and
    matplotlib rendering move in lockstep one decision at a time. Once the
    ``model.advance()`` chain finalizes the current step (and returns False),
    the figure stays on the final state until the window is closed (or until
    the Pillow writer exhausts the frame budget when ``save_path`` is set).
    """
    width = model.width
    height = model.height

    fig, ax, ax_legend = _new_axes(
        width, height,
        figsize=(max(6, width * 0.9 + 3), max(4, height * 0.9 + 1.4)),
    )

    tiles, glyphs = _cell_artists(width, height)
    for x in range(width):
        for y in range(height):
            ax.add_patch(tiles[x][y])

    initial_walls = set(model.walls)
    initial_doors = dict(model.doors)
    wall_lines, door_lines = _make_edge_artists(initial_walls, initial_doors, ax)

    max_agents = len(model.agents)
    markers: list[Circle] = []
    for i in range(max_agents):
        m = Circle((0.5, 0.5), 0.30, zorder=3, visible=False)
        ax.add_patch(m)
        markers.append(m)

    score_text = ax.text(
        0.98, 0.02,
        "",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=10, fontweight="bold",
        bbox=dict(facecolor="white", edgecolor="#1A1A1A", boxstyle="round,pad=0.3"),
        zorder=4,
    )

    title_text = ax.set_title(
        f"Flashpoint \u2014 step 0 / {model.max_steps}", fontsize=12, pad=10
    )

    ax_legend.legend(
        handles=_legend_handles(),
        title="Legend",
        loc="upper left",
        frameon=False,
        fontsize=10,
        title_fontsize=11,
    )

    def capture() -> dict:
        return {
            "grid": [
                [{"name": model.get_cell_name(x, y)} for y in range(height)]
                for x in range(width)
            ],
            "walls": set(model.walls),
            "doors": dict(model.doors),
            "agents": [(a.unique_id, tuple(a.pos), a.has_victim) for a in model.agents],
            "steps": model.steps,
            "rescued": model.victims_rescued,
            "killed": model.victims_killed,
        }

    def apply() -> list:
        snap = capture()
        _apply_grid(tiles, glyphs, snap["grid"], width, height)
        _refresh_edges(snap["walls"], snap["doors"], wall_lines, door_lines)
        agents = snap["agents"]
        for i, marker in enumerate(markers):
            if i < len(agents):
                uid, pos, carrying = agents[i]
                _set_agent_marker(marker, pos, carrying, agent_color(uid))
                marker.set_visible(True)
            else:
                marker.set_visible(False)
        score_text.set_text(
            f"step {snap['steps']} \u00B7 rescued {snap['rescued']} "
            f"\u00B7 killed {snap['killed']} \u00B7 active {len(agents)}"
        )
        title_text.set_text(
            f"Flashpoint \u2014 step {snap['steps']} / {model.max_steps}"
        )
        all_artists = [score_text, title_text]
        all_artists.extend(tiles[x][y] for x in range(width) for y in range(height))
        all_artists.extend(g for row in glyphs for g in row if g is not None)
        all_artists.extend(wall_lines.values())
        all_artists.extend(door_lines.values())
        all_artists.extend(markers)
        return all_artists

    def _init() -> list:
        return apply()

    def _update(_i) -> list:
        if model.running:
            model.advance()
        return apply()

    model._log_subscribers.append(quiet_log)

    if save_path:
        frame_budget = max(200, model.max_steps * model.steps * 6 + 20)
    else:
        frame_budget = None

    try:
        anim = FuncAnimation(
            fig,
            _update,
            init_func=_init,
            interval=interval_ms,
            repeat=False,
            blit=False,
            cache_frame_data=False,
            frames=frame_budget,
        )
        if save_path:
            anim.save(save_path, writer="pillow")
        if show:
            plt.show()
    finally:
        model._log_subscribers.remove(quiet_log)

    return anim


if __name__ == "__main__":
    import argparse

    from src.model import GameModel

    parser = argparse.ArgumentParser(description="Flashpoint map viz")
    parser.add_argument("--animate", action="store_true", help="Animate the simulation")
    parser.add_argument("--interval-ms", type=int, default=250, help="ms per frame (animate)")
    parser.add_argument("--save", type=str, default=None, help="Save output to path")
    args = parser.parse_args()

    if args.animate:
        model = GameModel()
        animate_simulation(model, interval_ms=args.interval_ms, show=True, save_path=args.save)
    else:
        render_map(show=True, save_path=args.save)
