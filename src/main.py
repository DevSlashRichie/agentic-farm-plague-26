from src.model import GameModel


def main() -> None:
    model = GameModel()
    print(f"Starting simulation: {model.width}x{model.height} map, "
          f"{len(model.agents)} agents, max_steps={model.max_steps}")

    while model.running:
        model.step()
        print(f"step {model.steps}: "
              f"rescued={model.victims_rescued}, killed={model.victims_killed}")

    print(f"Simulation ended after {model.steps} steps")


if __name__ == "__main__":
    main()
