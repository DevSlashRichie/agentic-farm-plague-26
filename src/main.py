from __future__ import annotations

from src.log import _BOLD, _c, terminal_logger
from src.model import GameModel


def main() -> None:
    model = GameModel()
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

    print(
        _c(
            _BOLD,
            f"Simulation ended after {model.steps} steps "
            f"(rescued={model.victims_rescued}, killed={model.victims_killed})",
        )
    )


if __name__ == "__main__":
    main()
