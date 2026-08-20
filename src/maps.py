DEFAULT_MAP = [
    ["none", "none", "door", "none", "none", "exit", "none", "none"],
    ["none", "fire", "fire", "unknown", "door", "none", "none", "none"],
    ["exit", "door", "fire", "door", "fire", "none", "door", "none"],
    ["none", "none", "none", "fire", "none", "door", "none", "exit"],
    ["unknown", "none", "none", "none", "none", "fire", "fire", "unknown"],
    ["none", "none", "exit", "none", "door", "fire", "door", "none"],
]


def default_map() -> list[list[str]]:
    return DEFAULT_MAP
