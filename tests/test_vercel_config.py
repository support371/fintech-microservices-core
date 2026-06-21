import json
from pathlib import Path


def test_vercel_config_is_valid_and_routes_services():
    config = json.loads(Path("vercel.json").read_text(encoding="utf-8"))

    destinations = {route["src"]: route["dest"] for route in config["routes"]}
    assert destinations["/api/v1/(.*)"] == "/api/card_service.py"
    assert destinations["/webhook/(.*)"] == "/api/converter_service.py"
    assert destinations["/internal/(.*)"] == "/api/converter_service.py"
    assert destinations["/health"] == "/api/index.py"
