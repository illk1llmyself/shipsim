from __future__ import annotations

import math
import random

from shipsim.models import AlarmEvent, RoutePoint, ScenarioConfig, SensorReading, ShipState, TelemetrySnapshot


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _jitter(value: float, amount: float, enabled: bool = True) -> float:
    if not enabled:
        return value
    return value + random.uniform(-amount, amount)


def _to_local_nm(latitude: float, longitude: float, origin_latitude: float):
    x = longitude * 60 * math.cos(math.radians(origin_latitude))
    y = latitude * 60
    return x, y


def _distance_point_to_segment_nm(
    point_latitude: float,
    point_longitude: float,
    start: RoutePoint,
    end: RoutePoint,
    origin_latitude: float,
) -> float:
    px, py = _to_local_nm(point_latitude, point_longitude, origin_latitude)
    ax, ay = _to_local_nm(start.latitude, start.longitude, origin_latitude)
    bx, by = _to_local_nm(end.latitude, end.longitude, origin_latitude)
    abx = bx - ax
    aby = by - ay
    apx = px - ax
    apy = py - ay
    length_sq = abx * abx + aby * aby
    if length_sq == 0:
        return math.hypot(apx, apy)
    ratio = max(0.0, min(1.0, (apx * abx + apy * aby) / length_sq))
    closest_x = ax + ratio * abx
    closest_y = ay + ratio * aby
    return math.hypot(px - closest_x, py - closest_y)


def _nm_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_nm = 3440.065
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_nm * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _route_deviation_nm(state: ShipState, scenario: ScenarioConfig) -> float:
    waypoints = scenario.route.waypoints
    if not waypoints:
        return 0.0
    if len(waypoints) == 1:
        only = waypoints[0]
        return _distance_point_to_segment_nm(state.latitude, state.longitude, only, only, state.latitude)

    origin_latitude = sum(point.latitude for point in waypoints) / len(waypoints)
    distances = [
        _distance_point_to_segment_nm(state.latitude, state.longitude, start, end, origin_latitude)
        for start, end in zip(waypoints, waypoints[1:])
    ]
    return min(distances, default=0.0)


def _route_remaining_nm(state: ShipState, scenario: ScenarioConfig) -> float:
    waypoints = scenario.route.waypoints
    if not waypoints:
        return 0.0
    next_index = int(_clamp(state.next_waypoint_index, 0, len(waypoints) - 1))
    current_target = waypoints[next_index]
    remaining = _nm_between(state.latitude, state.longitude, current_target.latitude, current_target.longitude)
    step = 1 if state.route_direction >= 0 else -1
    cursor = next_index
    while 0 <= cursor + step < len(waypoints):
        start = waypoints[cursor]
        end = waypoints[cursor + step]
        remaining += _nm_between(start.latitude, start.longitude, end.latitude, end.longitude)
        cursor += step
    return remaining


def _route_target_name(state: ShipState, scenario: ScenarioConfig) -> str:
    waypoints = scenario.route.waypoints
    if not waypoints:
        return "No route"
    next_index = int(_clamp(state.next_waypoint_index, 0, len(waypoints) - 1))
    return waypoints[next_index].name


def _sensor_status(sensor_name: str, offline: set[str], warning: bool = False) -> str:
    if sensor_name in offline:
        return "OFFLINE"
    if warning:
        return "WARN"
    return "OK"


def _build_navigation(state: ShipState, scenario: ScenarioConfig, deviation_nm: float) -> dict[str, float | str | bool]:
    remaining_nm = _route_remaining_nm(state, scenario)
    eta_hours = remaining_nm / max(state.speed_over_ground_knots, 0.1)
    turn_rate = abs(state.rate_of_turn_deg_min)
    turn_radius_nm = 0.0
    if turn_rate > 0.01 and state.speed_over_ground_knots > 0.1:
        turn_radius_nm = (state.speed_over_ground_knots / 60) / math.radians(turn_rate)
    gps_satellites = int(_clamp(12 - state.wave_height_m * 0.4 - (1 if "gps_drift" in state.active_fault_codes else 0), 7, 14))
    gps_hdop = _clamp(0.8 + state.wave_height_m * 0.1 + (0.8 if "gps_drift" in state.active_fault_codes else 0), 0.7, 3.5)
    return {
        "speed_over_ground_knots": round(state.speed_over_ground_knots, 2),
        "speed_through_water_knots": round(state.speed_knots, 2),
        "course_over_ground_deg": round(state.course_over_ground_deg, 2),
        "heading_deg": round(state.heading_deg, 2),
        "desired_heading_deg": round(state.desired_heading_deg, 2),
        "drift_angle_deg": round(state.drift_angle_deg, 2),
        "rate_of_turn_deg_min": round(state.rate_of_turn_deg_min, 2),
        "rudder_angle_deg": round(state.rudder_angle_deg, 2),
        "turn_radius_nm": round(turn_radius_nm, 3),
        "eta_hours": round(eta_hours, 2),
        "remaining_distance_nm": round(remaining_nm, 2),
        "next_waypoint_name": _route_target_name(state, scenario),
        "distance_to_next_nm": round(state.distance_to_next_nm, 2),
        "route_deviation_nm": round(deviation_nm, 3),
        "gps_satellites": gps_satellites,
        "gps_hdop": round(gps_hdop, 2),
        "route_direction": "forward" if state.route_direction >= 0 else "return",
        "nav_status": state.operation_mode.upper(),
    }


def _build_operations(state: ShipState, scenario: ScenarioConfig) -> dict[str, float | str | bool]:
    profile = scenario.ship.profile
    return {
        "operation_mode": state.operation_mode,
        "mission_status": state.mission_status,
        "ship_role": profile.role,
        "ship_class": profile.class_name,
        "maneuvering_mode": state.maneuvering_mode,
        "bow_thruster_active": state.bow_thruster_active,
        "berth_ticks_remaining": state.berth_ticks_remaining,
        "loading_progress_percent": round(state.loading_progress_percent, 1),
        "cargo_capacity": round(profile.cargo_capacity, 1),
        "cargo_unit": profile.cargo_unit,
        "length_m": round(profile.length_m, 1),
        "beam_m": round(profile.beam_m, 1),
    }


def _build_machinery(state: ShipState, scenario: ScenarioConfig) -> dict[str, float | str | bool]:
    fault_penalty = 1.4 if "low_oil_pressure" in state.active_fault_codes else 0.0
    oil_pressure = _clamp(5.8 - (state.engine_temperature_c - scenario.engine.base_temperature_c) * 0.04 - fault_penalty, 1.9, 6.4)
    load_ratio = _clamp(state.engine_load_percent / 100, 0.0, 1.0)
    shaft_power = scenario.engine.rated_power_kw * load_ratio * scenario.engine.gearbox_efficiency
    vibration = 1.8 + state.wave_height_m * 0.8 + load_ratio * 2.8 + (2.4 if "engine_overheating" in state.active_fault_codes else 0.0)
    return {
        "engine_load_percent": round(state.engine_load_percent, 1),
        "shaft_power_kw": round(shaft_power, 0),
        "fuel_flow_lph": round(state.fuel_flow_lph, 1),
        "lube_oil_pressure_bar": round(oil_pressure, 2),
        "lube_oil_temp_c": round(state.engine_temperature_c - 5.6, 1),
        "coolant_temp_c": round(state.engine_temperature_c, 1),
        "exhaust_temp_c": round(240 + load_ratio * 175 + state.wave_height_m * 6, 1),
        "turbo_rpm": round(8500 + load_ratio * 25000, 0),
        "vibration_mm_s": round(vibration, 2),
        "main_engine_status": "DEGRADED" if "engine_overheating" in state.active_fault_codes else "ONLINE",
        "propulsion_mode": "STOP" if state.speed_knots < 0.1 else "AHEAD",
    }


def _build_power(state: ShipState, scenario: ScenarioConfig) -> dict[str, float | str | bool]:
    hotel_load = scenario.engine.hotel_load_kw + state.wave_height_m * 14 + (36 if state.maneuvering_mode else 0)
    generator_penalty = 120 if "generator_fault" in state.active_fault_codes else 0
    generator_load = hotel_load + 110 + state.engine_load_percent * 2.1 - generator_penalty
    battery_voltage = _clamp(27.6 - generator_penalty * 0.01 - (0.9 if "generator_fault" in state.active_fault_codes else 0), 23.2, 28.1)
    return {
        "generator_load_kw": round(generator_load, 1),
        "hotel_load_kw": round(hotel_load, 1),
        "battery_voltage_v": round(battery_voltage, 2),
        "shore_power_connected": state.operation_mode == "berthed",
        "emergency_bus_status": "ACTIVE" if "generator_fault" in state.active_fault_codes else "STANDBY",
        "bow_thruster_ready": state.bow_thruster_active,
    }


def _build_hull(state: ShipState) -> dict[str, float | str | bool]:
    bilge = _clamp(4.0 + state.wave_height_m * 2.6 + max(0.0, abs(state.roll_deg) - 4.0) * 2.3, 0.0, 100.0)
    return {
        "draft_forward_m": round(state.draft_forward_m, 2),
        "draft_aft_m": round(state.draft_aft_m, 2),
        "trim_m": round(state.trim_m, 2),
        "roll_deg": round(state.roll_deg, 2),
        "pitch_deg": round(state.pitch_deg, 2),
        "heel_deg": round(state.heel_deg, 2),
        "ballast_percent": round(state.ballast_percent, 1),
        "bilge_level_percent": round(bilge, 1),
    }


def _build_cargo(state: ShipState, scenario: ScenarioConfig) -> dict[str, float | str | bool]:
    profile = scenario.ship.profile
    cargo_amount = profile.cargo_capacity * state.cargo_utilization_percent / 100
    cargo_mode = {
        "container": "CONTAINER STACK",
        "tanker": "LIQUID BULK",
        "bulk": "DRY BULK",
    }.get(profile.role, "GENERAL CARGO")
    return {
        "cargo_utilization_percent": round(state.cargo_utilization_percent, 1),
        "cargo_amount": round(cargo_amount, 1),
        "cargo_unit": profile.cargo_unit,
        "reefer_containers_online": int(cargo_amount * 0.04) if profile.role == "container" else 0,
        "freshwater_percent": round(state.freshwater_percent, 1),
        "waste_tank_percent": round(state.waste_tank_percent, 1),
        "sludge_tank_percent": round(state.sludge_tank_percent, 1),
        "cargo_mode": cargo_mode,
    }


def _build_environment(state: ShipState, scenario: ScenarioConfig) -> dict[str, float | str | bool]:
    apparent_wind = state.wind_speed_knots + state.speed_over_ground_knots * 0.34
    air_temperature = scenario.environment.air_temperature_c + math.sin(state.tick / 14) * 1.8
    humidity = _clamp(64 + state.wave_height_m * 5.5 + max(0, 8 - state.visibility_nm) * 2.4, 45, 98)
    pressure = 1014 - state.wave_height_m * 4.2 + math.cos(state.tick / 12) * 4.6
    sea_state = int(_clamp(round(state.wind_speed_knots / 4.7 + state.wave_height_m * 0.45), 1, 12))
    return {
        "wave_height_m": round(state.wave_height_m, 2),
        "wind_speed_knots": round(state.wind_speed_knots, 2),
        "wind_direction_deg": round(state.wind_direction_deg, 1),
        "apparent_wind_knots": round(apparent_wind, 2),
        "visibility_nm": round(state.visibility_nm, 2),
        "depth_m": round(state.depth_m, 2),
        "water_temperature_c": round(scenario.environment.water_temperature_c + math.sin(state.tick / 18) * 0.8, 1),
        "air_temperature_c": round(air_temperature, 1),
        "humidity_percent": round(humidity, 1),
        "barometric_pressure_hpa": round(pressure, 1),
        "current_knots": round(state.current_knots, 2),
        "current_set_deg": round(state.current_set_deg, 1),
        "sea_state_beaufort": sea_state,
    }


def _build_alerts(
    state: ShipState,
    scenario: ScenarioConfig,
    deviation_nm: float,
    navigation: dict[str, float | str | bool],
    machinery: dict[str, float | str | bool],
    power: dict[str, float | str | bool],
    hull: dict[str, float | str | bool],
) -> list[AlarmEvent]:
    alerts: list[AlarmEvent] = []
    thresholds = scenario.alarms

    if state.fuel_percent <= thresholds.fuel_critical_percent:
        alerts.append(AlarmEvent(code="fuel_critical", level="critical", title="Kritik yakit", message="Yakit seviyesi kritik esigin altinda.", value=round(state.fuel_percent, 2), unit="percent"))
    elif state.fuel_percent <= thresholds.fuel_warning_percent:
        alerts.append(AlarmEvent(code="fuel_warning", level="warning", title="Dusuk yakit", message="Yakit seviyesi izleme gerektiriyor.", value=round(state.fuel_percent, 2), unit="percent"))

    if state.engine_temperature_c >= thresholds.engine_temp_critical_c:
        alerts.append(AlarmEvent(code="engine_temp_critical", level="critical", title="Motor fazla isinmis", message="Ana makine sicakligi kritik seviyede.", value=round(state.engine_temperature_c, 2), unit="C"))
    elif state.engine_temperature_c >= thresholds.engine_temp_warning_c:
        alerts.append(AlarmEvent(code="engine_temp_warning", level="warning", title="Motor sicak", message="Motor sicakligi yukseliyor.", value=round(state.engine_temperature_c, 2), unit="C"))

    if deviation_nm >= thresholds.route_deviation_critical_nm:
        alerts.append(AlarmEvent(code="route_critical", level="critical", title="Rota disina cikildi", message="Planli hattan ciddi sapma var.", value=round(deviation_nm, 3), unit="nm"))
    elif deviation_nm >= thresholds.route_deviation_warning_nm:
        alerts.append(AlarmEvent(code="route_warning", level="warning", title="Rota sapmasi", message="Gemi planli hattan uzaklasiyor.", value=round(deviation_nm, 3), unit="nm"))

    if state.wave_height_m >= thresholds.wave_height_critical_m or state.visibility_nm <= thresholds.visibility_critical_nm:
        alerts.append(AlarmEvent(code="sea_critical", level="critical", title="Tehlikeli deniz kosulu", message="Dalga veya gorus kritik seviyede.", value=f"{round(state.wave_height_m, 1)}m / {round(state.visibility_nm, 1)}nm"))
    elif state.wave_height_m >= thresholds.wave_height_warning_m or state.visibility_nm <= thresholds.visibility_warning_nm:
        alerts.append(AlarmEvent(code="sea_warning", level="warning", title="Sert deniz kosulu", message="Deniz ve hava kosullari dikkat gerektiriyor.", value=f"{round(state.wave_height_m, 1)}m / {round(state.visibility_nm, 1)}nm"))

    if float(machinery["lube_oil_pressure_bar"]) < thresholds.oil_pressure_critical_bar:
        alerts.append(AlarmEvent(code="oil_pressure_critical", level="critical", title="Yag basinci kritik", message="Ana makine yaglama basinci tehlikeli seviyede.", value=machinery["lube_oil_pressure_bar"], unit="bar"))
    elif float(machinery["lube_oil_pressure_bar"]) < thresholds.oil_pressure_warning_bar:
        alerts.append(AlarmEvent(code="oil_pressure_warning", level="warning", title="Yag basinci dusuyor", message="Yag basinci dikkat gerektiriyor.", value=machinery["lube_oil_pressure_bar"], unit="bar"))

    if float(machinery["vibration_mm_s"]) > thresholds.vibration_warning_mm_s:
        alerts.append(AlarmEvent(code="vibration_warning", level="warning", title="Titreşim artisi", message="Sevk hattinda yuksek titresim var.", value=machinery["vibration_mm_s"], unit="mm/s"))

    if float(hull["bilge_level_percent"]) > thresholds.bilge_warning_percent:
        alerts.append(AlarmEvent(code="bilge_warning", level="warning", title="Sintine seviyesi yuksek", message="Sintine seviyesi normalin ustunde.", value=hull["bilge_level_percent"], unit="percent"))

    if float(power["battery_voltage_v"]) < thresholds.battery_warning_v:
        alerts.append(AlarmEvent(code="battery_warning", level="warning", title="Bus gerilimi dusuk", message="Batarya bus gerilimi nominal altinda.", value=power["battery_voltage_v"], unit="V"))

    for fault_code in state.active_fault_codes:
        alerts.append(AlarmEvent(code=fault_code, level="warning", title=fault_code.replace("_", " ").title(), message="Aktif ekipman arizasi simule ediliyor.", value="ACTIVE"))

    for event_code in state.active_event_codes:
        alerts.append(AlarmEvent(code=event_code, level="advisory", title=event_code.replace("_", " ").title(), message="Senaryo tetikleyicisi aktif.", value="SCENARIO"))

    return alerts


def build_snapshot(state: ShipState, scenario: ScenarioConfig) -> TelemetrySnapshot:
    noise_scale = scenario.sensors.noise_scale
    offline = set(scenario.sensors.offline)
    deviation_nm = _route_deviation_nm(state, scenario)
    navigation = _build_navigation(state, scenario, deviation_nm)
    operations = _build_operations(state, scenario)
    machinery = _build_machinery(state, scenario)
    power = _build_power(state, scenario)
    hull = _build_hull(state)
    cargo = _build_cargo(state, scenario)
    environment = _build_environment(state, scenario)
    alerts = _build_alerts(state, scenario, deviation_nm, navigation, machinery, power, hull)

    gps_drift = 0.012 if "gps_drift" in state.active_fault_codes else 0.0003
    radar_warning = "radar_fault" in state.active_fault_codes
    gps_warning = "gps_drift" in state.active_fault_codes
    shaft_torque_knm = 0.0
    if state.engine_rpm > 1:
        shaft_torque_knm = float(machinery["shaft_power_kw"]) * 9.55 / max(state.engine_rpm, 1)
    propeller_slip_percent = _clamp(
        max(0.0, float(navigation["speed_through_water_knots"]) - float(navigation["speed_over_ground_knots"])) * 8.5,
        0.0,
        36.0,
    )
    depth_under_keel = max(0.0, state.depth_m - state.draft_aft_m)
    reefer_power_kw = 0.0
    if scenario.ship.profile.role == "container":
        reefer_power_kw = float(cargo["reefer_containers_online"]) * 4.8
    bow_thruster_load_kw = 95.0 + state.wave_height_m * 18 if state.bow_thruster_active else 0.0
    weather_humidity_warn = float(environment["humidity_percent"]) > 92
    wind_warn = float(environment["apparent_wind_knots"]) > 28
    draft_warn = depth_under_keel < 8.0
    load_ratio = _clamp(float(machinery["engine_load_percent"]) / 100, 0.0, 1.0)
    main_bearing_temp_c = state.engine_temperature_c - 4.5 + load_ratio * 7.2
    thrust_bearing_temp_c = state.engine_temperature_c - 7.0 + load_ratio * 5.8
    jacket_water_pressure_bar = _clamp(3.9 + load_ratio * 0.7 - state.wave_height_m * 0.04, 2.6, 5.2)
    jacket_water_inlet_c = float(machinery["coolant_temp_c"]) - 7.6
    scav_air_pressure_bar = _clamp(1.15 + load_ratio * 1.45, 1.0, 3.2)
    scav_air_temp_c = 38 + load_ratio * 52 + state.wave_height_m * 1.2
    governor_output_percent = _clamp(22 + load_ratio * 73, 18, 100)
    gearbox_oil_temp_c = 46 + load_ratio * 24 + state.wave_height_m * 0.8
    gearbox_oil_pressure_bar = _clamp(5.6 - load_ratio * 0.55, 4.1, 6.2)
    stern_tube_temp_c = 33 + state.speed_over_ground_knots * 0.9 + state.wave_height_m * 0.7
    engine_room_temp_c = float(environment["air_temperature_c"]) + 8.5 + load_ratio * 5.0
    engine_room_humidity_percent = _clamp(float(environment["humidity_percent"]) - 12 + state.wave_height_m * 1.8, 36, 88)
    aux_blower_load_kw = 18 + load_ratio * 54
    hull_stress_index = _clamp(abs(state.roll_deg) * 7.5 + abs(state.pitch_deg) * 11 + state.wave_height_m * 8.2, 0, 100)
    hull_bending_percent = _clamp(state.cargo_utilization_percent * 0.58 + abs(state.trim_m) * 7 + state.wave_height_m * 3.2, 18, 98)
    torsion_index = _clamp(abs(state.heel_deg) * 10.5 + abs(state.rudder_angle_deg) * 0.75 + state.wave_height_m * 4.0, 0, 100)
    forepeak_tank_percent = _clamp(state.ballast_percent * 0.42 + state.pitch_deg * 1.6 + 18, 5, 95)
    aftpeak_tank_percent = _clamp(state.ballast_percent * 0.46 - state.pitch_deg * 1.6 + 16, 5, 95)
    freeboard_mid_m = max(1.8, scenario.ship.profile.design_draft_m + 7.5 - ((state.draft_forward_m + state.draft_aft_m) / 2))
    watertight_doors_secured = state.operation_mode not in {"berthed", "harbor"}
    leak_watch_warning = float(hull["bilge_level_percent"]) > 38

    sensors = {
        "gps": SensorReading(
            name="gps",
            value=f"{_jitter(state.latitude, gps_drift * noise_scale, 'gps' not in offline):.5f}, {_jitter(state.longitude, gps_drift * noise_scale, 'gps' not in offline):.5f}",
            status=_sensor_status("gps", offline, gps_warning),
        ),
        "gps_position": SensorReading(
            name="gps_position",
            value=f"{_jitter(state.latitude, gps_drift * noise_scale, 'gps_position' not in offline):.5f}, {_jitter(state.longitude, gps_drift * noise_scale, 'gps_position' not in offline):.5f}",
            status=_sensor_status("gps_position", offline, gps_warning),
        ),
        "speed": SensorReading(name="speed", value=round(_jitter(float(navigation["speed_over_ground_knots"]), 0.16 * noise_scale, "speed" not in offline), 2), unit="knots", status=_sensor_status("speed", offline)),
        "gps_satellites": SensorReading(name="gps_satellites", value=int(navigation["gps_satellites"]), unit="sat", status=_sensor_status("gps_satellites", offline, int(navigation["gps_satellites"]) < 9)),
        "gps_hdop": SensorReading(name="gps_hdop", value=round(_jitter(float(navigation["gps_hdop"]), 0.05 * noise_scale, "gps_hdop" not in offline), 2), status=_sensor_status("gps_hdop", offline, float(navigation["gps_hdop"]) > 1.8)),
        "heading": SensorReading(name="heading", value=round(_jitter(float(navigation["heading_deg"]), 0.8 * noise_scale, "heading" not in offline), 2), unit="deg", status=_sensor_status("heading", offline)),
        "gyro_heading": SensorReading(name="gyro_heading", value=round(_jitter(float(navigation["heading_deg"]), 0.5 * noise_scale, "gyro_heading" not in offline), 2), unit="deg", status=_sensor_status("gyro_heading", offline)),
        "magnetic_compass": SensorReading(name="magnetic_compass", value=round(_jitter(float(navigation["heading_deg"]) - 2.6, 1.2 * noise_scale, "magnetic_compass" not in offline), 2), unit="deg", status=_sensor_status("magnetic_compass", offline)),
        "course_over_ground": SensorReading(name="course_over_ground", value=round(_jitter(float(navigation["course_over_ground_deg"]), 0.6 * noise_scale, "course_over_ground" not in offline), 2), unit="deg", status=_sensor_status("course_over_ground", offline)),
        "speed_over_ground": SensorReading(name="speed_over_ground", value=round(_jitter(float(navigation["speed_over_ground_knots"]), 0.12 * noise_scale, "speed_over_ground" not in offline), 2), unit="knots", status=_sensor_status("speed_over_ground", offline)),
        "rate_of_turn": SensorReading(name="rate_of_turn", value=round(_jitter(float(navigation["rate_of_turn_deg_min"]), 0.1 * noise_scale, "rate_of_turn" not in offline), 2), unit="deg/min", status=_sensor_status("rate_of_turn", offline, abs(float(navigation["rate_of_turn_deg_min"])) > 14)),
        "speed_log": SensorReading(name="speed_log", value=round(_jitter(float(navigation["speed_through_water_knots"]), 0.14 * noise_scale, "speed_log" not in offline), 2), unit="knots", status=_sensor_status("speed_log", offline)),
        "track_error": SensorReading(name="track_error", value=round(_jitter(float(navigation["route_deviation_nm"]), 0.01 * noise_scale, "track_error" not in offline), 3), unit="nm", status=_sensor_status("track_error", offline, float(navigation["route_deviation_nm"]) > 0.08)),
        "ais_transponder": SensorReading(name="ais_transponder", value="TX/RX ACTIVE", status=_sensor_status("ais_transponder", offline)),
        "radar_range": SensorReading(name="radar_range", value=round(_jitter(float(environment["visibility_nm"]) * 3.2 * (0.45 if radar_warning else 1.0), 0.6, "radar_range" not in offline), 1), unit="nm", status=_sensor_status("radar_range", offline, radar_warning)),
        "doppler_log": SensorReading(name="doppler_log", value=round(_jitter(float(navigation["speed_through_water_knots"]), 0.09 * noise_scale, "doppler_log" not in offline), 2), unit="knots", status=_sensor_status("doppler_log", offline)),
        "depth_under_keel": SensorReading(name="depth_under_keel", value=round(_jitter(depth_under_keel, 0.18 * noise_scale, "depth_under_keel" not in offline), 2), unit="m", status=_sensor_status("depth_under_keel", offline, draft_warn)),
        "anemometer": SensorReading(name="anemometer", value=round(_jitter(float(environment["apparent_wind_knots"]), 0.7 * noise_scale, "anemometer" not in offline), 1), unit="knots", status=_sensor_status("anemometer", offline)),
        "wind_direction_true": SensorReading(name="wind_direction_true", value=round(_jitter(float(environment["wind_direction_deg"]), 1.8 * noise_scale, "wind_direction_true" not in offline), 1), unit="deg", status=_sensor_status("wind_direction_true", offline)),
        "barometer": SensorReading(name="barometer", value=round(_jitter(float(environment["barometric_pressure_hpa"]), 1.0 * noise_scale, "barometer" not in offline), 1), unit="hPa", status=_sensor_status("barometer", offline, float(environment["barometric_pressure_hpa"]) < 1002)),
        "humidity_sensor": SensorReading(name="humidity_sensor", value=round(_jitter(float(environment["humidity_percent"]), 1.4 * noise_scale, "humidity_sensor" not in offline), 1), unit="percent", status=_sensor_status("humidity_sensor", offline, weather_humidity_warn)),
        "air_temperature": SensorReading(name="air_temperature", value=round(_jitter(float(environment["air_temperature_c"]), 0.4 * noise_scale, "air_temperature" not in offline), 1), unit="C", status=_sensor_status("air_temperature", offline)),
        "water_temperature": SensorReading(name="water_temperature", value=round(_jitter(float(environment["water_temperature_c"]), 0.3 * noise_scale, "water_temperature" not in offline), 1), unit="C", status=_sensor_status("water_temperature", offline)),
        "current_meter": SensorReading(name="current_meter", value=round(_jitter(float(environment["current_knots"]), 0.06 * noise_scale, "current_meter" not in offline), 2), unit="knots", status=_sensor_status("current_meter", offline)),
        "current_set": SensorReading(name="current_set", value=round(_jitter(float(environment["current_set_deg"]), 1.5 * noise_scale, "current_set" not in offline), 1), unit="deg", status=_sensor_status("current_set", offline)),
        "visibility_sensor": SensorReading(name="visibility_sensor", value=round(_jitter(float(environment["visibility_nm"]), 0.15 * noise_scale, "visibility_sensor" not in offline), 2), unit="nm", status=_sensor_status("visibility_sensor", offline, float(environment["visibility_nm"]) < 3.0)),
        "sea_state": SensorReading(name="sea_state", value=int(environment["sea_state_beaufort"]), unit="bft", status=_sensor_status("sea_state", offline, float(environment["sea_state_beaufort"]) >= 6)),
        "echo_sounder": SensorReading(name="echo_sounder", value=round(_jitter(state.depth_m, 0.3 * noise_scale, "echo_sounder" not in offline), 2), unit="m", status=_sensor_status("echo_sounder", offline, state.depth_m < state.draft_aft_m + 7)),
        "shaft_power": SensorReading(name="shaft_power", value=round(_jitter(float(machinery["shaft_power_kw"]), 20 * noise_scale, "shaft_power" not in offline), 0), unit="kW", status=_sensor_status("shaft_power", offline)),
        "shaft_torque": SensorReading(name="shaft_torque", value=round(_jitter(shaft_torque_knm, 0.4 * noise_scale, "shaft_torque" not in offline), 2), unit="kNm", status=_sensor_status("shaft_torque", offline)),
        "propeller_slip": SensorReading(name="propeller_slip", value=round(_jitter(propeller_slip_percent, 0.6 * noise_scale, "propeller_slip" not in offline), 1), unit="percent", status=_sensor_status("propeller_slip", offline, propeller_slip_percent > 12)),
        "engine_load": SensorReading(name="engine_load", value=round(_jitter(float(machinery["engine_load_percent"]), 0.6 * noise_scale, "engine_load" not in offline), 1), unit="percent", status=_sensor_status("engine_load", offline, float(machinery["engine_load_percent"]) > 88)),
        "engine_temperature": SensorReading(name="engine_temperature", value=round(_jitter(state.engine_temperature_c, 0.6 * noise_scale, "engine_temperature" not in offline), 2), unit="C", status=_sensor_status("engine_temperature", offline, state.engine_temperature_c >= scenario.alarms.engine_temp_warning_c)),
        "main_bearing_temp": SensorReading(name="main_bearing_temp", value=round(_jitter(main_bearing_temp_c, 0.5 * noise_scale, "main_bearing_temp" not in offline), 1), unit="C", status=_sensor_status("main_bearing_temp", offline, main_bearing_temp_c > 86)),
        "thrust_bearing_temp": SensorReading(name="thrust_bearing_temp", value=round(_jitter(thrust_bearing_temp_c, 0.4 * noise_scale, "thrust_bearing_temp" not in offline), 1), unit="C", status=_sensor_status("thrust_bearing_temp", offline, thrust_bearing_temp_c > 80)),
        "coolant_temp": SensorReading(name="coolant_temp", value=round(_jitter(float(machinery["coolant_temp_c"]), 0.4 * noise_scale, "coolant_temp" not in offline), 1), unit="C", status=_sensor_status("coolant_temp", offline, float(machinery["coolant_temp_c"]) > scenario.alarms.engine_temp_warning_c)),
        "jacket_water_pressure": SensorReading(name="jacket_water_pressure", value=round(_jitter(jacket_water_pressure_bar, 0.04 * noise_scale, "jacket_water_pressure" not in offline), 2), unit="bar", status=_sensor_status("jacket_water_pressure", offline, jacket_water_pressure_bar < 3.0)),
        "jacket_water_inlet_temp": SensorReading(name="jacket_water_inlet_temp", value=round(_jitter(jacket_water_inlet_c, 0.3 * noise_scale, "jacket_water_inlet_temp" not in offline), 1), unit="C", status=_sensor_status("jacket_water_inlet_temp", offline)),
        "lube_oil_pressure": SensorReading(name="lube_oil_pressure", value=round(_jitter(float(machinery["lube_oil_pressure_bar"]), 0.05 * noise_scale, "lube_oil_pressure" not in offline), 2), unit="bar", status=_sensor_status("lube_oil_pressure", offline, float(machinery["lube_oil_pressure_bar"]) < scenario.alarms.oil_pressure_warning_bar)),
        "lube_oil_temp": SensorReading(name="lube_oil_temp", value=round(_jitter(float(machinery["lube_oil_temp_c"]), 0.5 * noise_scale, "lube_oil_temp" not in offline), 1), unit="C", status=_sensor_status("lube_oil_temp", offline)),
        "scavenge_air_pressure": SensorReading(name="scavenge_air_pressure", value=round(_jitter(scav_air_pressure_bar, 0.03 * noise_scale, "scavenge_air_pressure" not in offline), 2), unit="bar", status=_sensor_status("scavenge_air_pressure", offline)),
        "scavenge_air_temp": SensorReading(name="scavenge_air_temp", value=round(_jitter(scav_air_temp_c, 0.5 * noise_scale, "scavenge_air_temp" not in offline), 1), unit="C", status=_sensor_status("scavenge_air_temp", offline)),
        "governor_output": SensorReading(name="governor_output", value=round(_jitter(governor_output_percent, 0.6 * noise_scale, "governor_output" not in offline), 1), unit="percent", status=_sensor_status("governor_output", offline)),
        "turbo_rpm": SensorReading(name="turbo_rpm", value=round(_jitter(float(machinery["turbo_rpm"]), 35 * noise_scale, "turbo_rpm" not in offline), 0), unit="rpm", status=_sensor_status("turbo_rpm", offline)),
        "fuel_flow": SensorReading(name="fuel_flow", value=round(_jitter(float(machinery["fuel_flow_lph"]), 2.6 * noise_scale, "fuel_flow" not in offline), 1), unit="lph", status=_sensor_status("fuel_flow", offline)),
        "exhaust_temp": SensorReading(name="exhaust_temp", value=round(_jitter(float(machinery["exhaust_temp_c"]), 2.4 * noise_scale, "exhaust_temp" not in offline), 1), unit="C", status=_sensor_status("exhaust_temp", offline, float(machinery["exhaust_temp_c"]) > 420)),
        "vibration": SensorReading(name="vibration", value=round(_jitter(float(machinery["vibration_mm_s"]), 0.12 * noise_scale, "vibration" not in offline), 2), unit="mm/s", status=_sensor_status("vibration", offline, float(machinery["vibration_mm_s"]) > scenario.alarms.vibration_warning_mm_s)),
        "gearbox_oil_temp": SensorReading(name="gearbox_oil_temp", value=round(_jitter(gearbox_oil_temp_c, 0.4 * noise_scale, "gearbox_oil_temp" not in offline), 1), unit="C", status=_sensor_status("gearbox_oil_temp", offline)),
        "gearbox_oil_pressure": SensorReading(name="gearbox_oil_pressure", value=round(_jitter(gearbox_oil_pressure_bar, 0.05 * noise_scale, "gearbox_oil_pressure" not in offline), 2), unit="bar", status=_sensor_status("gearbox_oil_pressure", offline, gearbox_oil_pressure_bar < 4.5)),
        "stern_tube_temp": SensorReading(name="stern_tube_temp", value=round(_jitter(stern_tube_temp_c, 0.3 * noise_scale, "stern_tube_temp" not in offline), 1), unit="C", status=_sensor_status("stern_tube_temp", offline, stern_tube_temp_c > 58)),
        "engine_room_temp": SensorReading(name="engine_room_temp", value=round(_jitter(engine_room_temp_c, 0.4 * noise_scale, "engine_room_temp" not in offline), 1), unit="C", status=_sensor_status("engine_room_temp", offline, engine_room_temp_c > 46)),
        "engine_room_humidity": SensorReading(name="engine_room_humidity", value=round(_jitter(engine_room_humidity_percent, 1.0 * noise_scale, "engine_room_humidity" not in offline), 1), unit="percent", status=_sensor_status("engine_room_humidity", offline, weather_humidity_warn)),
        "aux_blower_load": SensorReading(name="aux_blower_load", value=round(_jitter(aux_blower_load_kw, 1.2 * noise_scale, "aux_blower_load" not in offline), 1), unit="kW", status=_sensor_status("aux_blower_load", offline)),
        "generator_load": SensorReading(name="generator_load", value=round(_jitter(float(power["generator_load_kw"]), 6.0 * noise_scale, "generator_load" not in offline), 1), unit="kW", status=_sensor_status("generator_load", offline, "generator_fault" in state.active_fault_codes)),
        "hotel_load": SensorReading(name="hotel_load", value=round(_jitter(float(power["hotel_load_kw"]), 3.2 * noise_scale, "hotel_load" not in offline), 1), unit="kW", status=_sensor_status("hotel_load", offline)),
        "bilge_level": SensorReading(name="bilge_level", value=round(_jitter(float(hull["bilge_level_percent"]), 0.4 * noise_scale, "bilge_level" not in offline), 1), unit="percent", status=_sensor_status("bilge_level", offline, float(hull["bilge_level_percent"]) > scenario.alarms.bilge_warning_percent)),
        "roll_sensor": SensorReading(name="roll_sensor", value=round(_jitter(float(hull["roll_deg"]), 0.15 * noise_scale, "roll_sensor" not in offline), 2), unit="deg", status=_sensor_status("roll_sensor", offline, abs(float(hull["roll_deg"])) > 6)),
        "pitch_sensor": SensorReading(name="pitch_sensor", value=round(_jitter(float(hull["pitch_deg"]), 0.12 * noise_scale, "pitch_sensor" not in offline), 2), unit="deg", status=_sensor_status("pitch_sensor", offline, abs(float(hull["pitch_deg"])) > 3.5)),
        "heel_sensor": SensorReading(name="heel_sensor", value=round(_jitter(float(hull["heel_deg"]), 0.12 * noise_scale, "heel_sensor" not in offline), 2), unit="deg", status=_sensor_status("heel_sensor", offline, abs(float(hull["heel_deg"])) > 5)),
        "draft_fore": SensorReading(name="draft_fore", value=round(_jitter(float(hull["draft_forward_m"]), 0.03 * noise_scale, "draft_fore" not in offline), 2), unit="m", status=_sensor_status("draft_fore", offline)),
        "draft_aft": SensorReading(name="draft_aft", value=round(_jitter(float(hull["draft_aft_m"]), 0.03 * noise_scale, "draft_aft" not in offline), 2), unit="m", status=_sensor_status("draft_aft", offline)),
        "trim_indicator": SensorReading(name="trim_indicator", value=round(_jitter(float(hull["trim_m"]), 0.03 * noise_scale, "trim_indicator" not in offline), 2), unit="m", status=_sensor_status("trim_indicator", offline)),
        "hull_stress": SensorReading(name="hull_stress", value=round(_jitter(hull_stress_index, 0.8 * noise_scale, "hull_stress" not in offline), 1), unit="percent", status=_sensor_status("hull_stress", offline, hull_stress_index > 72)),
        "hull_bending": SensorReading(name="hull_bending", value=round(_jitter(hull_bending_percent, 0.7 * noise_scale, "hull_bending" not in offline), 1), unit="percent", status=_sensor_status("hull_bending", offline, hull_bending_percent > 78)),
        "torsion_index": SensorReading(name="torsion_index", value=round(_jitter(torsion_index, 0.7 * noise_scale, "torsion_index" not in offline), 1), unit="percent", status=_sensor_status("torsion_index", offline, torsion_index > 68)),
        "forepeak_tank": SensorReading(name="forepeak_tank", value=round(_jitter(forepeak_tank_percent, 0.4 * noise_scale, "forepeak_tank" not in offline), 1), unit="percent", status=_sensor_status("forepeak_tank", offline)),
        "aftpeak_tank": SensorReading(name="aftpeak_tank", value=round(_jitter(aftpeak_tank_percent, 0.4 * noise_scale, "aftpeak_tank" not in offline), 1), unit="percent", status=_sensor_status("aftpeak_tank", offline)),
        "freeboard_mid": SensorReading(name="freeboard_mid", value=round(_jitter(freeboard_mid_m, 0.05 * noise_scale, "freeboard_mid" not in offline), 2), unit="m", status=_sensor_status("freeboard_mid", offline, freeboard_mid_m < 3.0)),
        "watertight_doors": SensorReading(name="watertight_doors", value=watertight_doors_secured, status=_sensor_status("watertight_doors", offline, not watertight_doors_secured)),
        "leak_watch": SensorReading(name="leak_watch", value=round(_jitter(float(hull["bilge_level_percent"]) * 0.78, 0.5 * noise_scale, "leak_watch" not in offline), 1), unit="percent", status=_sensor_status("leak_watch", offline, leak_watch_warning)),
        "battery_bus": SensorReading(name="battery_bus", value=round(_jitter(float(power["battery_voltage_v"]), 0.04 * noise_scale, "battery_bus" not in offline), 2), unit="V", status=_sensor_status("battery_bus", offline, float(power["battery_voltage_v"]) < scenario.alarms.battery_warning_v)),
        "shore_power": SensorReading(name="shore_power", value=bool(power["shore_power_connected"]), status=_sensor_status("shore_power", offline)),
        "emergency_bus": SensorReading(name="emergency_bus", value=str(power["emergency_bus_status"]), status=_sensor_status("emergency_bus", offline, str(power["emergency_bus_status"]) == "ACTIVE")),
        "fuel": SensorReading(name="fuel", value=round(_jitter(state.fuel_percent, 0.32 * noise_scale, "fuel" not in offline), 2), unit="percent", status=_sensor_status("fuel", offline, state.fuel_percent < scenario.alarms.fuel_warning_percent)),
        "fuel_total": SensorReading(name="fuel_total", value=round(_jitter(state.fuel_percent, 0.32 * noise_scale, "fuel_total" not in offline), 2), unit="percent", status=_sensor_status("fuel_total", offline, state.fuel_percent < scenario.alarms.fuel_warning_percent)),
        "freshwater_tank": SensorReading(name="freshwater_tank", value=round(_jitter(float(cargo["freshwater_percent"]), 0.18 * noise_scale, "freshwater_tank" not in offline), 1), unit="percent", status=_sensor_status("freshwater_tank", offline, float(cargo["freshwater_percent"]) < 20)),
        "waste_tank": SensorReading(name="waste_tank", value=round(_jitter(float(cargo["waste_tank_percent"]), 0.2 * noise_scale, "waste_tank" not in offline), 1), unit="percent", status=_sensor_status("waste_tank", offline, float(cargo["waste_tank_percent"]) > 80)),
        "sludge_tank": SensorReading(name="sludge_tank", value=round(_jitter(float(cargo["sludge_tank_percent"]), 0.2 * noise_scale, "sludge_tank" not in offline), 1), unit="percent", status=_sensor_status("sludge_tank", offline, float(cargo["sludge_tank_percent"]) > 75)),
        "cargo_level": SensorReading(name="cargo_level", value=round(_jitter(float(cargo["cargo_utilization_percent"]), 0.16 * noise_scale, "cargo_level" not in offline), 1), unit="percent", status=_sensor_status("cargo_level", offline)),
        "reefer_power": SensorReading(name="reefer_power", value=round(_jitter(reefer_power_kw, 4.0 * noise_scale, "reefer_power" not in offline), 1), unit="kW", status=_sensor_status("reefer_power", offline, reefer_power_kw > 0 and state.operation_mode == "berthed")),
        "depth": SensorReading(name="depth", value=round(_jitter(state.depth_m, 0.32 * noise_scale, "depth" not in offline), 2), unit="m", status=_sensor_status("depth", offline, state.depth_m < state.draft_aft_m + 7)),
        "rudder_feedback": SensorReading(name="rudder_feedback", value=round(state.rudder_angle_deg, 2), unit="deg", status=_sensor_status("rudder_feedback", offline)),
        "thruster_status": SensorReading(name="thruster_status", value=state.bow_thruster_active, status=_sensor_status("thruster_status", offline)),
        "thruster_load": SensorReading(name="thruster_load", value=round(_jitter(bow_thruster_load_kw, 2.0 * noise_scale, "thruster_load" not in offline), 1), unit="kW", status=_sensor_status("thruster_load", offline, state.bow_thruster_active)),
        "cargo_ops": SensorReading(name="cargo_ops", value=state.loading_progress_percent, unit="percent", status=_sensor_status("cargo_ops", offline, state.operation_mode == "berthed")),
    }

    return TelemetrySnapshot(
        scenario=scenario.name,
        timestamp=state.timestamp,
        tick=state.tick,
        ship={
            "name": scenario.ship.name,
            "latitude": round(state.latitude, 6),
            "longitude": round(state.longitude, 6),
            "speed_knots": round(state.speed_knots, 2),
            "speed_over_ground_knots": round(state.speed_over_ground_knots, 2),
            "heading_deg": round(state.heading_deg, 2),
            "course_over_ground_deg": round(state.course_over_ground_deg, 2),
            "fuel_percent": round(state.fuel_percent, 2),
            "engine_rpm": round(state.engine_rpm, 0),
            "route_direction": navigation["route_direction"],
            "operation_mode": state.operation_mode,
            "ship_role": scenario.ship.profile.role,
        },
        navigation=navigation,
        operations=operations,
        machinery=machinery,
        power=power,
        hull=hull,
        cargo=cargo,
        environment=environment,
        sensors=sensors,
        meta={
            "id": getattr(scenario, "meta", None).id if getattr(scenario, "meta", None) else scenario.name,
            "name": getattr(scenario, "meta", None).name if getattr(scenario, "meta", None) else scenario.name,
            "ship_name": getattr(scenario, "meta", None).ship_name if getattr(scenario, "meta", None) else scenario.ship.name,
            "origin_port": getattr(scenario, "meta", None).origin_port if getattr(scenario, "meta", None) else "",
            "origin_country": getattr(scenario, "meta", None).origin_country if getattr(scenario, "meta", None) else "",
            "destination_port": getattr(scenario, "meta", None).destination_port if getattr(scenario, "meta", None) else "",
            "destination_country": getattr(scenario, "meta", None).destination_country if getattr(scenario, "meta", None) else "",
            "color": getattr(scenario, "meta", None).color if getattr(scenario, "meta", None) else "#2470a0",
        },
        route={
            "waypoints": [point.model_dump(mode="json") for point in scenario.route.waypoints],
            "ports": [port.model_dump(mode="json") for port in scenario.route.ports],
            "deviation_nm": round(deviation_nm, 3),
            "active_waypoint_index": state.active_waypoint_index,
            "next_waypoint_index": state.next_waypoint_index,
            "next_waypoint_name": navigation["next_waypoint_name"],
            "remaining_distance_nm": navigation["remaining_distance_nm"],
        },
        alerts=alerts,
    )
