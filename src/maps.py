from src.domain import MapData


DEFAULT_MAP: MapData = {
    "rows": 6,
    "columns": 8,
    "matrix": [
        ["none", "none", "none", "none", "none", "exit", "none", "none"],
        ["none", "fire", "fire", "unknown", "none", "none", "none", "none"],
        ["exit", "none", "fire", "none", "fire", "none", "none", "none"],
        ["none", "none", "none", "fire", "none", "none", "none", "exit"],
        ["unknown", "none", "none", "none", "none", "fire", "fire", "unknown"],
        ["none", "none", "exit", "none", "none", "fire", "none", "none"],
    ],
    "walls": [
        [[2, 1], [2, 2]],
        [[3, 4], [4, 4]],
        [[4, 7], [5, 7]],
    ],
    "doors": [
        [[1, 3], [1, 4]],
        [[2, 5], [2, 6]],
        [[3, 7], [3, 8]],
        [[3, 2], [3, 3]],
        [[4, 6], [4, 7]],
        [[6, 5], [6, 6]],
        [[6, 7], [6, 8]],
        [[1, 1], [2, 1]],
    ],
}


def default_map() -> MapData:
    return DEFAULT_MAP
