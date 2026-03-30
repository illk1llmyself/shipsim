from __future__ import annotations

import math
from dataclasses import dataclass

from shipsim.models import ScenarioConfig, ShipState, utc_now
from shipsim.sensors import build_snapshot


@dataclass
class SimulationEngine:
    scenario: ScenarioConfig

    def __post_init__(self) -> None:
        self._tick = 0
        self.state = ShipState(
            timestamp=utc_now(),
            latitude=self.scenario.ship.latitude,
            longitude=self.scenario.ship.longitude,
            speed_knots=self.scenario.ship.speed_knots,
            heading_deg=self.scenario.ship.heading_deg,
            fuel_percent=self.scenario.ship.fuel_percent,
            engine_rpm=self.scenario.engine.base_rpm,
            engine_temperature_c=self.scenario.engine.base_temperature_c,
            depth_m=self.scenario.ship.base_depth_m,
            wave_height_m=self.scenario.environment.wave_height_m,
            wind_speed_knots=self.scenario.environment.wind_speed_knots,
            visibility_nm=self.scenario.environment.visibility_nm,
            tick=self._tick,
        )

    def step(self, dt_seconds: float):
        self._tick += 1

        sea_drag = self.scenario.environment.wave_height_m * 0.22
        wind_drag = self.scenario.environment.wind_speed_knots * 0.015
        desired_speed = max(0.5, self.scenario.ship.target_speed_knots - sea_drag - wind_drag)

        speed_delta = desired_speed - self.state.speed_knots
        self.state.speed_knots += speed_delta * min(1.0, dt_seconds * 0.25)

        heading_drift = math.sin(self._tick / 8) * self.scenario.environment.current_knots * 0.7
        self.state.heading_deg = (self.scenario.ship.heading_deg + heading_drift) % 360

        distance_nm = self.state.speed_knots * dt_seconds / 3600
        heading_rad = math.radians(self.state.heading_deg)
        delta_lat = math.cos(heading_rad) * distance_nm / 60
        cos_lat = max(0.2, math.cos(math.radians(self.state.latitude)))
        delta_lon = math.sin(heading_rad) * distance_nm / (60 * cos_lat)
        self.state.latitude += delta_lat
        self.state.longitude += delta_lon

        rpm_ratio = max(0.0, min(1.0, self.state.speed_knots / max(self.scenario.ship.target_speed_knots, 0.1)))
        self.state.engine_rpm = self.scenario.engine.base_rpm + (
            self.scenario.engine.max_rpm - self.scenario.engine.base_rpm
        ) * rpm_ratio

        target_temp = (
            self.scenario.engine.base_temperature_c
            + rpm_ratio * 18
            + self.scenario.environment.wave_height_m * 1.5
        )
        self.state.engine_temperature_c += (target_temp - self.state.engine_temperature_c) * min(
            1.0, dt_seconds * 0.2
        )

        fuel_drop = (
            self.scenario.engine.fuel_burn_lph
            * (0.45 + rpm_ratio)
            * dt_seconds
            / 3600
            / 45
        )
        self.state.fuel_percent = max(0.0, self.state.fuel_percent - fuel_drop)

        self.state.depth_m = max(
            5.0,
            self.scenario.ship.base_depth_m + math.sin(self._tick / 6) * self.scenario.environment.wave_height_m * 2.5,
        )
        self.state.timestamp = utc_now()
        self.state.wave_height_m = self.scenario.environment.wave_height_m
        self.state.wind_speed_knots = self.scenario.environment.wind_speed_knots
        self.state.visibility_nm = self.scenario.environment.visibility_nm
        self.state.tick = self._tick

        return build_snapshot(self.state, self.scenario)
