from __future__ import annotations

import json
from pathlib import Path

from shipsim.models import FleetCatalog, ScenarioConfig


def load_scenario(path: str | Path) -> ScenarioConfig:
    scenario_path = Path(path)
    data = json.loads(scenario_path.read_text(encoding="utf-8"))
    return ScenarioConfig.model_validate(data)


def load_fleet_catalog(path: str | Path) -> FleetCatalog:
    catalog_path = Path(path)
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    return FleetCatalog.model_validate(data)
