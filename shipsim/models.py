from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShipProfileConfig(BaseModel):
    role: str = "container"
    class_name: str = "Panamax Container"
    length_m: float = 289.0
    beam_m: float = 39.0
    design_draft_m: float = 11.2
    cargo_capacity: float = 5400.0
    cargo_unit: str = "TEU"
    service_speed_knots: float = 18.0
    maneuvering_speed_knots: float = 8.5
    max_rudder_angle_deg: float = 35.0
    max_turn_rate_deg_min: float = 24.0
    turn_response_gain: float = 0.34
    drag_coefficient: float = 0.015
    windage_factor: float = 0.035
    current_factor: float = 1.0


class PortOperationConfig(BaseModel):
    approach_distance_nm: float = 140.0
    harbor_distance_nm: float = 38.0
    approach_speed_knots: float = 11.5
    harbor_speed_knots: float = 7.0
    berth_speed_knots: float = 0.4
    berth_duration_ticks: int = 12
    cargo_handling_rate_per_tick: float = 1.8


class ShipConfig(BaseModel):
    name: str = "Training Vessel"
    latitude: float = 40.9821
    longitude: float = 29.0210
    speed_knots: float = 12.0
    target_speed_knots: float = 12.5
    heading_deg: float = 90.0
    fuel_percent: float = 100.0
    base_depth_m: float = 35.0
    profile: ShipProfileConfig = Field(default_factory=ShipProfileConfig)
    port_ops: PortOperationConfig = Field(default_factory=PortOperationConfig)


class EnvironmentConfig(BaseModel):
    wave_height_m: float = 1.0
    wind_speed_knots: float = 12.0
    wind_direction_deg: float = 205.0
    current_knots: float = 0.8
    current_set_deg: float = 160.0
    visibility_nm: float = 8.0
    water_temperature_c: float = 18.0
    air_temperature_c: float = 21.0


class EngineConfig(BaseModel):
    base_rpm: float = 900.0
    max_rpm: float = 2200.0
    idle_rpm: float = 380.0
    base_temperature_c: float = 68.0
    fuel_burn_lph: float = 120.0
    rated_power_kw: float = 8600.0
    hotel_load_kw: float = 220.0
    gearbox_efficiency: float = 0.96


class SensorConfig(BaseModel):
    noise_scale: float = 1.0
    offline: List[str] = Field(default_factory=list)


class FaultProfileConfig(BaseModel):
    enabled: bool = True
    gps_drift_chance_per_hour: float = 0.02
    radar_fault_chance_per_hour: float = 0.015
    overheating_chance_per_hour: float = 0.03
    oil_pressure_fault_chance_per_hour: float = 0.018
    generator_fault_chance_per_hour: float = 0.012
    min_duration_ticks: int = 8
    max_duration_ticks: int = 28


class EventRuleConfig(BaseModel):
    code: str
    kind: str
    title: str
    start_tick: int
    end_tick: int
    severity: str = "advisory"
    message: str = ""
    wave_delta_m: float = 0.0
    wind_delta_knots: float = 0.0
    visibility_delta_nm: float = 0.0
    current_delta_knots: float = 0.0
    current_set_shift_deg: float = 0.0
    fuel_penalty_percent: float = 0.0
    fault_code: str | None = None


class RoutePoint(BaseModel):
    name: str
    latitude: float
    longitude: float


class PortConfig(BaseModel):
    name: str
    latitude: float
    longitude: float
    kind: str = "port"


class RouteConfig(BaseModel):
    waypoints: List[RoutePoint] = Field(default_factory=list)
    ports: List[PortConfig] = Field(default_factory=list)


class AlarmConfig(BaseModel):
    fuel_warning_percent: float = 35.0
    fuel_critical_percent: float = 15.0
    engine_temp_warning_c: float = 82.0
    engine_temp_critical_c: float = 92.0
    route_deviation_warning_nm: float = 0.35
    route_deviation_critical_nm: float = 0.75
    wave_height_warning_m: float = 2.8
    wave_height_critical_m: float = 4.5
    visibility_warning_nm: float = 3.0
    visibility_critical_nm: float = 1.5
    oil_pressure_warning_bar: float = 3.2
    oil_pressure_critical_bar: float = 2.7
    vibration_warning_mm_s: float = 7.5
    battery_warning_v: float = 24.2
    bilge_warning_percent: float = 45.0


class ScenarioConfig(BaseModel):
    name: str = "normal"
    description: str = "Baseline training route."
    tick_rate_hz: float = 1.0
    ship: ShipConfig = Field(default_factory=ShipConfig)
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    engine: EngineConfig = Field(default_factory=EngineConfig)
    sensors: SensorConfig = Field(default_factory=SensorConfig)
    faults: FaultProfileConfig = Field(default_factory=FaultProfileConfig)
    events: List[EventRuleConfig] = Field(default_factory=list)
    route: RouteConfig = Field(default_factory=RouteConfig)
    alarms: AlarmConfig = Field(default_factory=AlarmConfig)


class RouteMeta(BaseModel):
    id: str
    name: str
    ship_name: str
    origin_port: str
    origin_country: str
    destination_port: str
    destination_country: str
    color: str = "#2470a0"


class WorldRouteConfig(ScenarioConfig):
    meta: RouteMeta


class FleetCatalog(BaseModel):
    tick_rate_hz: float = 1.0
    time_scale: float = 5400.0
    items: List[WorldRouteConfig] = Field(default_factory=list)


class ShipState(BaseModel):
    timestamp: datetime = Field(default_factory=utc_now)
    latitude: float
    longitude: float
    speed_knots: float
    speed_over_ground_knots: float = 0.0
    heading_deg: float
    course_over_ground_deg: float = 0.0
    desired_heading_deg: float = 0.0
    rate_of_turn_deg_min: float = 0.0
    rudder_angle_deg: float = 0.0
    drift_angle_deg: float = 0.0
    fuel_percent: float
    engine_rpm: float
    engine_temperature_c: float
    engine_load_percent: float = 0.0
    fuel_flow_lph: float = 0.0
    depth_m: float
    wave_height_m: float
    wind_speed_knots: float
    wind_direction_deg: float = 0.0
    current_knots: float = 0.0
    current_set_deg: float = 0.0
    visibility_nm: float
    active_waypoint_index: int = 0
    next_waypoint_index: int = 0
    route_direction: int = 1
    operation_mode: str = "underway"
    mission_status: str = "transit"
    maneuvering_mode: bool = False
    bow_thruster_active: bool = False
    berth_ticks_remaining: int = 0
    loading_progress_percent: float = 0.0
    cargo_utilization_percent: float = 0.0
    ballast_percent: float = 0.0
    freshwater_percent: float = 0.0
    waste_tank_percent: float = 0.0
    sludge_tank_percent: float = 0.0
    roll_deg: float = 0.0
    pitch_deg: float = 0.0
    heel_deg: float = 0.0
    draft_forward_m: float = 0.0
    draft_aft_m: float = 0.0
    trim_m: float = 0.0
    distance_to_next_nm: float = 0.0
    active_fault_codes: List[str] = Field(default_factory=list)
    active_event_codes: List[str] = Field(default_factory=list)
    tick: int = 0


class SensorReading(BaseModel):
    name: str
    value: float | str | bool
    unit: str | None = None
    status: str = "OK"


class AlarmEvent(BaseModel):
    code: str
    level: str
    title: str
    message: str
    value: float | str | bool
    unit: str | None = None


class FaultRecord(BaseModel):
    code: str
    title: str
    severity: str
    status: str
    message: str
    started_at: datetime
    expected_end_at: datetime | None = None
    ended_at: datetime | None = None
    effects: Dict[str, float | str | bool] = Field(default_factory=dict)


class ScenarioEventRecord(BaseModel):
    code: str
    kind: str
    title: str
    severity: str
    status: str
    message: str
    started_at: datetime
    ended_at: datetime | None = None
    start_tick: int
    end_tick: int | None = None


class AlarmHistoryEntry(BaseModel):
    code: str
    level: str
    title: str
    status: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ticks: int = 0
    last_value: float | str | bool | None = None
    unit: str | None = None


class TelemetrySnapshot(BaseModel):
    scenario: str
    timestamp: datetime
    tick: int
    ship: Dict[str, float | str | bool]
    navigation: Dict[str, float | str | bool] = Field(default_factory=dict)
    operations: Dict[str, float | str | bool] = Field(default_factory=dict)
    machinery: Dict[str, float | str | bool] = Field(default_factory=dict)
    power: Dict[str, float | str | bool] = Field(default_factory=dict)
    hull: Dict[str, float | str | bool] = Field(default_factory=dict)
    cargo: Dict[str, float | str | bool] = Field(default_factory=dict)
    environment: Dict[str, float | str | bool]
    sensors: Dict[str, SensorReading]
    meta: Dict[str, str] = Field(default_factory=dict)
    route: Dict[str, object] = Field(default_factory=dict)
    alerts: List[AlarmEvent] = Field(default_factory=list)
    faults: List[FaultRecord] = Field(default_factory=list)
    scenario_events: List[ScenarioEventRecord] = Field(default_factory=list)
    alarm_history: List[AlarmHistoryEntry] = Field(default_factory=list)


class FleetSnapshot(BaseModel):
    timestamp: datetime
    tick: int
    items: List[TelemetrySnapshot]
    summary: Dict[str, object] = Field(default_factory=dict)
