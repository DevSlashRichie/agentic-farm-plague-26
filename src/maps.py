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
        ((2, 1), (3, 1)),

        ((2, 1), (2, 2)),
        ((3, 1), (3, 2)),
        ((4, 1), (4, 2)),
        ((5, 1), (5, 2)),
        ((6, 1), (6, 2)),

        ((5, 2), (6, 2)),

        ((4, 0), (5, 0)),

        ((1, 3), (2, 3)),
        ((0, 3), (0, 4)),
        ((1, 3), (1, 4)),
        ((2, 3), (2, 4)),
        ((4, 3), (4, 4)),
        ((5, 3), (5, 4)),
        ((6, 3), (6, 4)),
        ((7, 3), (7, 4)),
        ((4, 4), (5, 4)),
        ((6, 4), (7, 4)),
    ],
    "doors": [
        ((2, 0), (3, 0)),
        ((1, 2), (2, 2)),
        ((3, 3), (3, 4)),
        ((4, 5), (5, 5)),
        ((6, 5), (7, 5)),
        ((7, 1), (7, 2)),

        ((5, 3), (6, 3)),

        ((4, 1), (5, 1)),
    ],
}


def default_map() -> MapData:
    return DEFAULT_MAP
