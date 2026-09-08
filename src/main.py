from __future__ import annotations

import argparse

from src.log import JsonCollector, _BOLD, _c, terminal_logger
from src.maps import default_map
from src.model import GameModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Flashpoint fire-rescue simulation")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a single big JSON object with all events + final result.",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="Serve a new simulation as JSON on http://0.0.0.0:8000/.",
    )
    args = parser.parse_args()

    if args.server:
        from src.http import serve

        serve()
        return

    map_data = default_map()
    model = GameModel(map_data=map_data)
    if args.json:
        collector = JsonCollector(map_data, model.agents)
        model._log_subscribers.append(collector)
    else:
        model._log_subscribers.append(terminal_logger)
        print(
            _c(
                _BOLD,
                f"Starting simulation: {model.width}x{model.height} map, "
                f"{len(model.agents)} agents, max_steps={model.max_steps}",
            )
        )

    while model.running:
        model.step()

    result = {
        "steps": model.steps,
        "rescued": model.victims_rescued,
        "killed": model.victims_killed,
        "structural_damage": model.structural_damage,
        "end_reason": model._is_end_condition_met() or "running",
    }
    if args.json:
        collector.dump(result)
    else:
        print(
            _c(
                _BOLD,
                f"Simulation ended after {model.steps} steps "
                f"(rescued={model.victims_rescued}, killed={model.victims_killed}, "
                f"damage={model.structural_damage})",
            )
        )


if __name__ == "__main__":
    main()
