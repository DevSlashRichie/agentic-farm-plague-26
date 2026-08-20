from src.types import MapData


DEFAULT_MAP: MapData = {
    "rows": 6,
    "columns": 8,
    "matrix": [
        ["none", "none", "none", "none", "none", "none", "none", "none"],
        ["none", "fire", "fire", "unknown", "none", "none", "none", "none"],
        ["none", "fire", "fire", "fire", "fire", "none", "none", "none"],
        ["none", "none", "none", "fire", "none", "none", "none", "none"],
        ["unknown", "none", "none", "none", "none", "fire", "fire", "unknown"],
        ["none", "none", "none", "none", "none", "fire", "none", "none"],
    ],
    "doors": [
        {"between": [[1, 3], [1, 4]]},
        {"between": [[2, 5], [2, 6]]},
        {"between": [[3, 7], [3, 8]]},
        {"between": [[3, 2], [3, 3]]},
        {"between": [[3, 4], [4, 4]]},
        {"between": [[4, 6], [4, 7]]},
        {"between": [[6, 5], [6, 6]]},
        {"between": [[6, 7], [6, 8]]},
    ],
    "exits": [
        {"cell": [1, 6], "side": "top"},
        {"cell": [3, 1], "side": "left"},
        {"cell": [4, 8], "side": "right"},
        {"cell": [6, 3], "side": "bottom"},
    ],
}


def default_map() -> MapData:
    return DEFAULT_MAP
