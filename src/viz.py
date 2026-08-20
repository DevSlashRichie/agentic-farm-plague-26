from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Patch, Rectangle

from src.maps import DEFAULT_MAP
from src.domain import CellName

if TYPE_CHECKING:
    from matplotlib.animation import Animation
    from matplotlib.figure import Figure

    from src.agent import Player
    from src.model import GameModel


CELL_STYLE: dict[CellName, dict] = {
    CellName.NONE: {"color": "#ECECEC", "glyph": "\u00B7", "text_color": "#555555"},
    CellName.FIRE: {"color": "#E74C3C", "glyph": "F", "text_color": "white"},
    CellName.SMOKE: {"color": "#9AA0A6", "glyph": "S", "text_color": "white"},
    CellName.DOOR: {"color": "#8B5A2B", "glyph": "D", "text_color": "white"},
    CellName.WALL: {"color": "#2C2C2C", "glyph": "W", "text_color": "white"},
    CellName.EXIT: {"color": "#2ECC71", "glyph": "E", "text_color": "white"},
    CellName.VICTIM: {"color": "#F1C40F", "glyph": "V", "text_color": "black"},
    CellName.FAKE: {"color": "#FFE066", "glyph": "f", "text_color": "#7A6600"},
    CellName.UNKNOWN: {"color": "#4B4B4B", "glyph": "?", "text_color": "white"},
}

AGENT_CMAP = plt.get_cmap("tab10")


def agent_color(unique_id: int) -> str:
    return AGENT_CMAP(unique_id % 10)


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
    """Create one Rectangle + Text per cell, return as 2D arrays."""
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


def _legend_handles():
    handles = [
        Patch(facecolor=CELL_STYLE[name]["color"], edgecolor="#1A1A1A", label=name.value)
        for name in CellName
    ]
    handles.append(Patch(facecolor=agent_color(0), edgecolor="#1A1A1A", label="player"))
    handles.append(
        Patch(facecolor=agent_color(0), edgecolor="white", linewidth=2.5, label="carrying victim")
    )
    return handles


def _set_agent_marker(marker, pos, carrying: bool, color: str):
    marker.center = (pos[0] + 0.5, pos[1] + 0.5)
    marker.set_facecolor(color)
    marker.set_edgecolor("white" if carrying else "#1A1A1A")
    marker.set_linewidth(2.5 if carrying else 0.8)


def render_map(
    map_data: list[list[str]] | None = None,
    *,
    show: bool = True,
    save_path: str | None = None,
    title: str | None = None,
) -> Figure:
    if map_data is None:
        map_data = DEFAULT_MAP

    height = len(map_data)
    width = len(map_data[0]) if height else 0

    fig, ax, ax_legend = _new_axes(width, height, figsize=(max(6, width * 0.9 + 3), max(4, height * 0.9 + 1)))

    # Build a synthetic grid_data matching DEFAULT_MAP strings (grid_data[x][y] layout, like GameModel).
    grid_data = [
        [{"name": CellName(map_data[y][x])} for y in range(height)]
        for x in range(width)
    ]

    tiles, glyphs = _cell_artists(width, height)
    for x in range(width):
        for y in range(height):
            ax.add_patch(tiles[x][y])
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
    """Pre-run the model, then play back frames in a live matplotlib window.

    Consumes the model: after this call, ``model.running`` is False and its
    state reflects the final step.
    """
    def capture() -> dict:
        return {
            "grid": copy.deepcopy(model.grid_data),
            "agents": [(a.unique_id, tuple(a.pos), a.has_victim) for a in model.agents],
            "steps": model.steps,
            "rescued": model.victims_rescued,
            "killed": model.victims_killed,
        }

    snapshots: list[dict] = [capture()]
    while model.running:
        model.step()
        snapshots.append(capture())

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
        f"Flashpoint \u2014 step 0 / {len(snapshots) - 1}", fontsize=12, pad=10
    )

    ax_legend.legend(
        handles=_legend_handles(),
        title="Legend",
        loc="upper left",
        frameon=False,
        fontsize=10,
        title_fontsize=11,
    )

    def apply(snap: dict) -> list:
        _apply_grid(tiles, glyphs, snap["grid"], width, height)
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
            f"Flashpoint \u2014 step {snap['steps']} / {len(snapshots) - 1}"
        )
        all_artists = [score_text, title_text]
        all_artists.extend(tiles[x][y] for x in range(width) for y in range(height))
        all_artists.extend(g for row in glyphs for g in row if g is not None)
        all_artists.extend(markers)
        return all_artists

    def _init():
        if not snapshots:
            return [score_text, title_text]
        return apply(snapshots[0])

    def _update(i):
        return apply(snapshots[i])

    if not snapshots:
        # Nothing to animate — just show the initial figure.
        if show:
            plt.show()
        return None

    anim = FuncAnimation(
        fig,
        _update,
        init_func=_init,
        frames=len(snapshots),
        interval=interval_ms,
        repeat=False,
        blit=False,
    )

    if save_path:
        anim.save(save_path, writer="pillow")
    if show:
        plt.show()
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