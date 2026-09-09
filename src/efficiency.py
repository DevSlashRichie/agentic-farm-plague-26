"""Batch benchmark: win rate + speed/efficiency of the current strategy.

Runs headless GameModel simulations over N seeds (optionally sweeping
agent counts) and prints a terminal summary table.

Usage:
    .venv/bin/python -m src.efficiency --seeds 30 --agents 6 --max-steps 50
    .venv/bin/python -m src.efficiency --seeds 10 --agents 2 4 6
"""

from __future__ import annotations

import argparse
import statistics

from src.domain import Action
from src.maps import default_map
from src.model import GameModel


def run_once(agents: int, max_steps: int, seed: int) -> dict:
    model = GameModel(
        agents=agents, max_steps=max_steps, map_data=default_map(), seed=seed
    )
    counts = {a: 0 for a in Action}
    ap_total = 0
    chop_damage = 0
    explosion_damage = 0

    def _sub(kind: str, payload: dict) -> None:
        nonlocal ap_total, chop_damage, explosion_damage
        if kind == "action":
            counts[payload["action"]] += 1
            ap_total += payload["cost"]
        elif kind == "structural_damage":
            if payload.get("reason") == "chop":
                chop_damage += payload["amount"]
            elif payload.get("reason") == "explosion":
                explosion_damage += payload["amount"]

    model._log_subscribers.append(_sub)
    while model.running:
        model.step()

    rescued = model.victims_rescued
    return {
        "seed": seed,
        "agents": agents,
        "won": rescued >= 7,
        "steps": model.steps,
        "rescued": rescued,
        "killed": model.victims_killed,
        "damage": model.structural_damage,
        "chop_damage": chop_damage,
        "explosion_damage": explosion_damage,
        "ap_total": ap_total,
        "ap_per_rescue": ap_total / max(1, rescued),
        "n_move": counts[Action.MOVE],
        "n_extinguish": counts[Action.EXTINGUISH],
        "n_open": counts[Action.OPEN_DOOR],
        "n_chop": counts[Action.CHOP_WALL],
        "end_reason": model._is_end_condition_met() or "running",
    }


def _mean_std(values: list[float]) -> str:
    if not values:
        return "n/a"
    mean = statistics.mean(values)
    if len(values) < 2:
        return f"{mean:.2f}"
    return f"{mean:.2f}±{statistics.stdev(values):.2f}"


def summarize(runs: list[dict]) -> dict:
    wins = [r for r in runs if r["won"]]
    losses: dict[str, int] = {}
    for r in runs:
        if not r["won"]:
            losses[r["end_reason"]] = losses.get(r["end_reason"], 0) + 1
    win_steps = [r["steps"] for r in wins]
    return {
        "n": len(runs),
        "wins": len(wins),
        "win_rate": 100.0 * len(wins) / max(1, len(runs)),
        "steps_win": _mean_std(win_steps),
        "steps_all": _mean_std([r["steps"] for r in runs]),
        "ap_per_rescue": _mean_std([r["ap_per_rescue"] for r in runs]),
        "rescued": _mean_std([r["rescued"] for r in runs]),
        "damage": _mean_std([r["damage"] for r in runs]),
        "chops": _mean_std([r["n_chop"] for r in runs]),
        "extinguish": _mean_std([r["n_extinguish"] for r in runs]),
        "losses": losses,
    }


def print_report(all_runs: dict[int, list[dict]], seeds: int, max_steps: int) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(
        f"[bold]Efficiency benchmark[/bold]: seeds={seeds} max_steps={max_steps}"
    )
    console.print("Win = 7+ rescued. Lose = 3 killed, damage >= 24, or timeout.")

    if len(all_runs) > 1:
        compare = Table(title="Config comparison", show_lines=False)
        for col in ("agents", "win rate", "steps/win", "AP/rescue", "dmg/run", "chops/run"):
            compare.add_column(col, justify="right")
        for agents, runs in all_runs.items():
            s = summarize(runs)
            compare.add_row(
                str(agents),
                f"{s['win_rate']:.1f}% ({s['wins']}/{s['n']})",
                s["steps_win"],
                s["ap_per_rescue"],
                s["damage"],
                s["chops"],
            )
        console.print(compare)

    for agents, runs in all_runs.items():
        s = summarize(runs)

        summary = Table(
            title=f"Summary (agents={agents})",
            show_header=True,
            show_lines=False,
        )
        summary.add_column("metric", style="cyan")
        summary.add_column("value", justify="right", style="bold")
        summary.add_row("win rate", f"{s['win_rate']:.1f}% ({s['wins']}/{s['n']})")
        summary.add_row("steps/win", s["steps_win"])
        summary.add_row("steps/run", s["steps_all"])
        summary.add_row("AP/rescue", s["ap_per_rescue"])
        summary.add_row("rescued/run", s["rescued"])
        summary.add_row("dmg/run", s["damage"])
        summary.add_row("chops/run", s["chops"])
        summary.add_row("extinguish/run", s["extinguish"])
        losses = (
            ", ".join(f"{k}={v}" for k, v in s["losses"].items())
            if s["losses"]
            else "none"
        )
        summary.add_row("losses", losses)
        console.print(summary)

        detail = Table(title=f"Per-seed detail (agents={agents})", show_lines=False)
        for col in ("seed", "won", "steps", "resc", "AP/resc", "chop", "ext", "dmg", "reason"):
            justify = "left" if col == "reason" else "right"
            detail.add_column(col, justify=justify)
        for r in runs:
            won_str = "[green]✓[/green]" if r["won"] else "[red]✗[/red]"
            detail.add_row(
                str(r["seed"]),
                won_str,
                str(r["steps"]),
                str(r["rescued"]),
                f"{r['ap_per_rescue']:.2f}",
                str(r["n_chop"]),
                str(r["n_extinguish"]),
                str(r["damage"]),
                r["end_reason"],
            )
        console.print(detail)


def main() -> None:
    parser = argparse.ArgumentParser(description="Win-efficiency benchmark")
    parser.add_argument("--seeds", type=int, default=30)
    parser.add_argument("--agents", type=int, nargs="+", default=[6])
    parser.add_argument("--max-steps", type=int, default=50)
    parser.add_argument("--seed-offset", type=int, default=0)
    args = parser.parse_args()

    all_runs: dict[int, list[dict]] = {}
    for agents in args.agents:
        runs = [
            run_once(agents, args.max_steps, seed)
            for seed in range(args.seed_offset, args.seed_offset + args.seeds)
        ]
        all_runs[agents] = runs
    print_report(all_runs, args.seeds, args.max_steps)


if __name__ == "__main__":
    main()
