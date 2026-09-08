from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import logging

from src.log import JsonCollector
from src.maps import default_map
from src.model import GameModel


logger = logging.getLogger(__name__)


def run_simulation() -> dict:
    map_data = default_map()
    model = GameModel(map_data=map_data)
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
        if self.path != "/":
            self._send_json(404, {"error": "not found"})
            return

        try:
            self._send_json(200, run_simulation())
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
    serve()
