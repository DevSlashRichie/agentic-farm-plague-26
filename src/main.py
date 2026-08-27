from __future__ import annotations

import argparse

from src.log import JsonCollector, _BOLD, _c, terminal_logger
from src.model import GameModel


def main() -> None:
    parser = argparse.ArgumentParser(description="Flashpoint fire-rescue simulation")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a single big JSON object with all events + final result.",
    )
    args = parser.parse_args()

    model = GameModel()
    if args.json:
        collector = JsonCollector()
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
    }
    if args.json:
        collector.dump(result)
    else:
        print(
            _c(
                _BOLD,
                f"Simulation ended after {model.steps} steps "
                f"(rescued={model.victims_rescued}, killed={model.victims_killed})",
            )
        )


if __name__ == "__main__":
    main()
