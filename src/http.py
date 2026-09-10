from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging
from urllib.parse import parse_qs, urlparse

from src.log import JsonCollector
from src.maps import default_map
from src.model import GameModel


logger = logging.getLogger(__name__)


def parse_seed(raw: str | None) -> float | int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        raise ValueError(f"invalid seed: {raw!r}")


def run_simulation(seed: float | int | None = None) -> dict:
    map_data = default_map()
    model = GameModel(map_data=map_data, seed=seed)
    collector = JsonCollector(map_data, model.agents)
    model._log_subscribers.append(collector)

    while model.running:
        model.step()

    result = {
        "steps": model.steps,
        "rescued": model.victims_rescued,
        "killed": model.victims_killed,
        "structural_damage": model.structural_damage,
        "end_reason": model._is_end_condition_met() or "running",
    }
    return collector.to_dict(result)


class SimulationRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/":
            self._send_json(404, {"error": "not found"})
            return

        query = parse_qs(parsed.query)
        raw_seed = query.get("seed", [None])[0]
        try:
            seed = parse_seed(raw_seed)
        except ValueError:
            self._send_json(400, {"error": f"invalid seed: {raw_seed!r}"})
            return

        try:
            self._send_json(200, run_simulation(seed=seed))
        except Exception:
            logger.exception("Simulation request failed")
            self._send_json(500, {"error": "simulation failed"})

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), format % args)


def serve(host: str = "0.0.0.0", port: int = 8000) -> None:
    logging.basicConfig(level=logging.INFO)
    server = HTTPServer((host, port), SimulationRequestHandler)
    logger.info("Simulation server listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping simulation server")
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Flashpoint simulation server")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    serve(host=args.host, port=args.port)
