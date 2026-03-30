from __future__ import annotations

import math
import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Deque

from shipsim.models import (
    AlarmHistoryEntry,
    FaultRecord,
    FleetCatalog,
    FleetSnapshot,
    ScenarioEventRecord,
    ShipState,
    TelemetrySnapshot,
    WorldRouteConfig,
    utc_now,
)
from shipsim.scenario import load_fleet_catalog
from shipsim.sensors import build_snapshot


FleetListener = Callable[[FleetSnapshot], None]


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _nm_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_nm = 3440.065
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_nm * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _lon_delta(lon1: float, lon2: float) -> float:
    delta = lon2 - lon1
    if delta > 180:
        delta -= 360
    if delta < -180:
        delta += 360
    return delta


def _signed_angle(target: float, current: float) -> float:
    return (target - current + 540) % 360 - 180


def _vector_from_course(course_deg: float, speed_knots: float) -> tuple[float, float]:
    radians = math.radians(course_deg)
    east = math.sin(radians) * speed_knots
    north = math.cos(radians) * speed_knots
    return east, north


def _course_speed_from_vector(east_knots: float, north_knots: float) -> tuple[float, float]:
    speed = math.hypot(east_knots, north_knots)
    if speed < 0.0001:
        return 0.0, 0.0
    course = (math.degrees(math.atan2(east_knots, north_knots)) + 360) % 360
    return course, speed


def _move_position(latitude: float, longitude: float, east_nm: float, north_nm: float) -> tuple[float, float]:
    new_lat = latitude + north_nm / 60
    cos_lat = max(0.2, math.cos(math.radians((latitude + new_lat) / 2)))
    new_lon = longitude + east_nm / (60 * cos_lat)
    while new_lon > 180:
        new_lon -= 360
    while new_lon < -180:
        new_lon += 360
    return new_lat, new_lon


def _to_local_nm(latitude: float, longitude: float, origin_latitude: float) -> tuple[float, float]:
    return longitude * 60 * math.cos(math.radians(origin_latitude)), latitude * 60


def _project_to_segment(
    point_latitude: float,
    point_longitude: float,
    start_latitude: float,
    start_longitude: float,
    end_latitude: float,
    end_longitude: float,
) -> tuple[float, float, float]:
    origin_latitude = (start_latitude + end_latitude + point_latitude) / 3
    px, py = _to_local_nm(point_latitude, point_longitude, origin_latitude)
    ax, ay = _to_local_nm(start_latitude, start_longitude, origin_latitude)
    bx, by = _to_local_nm(end_latitude, end_longitude, origin_latitude)
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    length_sq = abx * abx + aby * aby
    if length_sq <= 1e-9:
        return start_latitude, start_longitude, 0.0
    ratio = _clamp((apx * abx + apy * aby) / length_sq, 0.0, 1.0)
    proj_x = ax + ratio * abx
    proj_y = ay + ratio * aby
    cross = abx * apy - aby * apx
    proj_lat = proj_y / 60
    proj_lon = proj_x / (60 * max(0.2, math.cos(math.radians(origin_latitude))))
    return proj_lat, proj_lon, cross


def _role_defaults(role: str) -> dict[str, float]:
    return {
        "container": {"cargo": 82.0, "ballast": 34.0, "freshwater": 86.0},
        "tanker": {"cargo": 91.0, "ballast": 28.0, "freshwater": 80.0},
        "bulk": {"cargo": 74.0, "ballast": 42.0, "freshwater": 84.0},
    }.get(role, {"cargo": 78.0, "ballast": 38.0, "freshwater": 84.0})


@dataclass
class RuntimeFault:
    code: str
    title: str
    severity: str
    message: str
    effects: dict[str, float | str | bool]
    start_tick: int
    end_tick: int
    started_at: object


@dataclass
class RuntimeEvent:
    code: str
    kind: str
    title: str
    severity: str
    message: str
    start_tick: int
    end_tick: int
    started_at: object


@dataclass
class EnvironmentFrame:
    wave_height_m: float
    wind_speed_knots: float
    wind_direction_deg: float
    current_knots: float
    current_set_deg: float
    visibility_nm: float
    water_temperature_c: float
    air_temperature_c: float


@dataclass
class WorldRouteEngine:
    config: WorldRouteConfig

    def __post_init__(self) -> None:
        self._tick = 0
        self._segment_index = 0
        self._segment_direction = 1
        self._departure_ticks_remaining = 0
        self._active_faults: dict[str, RuntimeFault] = {}
        self._fault_history: Deque[FaultRecord] = deque(maxlen=18)
        self._active_events: dict[str, RuntimeEvent] = {}
        self._event_history: Deque[ScenarioEventRecord] = deque(maxlen=24)
        self._active_alarm_history: dict[str, AlarmHistoryEntry] = {}
        self._resolved_alarm_history: Deque[AlarmHistoryEntry] = deque(maxlen=30)
        self._rng = random.Random(sum(ord(char) for char in self.config.meta.id))
        role_defaults = _role_defaults(self.config.ship.profile.role)
        start = self.config.route.waypoints[0]
        self.state = ShipState(
            timestamp=utc_now(),
            latitude=start.latitude,
            longitude=start.longitude,
            speed_knots=self.config.ship.speed_knots,
            speed_over_ground_knots=self.config.ship.speed_knots,
            heading_deg=self.config.ship.heading_deg,
            course_over_ground_deg=self.config.ship.heading_deg,
            desired_heading_deg=self.config.ship.heading_deg,
            fuel_percent=self.config.ship.fuel_percent,
            engine_rpm=self.config.engine.base_rpm,
            engine_temperature_c=self.config.engine.base_temperature_c,
            depth_m=self.config.ship.base_depth_m,
            wave_height_m=self.config.environment.wave_height_m,
            wind_speed_knots=self.config.environment.wind_speed_knots,
            wind_direction_deg=self.config.environment.wind_direction_deg,
            current_knots=self.config.environment.current_knots,
            current_set_deg=self.config.environment.current_set_deg,
            visibility_nm=self.config.environment.visibility_nm,
            active_waypoint_index=0,
            next_waypoint_index=1 if len(self.config.route.waypoints) > 1 else 0,
            route_direction=1,
            operation_mode="underway",
            mission_status="transit",
            maneuvering_mode=False,
            cargo_utilization_percent=role_defaults["cargo"],
            ballast_percent=role_defaults["ballast"],
            freshwater_percent=role_defaults["freshwater"],
            waste_tank_percent=18.0,
            sludge_tank_percent=14.0,
            tick=0,
        )

    def _next_target_index(self, waypoint_count: int) -> int:
        candidate = self._segment_index + self._segment_direction
        if candidate >= waypoint_count or candidate < 0:
            self._segment_direction *= -1
            candidate = self._segment_index + self._segment_direction
        return candidate

    def _peek_next_target_index(self, waypoint_count: int) -> int:
        candidate = self._segment_index + self._segment_direction
        if candidate >= waypoint_count or candidate < 0:
            candidate = self._segment_index - self._segment_direction
        return max(0, min(waypoint_count - 1, candidate))

    def _fault_probability(self, per_hour: float, dt_seconds: float) -> float:
        sim_hours = min(dt_seconds / 3600, 1.2)
        return 1 - math.exp(-per_hour * sim_hours)

    def _fault_duration_ticks(self) -> int:
        profile = self.config.faults
        return self._rng.randint(profile.min_duration_ticks, profile.max_duration_ticks)

    def _activate_fault(
        self,
        code: str,
        title: str,
        severity: str,
        message: str,
        effects: dict[str, float | str | bool],
        duration_ticks: int | None = None,
    ) -> None:
        if code in self._active_faults:
            return
        duration = duration_ticks if duration_ticks is not None else self._fault_duration_ticks()
        self._active_faults[code] = RuntimeFault(
            code=code,
            title=title,
            severity=severity,
            message=message,
            effects=effects,
            start_tick=self._tick,
            end_tick=self._tick + duration,
            started_at=utc_now(),
        )

    def _expire_faults(self) -> None:
        now = utc_now()
        expired = [code for code, fault in self._active_faults.items() if self._tick >= fault.end_tick]
        for code in expired:
            fault = self._active_faults.pop(code)
            self._fault_history.appendleft(
                FaultRecord(
                    code=fault.code,
                    title=fault.title,
                    severity=fault.severity,
                    status="resolved",
                    message=fault.message,
                    started_at=fault.started_at,
                    expected_end_at=None,
                    ended_at=now,
                    effects=fault.effects,
                )
            )

    def _event_modifiers(self) -> dict[str, float]:
        modifiers = {
            "wave_height_m": 0.0,
            "wind_speed_knots": 0.0,
            "visibility_nm": 0.0,
            "current_knots": 0.0,
            "current_set_shift_deg": 0.0,
            "fuel_penalty_percent": 0.0,
        }
        active_codes: set[str] = set()
        now = utc_now()

        for rule in self.config.events:
            active = rule.start_tick <= self._tick <= rule.end_tick
            if active:
                active_codes.add(rule.code)
                modifiers["wave_height_m"] += rule.wave_delta_m
                modifiers["wind_speed_knots"] += rule.wind_delta_knots
                modifiers["visibility_nm"] += rule.visibility_delta_nm
                modifiers["current_knots"] += rule.current_delta_knots
                modifiers["current_set_shift_deg"] += rule.current_set_shift_deg
                modifiers["fuel_penalty_percent"] += rule.fuel_penalty_percent
                if rule.code not in self._active_events:
                    self._active_events[rule.code] = RuntimeEvent(
                        code=rule.code,
                        kind=rule.kind,
                        title=rule.title,
                        severity=rule.severity,
                        message=rule.message,
                        start_tick=rule.start_tick,
                        end_tick=rule.end_tick,
                        started_at=now,
                    )
                if rule.fault_code:
                    self._activate_fault(
                        code=rule.fault_code,
                        title=rule.fault_code.replace("_", " ").title(),
                        severity="warning",
                        message=rule.message or f"Scenario fault injected: {rule.fault_code}",
                        effects={},
                        duration_ticks=max(4, rule.end_tick - self._tick + 1),
                    )

        for code in list(self._active_events):
            if code in active_codes:
                continue
            event = self._active_events.pop(code)
            self._event_history.appendleft(
                ScenarioEventRecord(
                    code=event.code,
                    kind=event.kind,
                    title=event.title,
                    severity=event.severity,
                    status="resolved",
                    message=event.message,
                    started_at=event.started_at,
                    ended_at=now,
                    start_tick=event.start_tick,
                    end_tick=event.end_tick,
                )
            )

        return modifiers

    def _environment_frame(self, modifiers: dict[str, float]) -> EnvironmentFrame:
        return EnvironmentFrame(
            wave_height_m=max(0.2, self.config.environment.wave_height_m + modifiers["wave_height_m"]),
            wind_speed_knots=max(0.0, self.config.environment.wind_speed_knots + modifiers["wind_speed_knots"]),
            wind_direction_deg=self.config.environment.wind_direction_deg + math.sin(self._tick / 13) * 8,
            current_knots=max(0.0, self.config.environment.current_knots + modifiers["current_knots"]),
            current_set_deg=(self.config.environment.current_set_deg + modifiers["current_set_shift_deg"]) % 360,
            visibility_nm=max(0.5, self.config.environment.visibility_nm + modifiers["visibility_nm"]),
            water_temperature_c=self.config.environment.water_temperature_c + math.sin(self._tick / 20) * 0.9,
            air_temperature_c=self.config.environment.air_temperature_c + math.cos(self._tick / 16) * 1.6,
        )

    def _fault_effects(self, dt_seconds: float) -> dict[str, float]:
        profile = self.config.faults
        if profile.enabled:
            candidates = [
                (
                    "gps_drift",
                    profile.gps_drift_chance_per_hour,
                    "GPS drift",
                    "warning",
                    "GPS pozisyonu drift uretiyor.",
                    {"gps_drift_nm": 0.75},
                ),
                (
                    "radar_fault",
                    profile.radar_fault_chance_per_hour,
                    "Radar fault",
                    "warning",
                    "Radar menzil verisi tutarsiz.",
                    {"radar_range_factor": 0.4},
                ),
                (
                    "engine_overheating",
                    profile.overheating_chance_per_hour,
                    "Engine overheating",
                    "critical",
                    "Ana makine sogutma performansi dustu.",
                    {"temperature_delta_c": 10.0, "drag_penalty": 0.08},
                ),
                (
                    "low_oil_pressure",
                    profile.oil_pressure_fault_chance_per_hour,
                    "Low oil pressure",
                    "critical",
                    "Yaglama basinci duzensiz.",
                    {"oil_pressure_delta_bar": -1.4, "fuel_flow_penalty": 0.06},
                ),
                (
                    "generator_fault",
                    profile.generator_fault_chance_per_hour,
                    "Generator fault",
                    "warning",
                    "Bir jeneratorde yuk dagilimi bozuldu.",
                    {"generator_delta_kw": -120.0, "battery_delta_v": -1.3},
                ),
            ]
            for code, chance_per_hour, title, severity, message, effects in candidates:
                if code in self._active_faults:
                    continue
                if self._rng.random() < self._fault_probability(chance_per_hour, dt_seconds):
                    self._activate_fault(code, title, severity, message, effects)

        self._expire_faults()
        aggregated = {
            "gps_drift_nm": 0.0,
            "radar_range_factor": 1.0,
            "temperature_delta_c": 0.0,
            "drag_penalty": 0.0,
            "oil_pressure_delta_bar": 0.0,
            "fuel_flow_penalty": 0.0,
            "generator_delta_kw": 0.0,
            "battery_delta_v": 0.0,
        }
        for fault in self._active_faults.values():
            for key, value in fault.effects.items():
                if isinstance(value, (int, float)):
                    if key == "radar_range_factor":
                        aggregated[key] *= float(value)
                    else:
                        aggregated[key] += float(value)
        return aggregated

    def _operation_mode(self, distance_to_target: float, next_index: int) -> str:
        port_ops = self.config.ship.port_ops
        endpoint = next_index in (0, len(self.config.route.waypoints) - 1)
        if self.state.berth_ticks_remaining > 0:
            return "berthed"
        if self._departure_ticks_remaining > 0:
            return "departure"
        if endpoint and distance_to_target <= port_ops.harbor_distance_nm:
            return "harbor"
        if endpoint and distance_to_target <= port_ops.approach_distance_nm:
            return "approach"
        return "underway"

    def _desired_speed(self, operation_mode: str, environment: EnvironmentFrame, effects: dict[str, float]) -> float:
        profile = self.config.ship.profile
        port_ops = self.config.ship.port_ops
        service_speed = min(self.config.ship.target_speed_knots, profile.service_speed_knots)
        if operation_mode == "underway":
            desired = service_speed
        elif operation_mode == "approach":
            desired = min(service_speed * 0.72, port_ops.approach_speed_knots)
        elif operation_mode == "harbor":
            desired = min(port_ops.harbor_speed_knots, profile.maneuvering_speed_knots)
        elif operation_mode == "departure":
            desired = min(port_ops.harbor_speed_knots + 1.2, profile.maneuvering_speed_knots + 1.2)
        else:
            desired = 0.0

        bow_component = abs(math.cos(math.radians((environment.wind_direction_deg - self.state.heading_deg) % 360)))
        sea_drag = environment.wave_height_m * (0.18 + profile.drag_coefficient * 4.4)
        wind_drag = environment.wind_speed_knots * 0.01 * bow_component
        desired *= max(0.3, 1 - sea_drag * 0.03 - wind_drag * 0.02 - effects["drag_penalty"])
        return max(0.0, desired)

    def _segment_projection(self, next_index: int) -> tuple[float, float, float]:
        if next_index == self._segment_index:
            return self.state.latitude, self.state.longitude, 0.0
        start = self.config.route.waypoints[self._segment_index]
        end = self.config.route.waypoints[next_index]
        return _project_to_segment(
            self.state.latitude,
            self.state.longitude,
            start.latitude,
            start.longitude,
            end.latitude,
            end.longitude,
        )

    def _guidance_heading(self, next_index: int, target_latitude: float, target_longitude: float) -> tuple[float, float]:
        base_heading = _bearing_deg(self.state.latitude, self.state.longitude, target_latitude, target_longitude)
        _, _, cross = self._segment_projection(next_index)
        signed_cross_track_nm = cross / 60
        correction = _clamp(-signed_cross_track_nm * 12.0, -42.0, 42.0)
        if abs(signed_cross_track_nm) > 2.5:
            correction *= 1.2
        return (base_heading + correction + 360) % 360, signed_cross_track_nm

    def _update_berth_state(self) -> None:
        if self.state.berth_ticks_remaining <= 0:
            return

        self.state.operation_mode = "berthed"
        self.state.mission_status = "cargo_ops"
        self.state.maneuvering_mode = True
        self.state.bow_thruster_active = True
        self.state.speed_knots = 0.0
        self.state.speed_over_ground_knots = 0.0
        self.state.rate_of_turn_deg_min = 0.0
        self.state.rudder_angle_deg = 0.0
        self.state.engine_rpm += (self.config.engine.idle_rpm - self.state.engine_rpm) * 0.4
        endpoint_index = self._segment_index
        handling_rate = self.config.ship.port_ops.cargo_handling_rate_per_tick

        if endpoint_index == len(self.config.route.waypoints) - 1:
            self.state.loading_progress_percent = min(100.0, self.state.loading_progress_percent + handling_rate)
            self.state.cargo_utilization_percent = max(28.0, self.state.cargo_utilization_percent - handling_rate * 0.9)
        else:
            self.state.loading_progress_percent = min(100.0, self.state.loading_progress_percent + handling_rate)
            self.state.cargo_utilization_percent = min(96.0, self.state.cargo_utilization_percent + handling_rate * 0.75)

        self.state.ballast_percent = _clamp(100 - self.state.cargo_utilization_percent * 0.58, 18, 82)
        self.state.freshwater_percent = min(100.0, self.state.freshwater_percent + 1.8)
        self.state.waste_tank_percent = max(4.0, self.state.waste_tank_percent - 2.6)
        self.state.sludge_tank_percent = max(4.0, self.state.sludge_tank_percent - 1.2)
        self.state.fuel_percent = min(100.0, self.state.fuel_percent + 3.8)
        self.state.berth_ticks_remaining -= 1
        if self.state.berth_ticks_remaining <= 0:
            self._departure_ticks_remaining = 6
            self.state.loading_progress_percent = 0.0

    def _arrive_at_waypoint(self, next_index: int) -> None:
        target = self.config.route.waypoints[next_index]
        self.state.latitude = target.latitude
        self.state.longitude = target.longitude
        self._segment_index = next_index
        if next_index in (0, len(self.config.route.waypoints) - 1):
            self.state.berth_ticks_remaining = self.config.ship.port_ops.berth_duration_ticks
            self.state.operation_mode = "berthed"
            self.state.mission_status = "cargo_ops"
            self.state.maneuvering_mode = True
            self.state.bow_thruster_active = True
            self.state.speed_knots = 0.0
            self.state.speed_over_ground_knots = 0.0

    def _update_alarm_history(self, alerts, timestamp) -> list[AlarmHistoryEntry]:
        current_codes = {alert.code for alert in alerts}
        for alert in alerts:
            entry = self._active_alarm_history.get(alert.code)
            if entry is None:
                self._active_alarm_history[alert.code] = AlarmHistoryEntry(
                    code=alert.code,
                    level=alert.level,
                    title=alert.title,
                    status="active",
                    started_at=timestamp,
                    duration_ticks=1,
                    last_value=alert.value,
                    unit=alert.unit,
                )
            else:
                entry.duration_ticks += 1
                entry.last_value = alert.value
                entry.unit = alert.unit

        for code in list(self._active_alarm_history):
            if code in current_codes:
                continue
            entry = self._active_alarm_history.pop(code)
            entry.status = "resolved"
            entry.ended_at = timestamp
            self._resolved_alarm_history.appendleft(entry)

        active_entries = list(self._active_alarm_history.values())
        resolved_entries = list(self._resolved_alarm_history)[:10]
        return active_entries + resolved_entries

    def _fault_records(self) -> list[FaultRecord]:
        active = [
            FaultRecord(
                code=fault.code,
                title=fault.title,
                severity=fault.severity,
                status="active",
                message=fault.message,
                started_at=fault.started_at,
                expected_end_at=None,
                ended_at=None,
                effects=fault.effects,
            )
            for fault in self._active_faults.values()
        ]
        return active + list(self._fault_history)[:8]

    def _event_records(self) -> list[ScenarioEventRecord]:
        active = [
            ScenarioEventRecord(
                code=event.code,
                kind=event.kind,
                title=event.title,
                severity=event.severity,
                status="active",
                message=event.message,
                started_at=event.started_at,
                ended_at=None,
                start_tick=event.start_tick,
                end_tick=event.end_tick,
            )
            for event in self._active_events.values()
        ]
        return active + list(self._event_history)[:8]

    def step(self, dt_seconds: float) -> TelemetrySnapshot:
        self._tick += 1
        modifiers = self._event_modifiers()
        environment = self._environment_frame(modifiers)
        effects = self._fault_effects(dt_seconds)

        waypoints = self.config.route.waypoints
        remaining_seconds = dt_seconds
        while remaining_seconds > 0:
            next_index = self._next_target_index(len(waypoints))
            target = waypoints[next_index]
            distance_to_target = _nm_between(self.state.latitude, self.state.longitude, target.latitude, target.longitude)

            self.state.operation_mode = self._operation_mode(distance_to_target, next_index)
            self.state.mission_status = {
                "underway": "transit",
                "approach": "port_approach",
                "harbor": "maneuvering",
                "departure": "port_departure",
                "berthed": "cargo_ops",
            }[self.state.operation_mode]
            self.state.maneuvering_mode = self.state.operation_mode in {"approach", "harbor", "departure", "berthed"}
            self.state.bow_thruster_active = self.state.operation_mode in {"harbor", "departure", "berthed"}

            sub_dt = min(remaining_seconds, 240 if self.state.maneuvering_mode else 420)
            remaining_seconds -= sub_dt

            if self.state.berth_ticks_remaining > 0:
                self._update_berth_state()
                continue

            desired_heading, cross_track_nm = self._guidance_heading(next_index, target.latitude, target.longitude)
            self.state.desired_heading_deg = desired_heading
            heading_error = _signed_angle(desired_heading, self.state.heading_deg)
            max_rudder = self.config.ship.profile.max_rudder_angle_deg
            rudder_command = _clamp(heading_error * 0.95, -max_rudder, max_rudder)
            rudder_blend = min(1.0, sub_dt * 0.0035)
            self.state.rudder_angle_deg += (rudder_command - self.state.rudder_angle_deg) * rudder_blend

            speed_factor = _clamp(self.state.speed_knots / max(self.config.ship.profile.service_speed_knots, 0.1), 0.18, 1.0)
            max_turn_rate = self.config.ship.profile.max_turn_rate_deg_min * speed_factor
            if self.state.maneuvering_mode:
                max_turn_rate *= 1.2
            target_rot = (self.state.rudder_angle_deg / max(max_rudder, 1)) * max_turn_rate
            self.state.rate_of_turn_deg_min += (target_rot - self.state.rate_of_turn_deg_min) * min(1.0, sub_dt * 0.003)
            self.state.heading_deg = (self.state.heading_deg + self.state.rate_of_turn_deg_min * sub_dt / 60) % 360

            desired_speed = self._desired_speed(self.state.operation_mode, environment, effects)
            if self._departure_ticks_remaining > 0:
                self._departure_ticks_remaining -= 1
            acceleration = 0.14 if self.state.maneuvering_mode else 0.1
            self.state.speed_knots += (desired_speed - self.state.speed_knots) * min(1.0, sub_dt * acceleration / 60)
            self.state.speed_knots = max(0.0, self.state.speed_knots)

            rpm_ratio = _clamp(self.state.speed_knots / max(self.config.ship.profile.service_speed_knots, 0.1), 0.0, 1.0)
            target_rpm = self.config.engine.idle_rpm + rpm_ratio * (self.config.engine.max_rpm - self.config.engine.idle_rpm)
            self.state.engine_rpm += (target_rpm - self.state.engine_rpm) * min(1.0, sub_dt * 0.0028)
            self.state.engine_load_percent = _clamp(18 + rpm_ratio * 78 + environment.wave_height_m * 1.4 + abs(cross_track_nm) * 0.8, 12, 100)

            head_sea_factor = abs(math.cos(math.radians((environment.wind_direction_deg - self.state.heading_deg) % 360)))
            propulsive_efficiency = self.config.engine.gearbox_efficiency * max(0.7, 1 - environment.wave_height_m * 0.03)
            self.state.fuel_flow_lph = self.config.engine.fuel_burn_lph * (
                0.36
                + rpm_ratio * 0.92
                + head_sea_factor * 0.08
                + modifiers["fuel_penalty_percent"] * 0.01
                + effects["fuel_flow_penalty"]
            )

            target_temp = (
                self.config.engine.base_temperature_c
                + rpm_ratio * 18
                + environment.wave_height_m * 1.6
                + head_sea_factor * 1.3
                + effects["temperature_delta_c"]
            )
            self.state.engine_temperature_c += (target_temp - self.state.engine_temperature_c) * min(1.0, sub_dt * 0.002)

            propulsion_east, propulsion_north = _vector_from_course(
                self.state.heading_deg,
                self.state.speed_knots * propulsive_efficiency,
            )
            route_capture_factor = max(0.05, 1 - min(abs(cross_track_nm), 6.0) * 0.14)
            current_east, current_north = _vector_from_course(
                environment.current_set_deg,
                environment.current_knots * self.config.ship.profile.current_factor * route_capture_factor,
            )
            wind_set_deg = (environment.wind_direction_deg + 180) % 360
            wind_drift_knots = environment.wind_speed_knots * self.config.ship.profile.windage_factor * (
                0.3 + environment.wave_height_m * 0.06
            ) * route_capture_factor
            wind_east, wind_north = _vector_from_course(wind_set_deg, wind_drift_knots)
            total_east = propulsion_east + current_east + wind_east
            total_north = propulsion_north + current_north + wind_north
            cog, sog = _course_speed_from_vector(total_east, total_north)

            self.state.course_over_ground_deg = cog
            self.state.speed_over_ground_knots = sog
            self.state.drift_angle_deg = _signed_angle(cog, self.state.heading_deg)

            east_nm = total_east * sub_dt / 3600
            north_nm = total_north * sub_dt / 3600
            moved_latitude, moved_longitude = _move_position(
                self.state.latitude,
                self.state.longitude,
                east_nm,
                north_nm,
            )
            start = waypoints[self._segment_index]
            target = waypoints[next_index]
            projected_lat, projected_lon, _ = _project_to_segment(
                moved_latitude,
                moved_longitude,
                start.latitude,
                start.longitude,
                target.latitude,
                target.longitude,
            )
            self.state.latitude = projected_lat
            self.state.longitude = projected_lon

            fuel_drop = self.state.fuel_flow_lph * sub_dt / 3600 / 1850
            self.state.fuel_percent = max(0.0, self.state.fuel_percent - fuel_drop)
            self.state.freshwater_percent = max(8.0, self.state.freshwater_percent - sub_dt / 3600 * 0.15)
            self.state.waste_tank_percent = min(98.0, self.state.waste_tank_percent + sub_dt / 3600 * 0.16)
            self.state.sludge_tank_percent = min(94.0, self.state.sludge_tank_percent + sub_dt / 3600 * 0.09)
            self.state.ballast_percent = _clamp(100 - self.state.cargo_utilization_percent * 0.58, 18, 82)

            reached_distance = _nm_between(self.state.latitude, self.state.longitude, target.latitude, target.longitude)
            arrival_threshold = 1.2 if self.state.maneuvering_mode else 2.2
            if reached_distance <= arrival_threshold:
                self._arrive_at_waypoint(next_index)

        draft_base = self.config.ship.profile.design_draft_m * (0.76 + self.state.cargo_utilization_percent / 160)
        self.state.roll_deg = math.sin(self._tick / 4.8) * min(8.8, environment.wave_height_m * 2.4)
        self.state.pitch_deg = math.cos(self._tick / 5.1) * min(4.7, environment.wave_height_m * 1.55)
        self.state.heel_deg = self.state.roll_deg * 0.72 + self.state.rudder_angle_deg * 0.04
        self.state.draft_forward_m = draft_base - 0.12 + self.state.pitch_deg * 0.04
        self.state.draft_aft_m = draft_base + 0.22 + self.state.engine_load_percent / 240
        self.state.trim_m = self.state.draft_aft_m - self.state.draft_forward_m

        next_target = waypoints[self._peek_next_target_index(len(waypoints))]
        distance_to_next = _nm_between(self.state.latitude, self.state.longitude, next_target.latitude, next_target.longitude)
        harbor_bias = 0.0
        if next_target in (waypoints[0], waypoints[-1]):
            harbor_bias = max(0.0, 18 - distance_to_next) * 0.7
        self.state.depth_m = max(
            self.state.draft_aft_m + 6,
            self.config.ship.base_depth_m
            + math.sin(self._tick / 7) * environment.wave_height_m * 2.2
            - harbor_bias,
        )

        self.state.timestamp = utc_now()
        self.state.wave_height_m = environment.wave_height_m
        self.state.wind_speed_knots = environment.wind_speed_knots
        self.state.wind_direction_deg = environment.wind_direction_deg
        self.state.current_knots = environment.current_knots
        self.state.current_set_deg = environment.current_set_deg
        self.state.visibility_nm = environment.visibility_nm
        self.state.active_waypoint_index = self._segment_index
        self.state.next_waypoint_index = self._peek_next_target_index(len(waypoints))
        self.state.route_direction = 1 if self.state.next_waypoint_index >= self._segment_index else -1
        self.state.distance_to_next_nm = distance_to_next
        self.state.active_fault_codes = sorted(self._active_faults.keys())
        self.state.active_event_codes = sorted(self._active_events.keys())
        self.state.tick = self._tick

        snapshot = build_snapshot(self.state, self.config)
        snapshot.faults = self._fault_records()
        snapshot.scenario_events = self._event_records()
        snapshot.alarm_history = self._update_alarm_history(snapshot.alerts, snapshot.timestamp)
        return snapshot


class FleetRunner:
    def __init__(self, history_limit: int = 120) -> None:
        self._history: Deque[FleetSnapshot] = deque(maxlen=history_limit)
        self._latest: FleetSnapshot | None = None
        self._catalog: FleetCatalog | None = None
        self._listeners: list[FleetListener] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def add_listener(self, listener: FleetListener) -> None:
        self._listeners.append(listener)

    def start(self, catalog_path: str | Path) -> None:
        with self._lock:
            if self.is_running():
                return

            self._catalog = load_fleet_catalog(catalog_path)
            self._history.clear()
            self._latest = None
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def latest(self) -> FleetSnapshot | None:
        with self._lock:
            return self._latest

    def history(self, limit: int = 20) -> list[FleetSnapshot]:
        with self._lock:
            return list(self._history)[-limit:]

    def routes(self) -> list[dict[str, str]]:
        if self._catalog is None:
            return []
        return [item.meta.model_dump(mode="json") for item in self._catalog.items]

    def status(self) -> dict[str, object]:
        latest = self.latest()
        return {
            "running": self.is_running(),
            "active_routes": len(self._catalog.items) if self._catalog else 0,
            "tick_rate_hz": self._catalog.tick_rate_hz if self._catalog else None,
            "time_scale": self._catalog.time_scale if self._catalog else None,
            "latest_tick": latest.tick if latest else None,
            "last_timestamp": latest.timestamp.isoformat() if latest else None,
            "total_alerts": latest.summary.get("total_alerts", 0) if latest else 0,
            "active_faults": latest.summary.get("active_faults", 0) if latest else 0,
            "active_events": latest.summary.get("active_events", 0) if latest else 0,
        }

    def _run_loop(self) -> None:
        assert self._catalog is not None
        engines = [WorldRouteEngine(item) for item in self._catalog.items]
        tick = 0
        dt = 1 / max(self._catalog.tick_rate_hz, 0.1)
        sim_dt = dt * max(self._catalog.time_scale, 1.0)

        while not self._stop_event.is_set():
            tick += 1
            items = [engine.step(sim_dt) for engine in engines]
            countries = sorted(
                {
                    country
                    for item in items
                    for country in (item.meta.get("origin_country", ""), item.meta.get("destination_country", ""))
                    if country
                }
            )
            payload = FleetSnapshot(
                timestamp=utc_now(),
                tick=tick,
                items=items,
                summary={
                    "active_routes": len(items),
                    "total_alerts": sum(len(item.alerts) for item in items),
                    "routes_with_alerts": sum(1 for item in items if item.alerts),
                    "active_faults": sum(len([fault for fault in item.faults if fault.status == "active"]) for item in items),
                    "active_events": sum(len([event for event in item.scenario_events if event.status == "active"]) for item in items),
                    "countries": countries,
                },
            )

            with self._lock:
                self._latest = payload
                self._history.append(payload)

            for listener in self._listeners:
                listener(payload)

            time.sleep(dt)
