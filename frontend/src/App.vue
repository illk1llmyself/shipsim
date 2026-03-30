<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { geoCentroid, geoEquirectangular, geoGraticule10, geoPath } from "d3-geo";
import { feature } from "topojson-client";
import worldAtlas from "world-atlas/countries-110m.json";

const MAP_WIDTH = 960;
const MAP_HEIGHT = 500;
const FOCUS_WIDTH = 300;
const FOCUS_HEIGHT = 300;
const VISIBLE_LATITUDE = { north: 78, south: -58 };
const countriesFeature = feature(worldAtlas, worldAtlas.objects.countries);
const projection = geoEquirectangular().fitExtent(
  [
    [18, 18],
    [MAP_WIDTH - 18, MAP_HEIGHT - 18],
  ],
  {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [-180, VISIBLE_LATITUDE.north],
          [180, VISIBLE_LATITUDE.north],
          [180, VISIBLE_LATITUDE.south],
          [-180, VISIBLE_LATITUDE.south],
          [-180, VISIBLE_LATITUDE.north],
        ],
      ],
    },
  }
);
const pathBuilder = geoPath(projection);
const graticulePath = pathBuilder(geoGraticule10()) ?? "";
const countryPaths = countriesFeature.features
  .filter((entry) => geoCentroid(entry)[1] > VISIBLE_LATITUDE.south)
  .map((entry, index) => ({
    id: entry.id ?? `country-${index}`,
    d: pathBuilder(entry) ?? "",
  }))
  .filter((entry) => entry.d);

const latestFleet = ref(null);
const selectedRouteId = ref(null);
const connectionState = ref("baglaniyor");
const positionFrames = ref({});
const animationProgress = ref(1);
const snapshotIntervalMs = ref(500);

let socket = null;
let reconnectTimer = null;
let animationFrame = null;
let animationStartedAt = 0;
let lastSnapshotAt = 0;

function formatNumber(value, digits = 2) {
  return Number(value).toFixed(digits);
}

function formatMetric(value, digits = 1, unit = "") {
  if (typeof value === "boolean") {
    return value ? "ONLINE" : "OFFLINE";
  }
  if (typeof value === "number") {
    return `${formatNumber(value, digits)}${unit ? ` ${unit}` : ""}`;
  }
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  return unit ? `${value} ${unit}` : String(value);
}

function sensorLabel(key) {
  const labels = {
    gps_position: "GPS Position",
    gps_satellites: "GPS Satellites",
    gps_hdop: "GPS HDOP",
    gyro_heading: "Gyro Heading",
    magnetic_compass: "Magnetic Compass",
    course_over_ground: "Course Over Ground",
    speed_over_ground: "Speed Over Ground",
    rate_of_turn: "Rate Of Turn",
    speed_log: "Speed Log",
    track_error: "Track Error",
    ais_transponder: "AIS",
    doppler_log: "Doppler Log",
    depth_under_keel: "Depth Under Keel",
    radar_range: "Radar Range",
    anemometer: "Anemometer",
    wind_direction_true: "Wind Direction",
    barometer: "Barometer",
    humidity_sensor: "Humidity",
    air_temperature: "Air Temperature",
    water_temperature: "Water Temperature",
    current_meter: "Current Meter",
    current_set: "Current Set",
    visibility_sensor: "Visibility",
    sea_state: "Sea State",
    echo_sounder: "Echo Sounder",
    shaft_power: "Shaft Power",
    shaft_torque: "Shaft Torque",
    propeller_slip: "Propeller Slip",
    engine_load: "Engine Load",
    main_bearing_temp: "Main Bearing Temp",
    thrust_bearing_temp: "Thrust Bearing Temp",
    coolant_temp: "Coolant Temp",
    jacket_water_pressure: "Jacket Water Pressure",
    jacket_water_inlet_temp: "Jacket Water Inlet Temp",
    lube_oil_pressure: "Lube Oil Pressure",
    lube_oil_temp: "Lube Oil Temp",
    scavenge_air_pressure: "Scavenge Air Pressure",
    scavenge_air_temp: "Scavenge Air Temp",
    governor_output: "Governor Output",
    turbo_rpm: "Turbo RPM",
    fuel_flow: "Fuel Flow",
    exhaust_temp: "Exhaust Temp",
    vibration: "Vibration",
    gearbox_oil_temp: "Gearbox Oil Temp",
    gearbox_oil_pressure: "Gearbox Oil Pressure",
    stern_tube_temp: "Stern Tube Temp",
    engine_room_temp: "Engine Room Temp",
    engine_room_humidity: "Engine Room Humidity",
    aux_blower_load: "Aux Blower Load",
    generator_load: "Generator Load",
    hotel_load: "Hotel Load",
    bilge_level: "Bilge Level",
    roll_sensor: "Roll Sensor",
    pitch_sensor: "Pitch Sensor",
    heel_sensor: "Heel Sensor",
    draft_fore: "Draft Fore",
    draft_aft: "Draft Aft",
    trim_indicator: "Trim Indicator",
    hull_stress: "Hull Stress",
    hull_bending: "Hull Bending",
    torsion_index: "Torsion Index",
    forepeak_tank: "Forepeak Tank",
    aftpeak_tank: "Aftpeak Tank",
    freeboard_mid: "Freeboard Mid",
    watertight_doors: "Watertight Doors",
    leak_watch: "Leak Watch",
    battery_bus: "Battery Bus",
    shore_power: "Shore Power",
    emergency_bus: "Emergency Bus",
    fuel_total: "Fuel Total",
    freshwater_tank: "Freshwater Tank",
    waste_tank: "Waste Tank",
    sludge_tank: "Sludge Tank",
    cargo_level: "Cargo Level",
    reefer_power: "Reefer Power",
    rudder_feedback: "Rudder Feedback",
    thruster_status: "Thruster Status",
    thruster_load: "Thruster Load",
    cargo_ops: "Cargo Ops",
  };
  return labels[key] ?? key;
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `Istek basarisiz: ${response.status}`);
  }
  return response.json();
}

function normalizeLongitude(value) {
  let longitude = Number(value);
  while (longitude > 180) {
    longitude -= 360;
  }
  while (longitude < -180) {
    longitude += 360;
  }
  return longitude;
}

function longitudeDelta(from, to) {
  let delta = Number(to) - Number(from);
  if (delta > 180) {
    delta -= 360;
  }
  if (delta < -180) {
    delta += 360;
  }
  return delta;
}

function lerp(start, end, progress) {
  return start + (end - start) * progress;
}

function lerpHeading(start, end, progress) {
  return (start + longitudeDelta(start, end) * progress + 360) % 360;
}

function normalizeAngle(value) {
  return (Number(value) % 360 + 360) % 360;
}

function clampHeadingChange(from, to, limit) {
  const delta = longitudeDelta(from, to);
  return normalizeAngle(from + clamp(delta, -limit, limit));
}

function headingFromMotion(from, to, fallback) {
  const deltaLat = Number(to.latitude) - Number(from.latitude);
  const deltaLon = longitudeDelta(Number(from.longitude), Number(to.longitude));

  if (Math.abs(deltaLat) < 0.0001 && Math.abs(deltaLon) < 0.0001) {
    return fallback;
  }

  return (Math.atan2(deltaLon, deltaLat) * 180 / Math.PI + 360) % 360;
}

function headingFromRouteSegment(route) {
  const waypoints = route?.waypoints ?? [];
  if (!waypoints.length) {
    return null;
  }

  const activeIndex = clamp(Number(route.active_waypoint_index ?? 0), 0, waypoints.length - 1);
  const nextIndex = clamp(Number(route.next_waypoint_index ?? activeIndex), 0, waypoints.length - 1);
  const fromPoint = waypoints[activeIndex];
  const toPoint = waypoints[nextIndex];

  if (!fromPoint || !toPoint || activeIndex === nextIndex) {
    return null;
  }

  return headingFromMotion(
    { latitude: fromPoint.latitude, longitude: fromPoint.longitude },
    { latitude: toPoint.latitude, longitude: toPoint.longitude },
    null
  );
}

function preferredShipHeading(ship, route, fromPosition, toPosition) {
  const routeHeading = headingFromRouteSegment(route);
  if (routeHeading !== null) {
    return normalizeAngle(routeHeading);
  }

  const motionHeading = headingFromMotion(fromPosition, toPosition, null);
  if (motionHeading !== null) {
    return motionHeading;
  }

  const course = ship.course_over_ground_deg;
  if (course !== undefined && course !== null) {
    return normalizeAngle(course);
  }

  return normalizeAngle(ship.heading_deg);
}

function project(latitude, longitude) {
  const [x, y] = projection([Number(longitude), Number(latitude)]) ?? [MAP_WIDTH / 2, MAP_HEIGHT / 2];
  return { x, y };
}

function lineFromPoints(points) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
}

function projectFocusPoint(latitude, longitude, centerLatitude, centerLongitude, spanLongitude = 72, spanLatitude = 42) {
  const deltaLon = longitudeDelta(centerLongitude, longitude);
  const deltaLat = Number(latitude) - Number(centerLatitude);

  return {
    x: ((deltaLon / spanLongitude) + 0.5) * FOCUS_WIDTH,
    y: (0.5 - (deltaLat / spanLatitude)) * FOCUS_HEIGHT,
  };
}

function isInsideFocusWindow(latitude, longitude, centerLatitude, centerLongitude, spanLongitude = 72, spanLatitude = 42) {
  const deltaLon = longitudeDelta(centerLongitude, longitude);
  const deltaLat = Number(latitude) - Number(centerLatitude);
  return Math.abs(deltaLon) <= spanLongitude * 0.65 && Math.abs(deltaLat) <= spanLatitude * 0.65;
}

function buildLocalRingPath(ring, centerLatitude, centerLongitude, spanLongitude = 72, spanLatitude = 42) {
  if (!ring?.length) {
    return "";
  }

  const points = ring.map(([longitude, latitude]) =>
    projectFocusPoint(latitude, longitude, centerLatitude, centerLongitude, spanLongitude, spanLatitude)
  );

  return `${lineFromPoints(points)} Z`;
}

function buildFocusLandPaths(geometry, centerLatitude, centerLongitude, spanLongitude = 72, spanLatitude = 42) {
  if (!geometry) {
    return [];
  }

  const polygons = geometry.type === "Polygon"
    ? [geometry.coordinates]
    : geometry.type === "MultiPolygon"
      ? geometry.coordinates
      : [];

  const paths = [];
  for (const polygon of polygons) {
    const visible = polygon.some((ring) =>
      ring.some(([longitude, latitude]) =>
        isInsideFocusWindow(latitude, longitude, centerLatitude, centerLongitude, spanLongitude, spanLatitude)
      )
    );

    if (!visible) {
      continue;
    }

    const shape = polygon
      .map((ring) => buildLocalRingPath(ring, centerLatitude, centerLongitude, spanLongitude, spanLatitude))
      .filter(Boolean)
      .join(" ");

    if (shape) {
      paths.push(shape);
    }
  }

  return paths;
}

function captureShipPosition(ship) {
  return {
    latitude: Number(ship.latitude),
    longitude: normalizeLongitude(ship.longitude),
    heading: normalizeAngle(ship.course_over_ground_deg ?? ship.heading_deg),
  };
}

function displayedPositionFor(routeId, ship) {
  const frame = positionFrames.value[routeId];
  if (!frame) {
    return captureShipPosition(ship);
  }

  const progress = animationProgress.value;
  return {
    latitude: lerp(frame.from.latitude, frame.to.latitude, progress),
    longitude: normalizeLongitude(frame.from.longitude + longitudeDelta(frame.from.longitude, frame.to.longitude) * progress),
    heading: lerpHeading(frame.from.heading, frame.to.heading, progress),
  };
}

function ensureSelection(payload) {
  if (!payload.items.length || selectedRouteId.value === null) {
    return;
  }

  const exists = payload.items.some((item) => item.meta.id === selectedRouteId.value);
  if (!exists) {
    selectedRouteId.value = null;
  }
}

function stopAnimation() {
  if (animationFrame !== null) {
    window.cancelAnimationFrame(animationFrame);
    animationFrame = null;
  }
}

function startAnimation() {
  stopAnimation();
  animationStartedAt = performance.now();
  const duration = Math.max(220, snapshotIntervalMs.value * 0.94);

  const animate = (now) => {
    animationProgress.value = clamp((now - animationStartedAt) / duration, 0, 1);
    if (animationProgress.value < 1) {
      animationFrame = window.requestAnimationFrame(animate);
      return;
    }
    animationFrame = null;
  };

  animationFrame = window.requestAnimationFrame(animate);
}

function primeDisplayState(payload) {
  const nextFrames = {};
  for (const item of payload.items) {
    const position = captureShipPosition(item.ship);
    nextFrames[item.meta.id] = {
      from: position,
      to: position,
    };
  }
  positionFrames.value = nextFrames;
  animationProgress.value = 1;
  latestFleet.value = payload;
  ensureSelection(payload);
}

function applyFleetSnapshot(payload) {
  const now = performance.now();
  if (lastSnapshotAt) {
    snapshotIntervalMs.value = clamp(now - lastSnapshotAt, 280, 1200);
  }
  lastSnapshotAt = now;

  const nextFrames = {};
  for (const item of payload.items) {
    const routeId = item.meta.id;
    const currentDisplayed = displayedPositionFor(routeId, item.ship);
    const rawTarget = captureShipPosition(item.ship);
    const desiredHeading = preferredShipHeading(item.ship, item.route, currentDisplayed, rawTarget);
    const headingDelta = Math.abs(longitudeDelta(currentDisplayed.heading, desiredHeading));
    const turnLimit = headingDelta > 100
      ? 180
      : item.ship.operation_mode === "harbor"
        ? 36
        : item.ship.operation_mode === "approach"
          ? 24
          : 18;
    nextFrames[routeId] = {
      from: currentDisplayed,
      to: {
        ...rawTarget,
        heading: clampHeadingChange(currentDisplayed.heading, desiredHeading, turnLimit),
      },
    };
  }

  positionFrames.value = nextFrames;
  animationProgress.value = 0;
  latestFleet.value = payload;
  ensureSelection(payload);
  startAnimation();
}

async function loadInitialState() {
  const status = await fetchJson("/simulation/status");

  if (status.tick_rate_hz) {
    snapshotIntervalMs.value = clamp(1000 / Number(status.tick_rate_hz), 280, 1200);
  }

  const current = await fetchJson("/fleet/current");
  primeDisplayState(current);
  lastSnapshotAt = performance.now();
}

function connectWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${protocol}://${window.location.host}/ws/fleet`);

  socket.addEventListener("open", () => {
    connectionState.value = "canli";
  });

  socket.addEventListener("message", (event) => {
    applyFleetSnapshot(JSON.parse(event.data));
  });

  socket.addEventListener("close", () => {
    connectionState.value = "kopuk";
    reconnectTimer = window.setTimeout(connectWebSocket, 1500);
  });
}

function closeSelectedRoute() {
  selectedRouteId.value = null;
}

const summary = computed(() => latestFleet.value?.summary ?? { active_routes: 0 });

const mapRoutes = computed(() => {
  if (!latestFleet.value) {
    return [];
  }

  return latestFleet.value.items.map((item) => {
    const planned = item.route.waypoints.map((point) => project(point.latitude, point.longitude));
    const displayed = displayedPositionFor(item.meta.id, item.ship);
    const vesselPoint = project(displayed.latitude, displayed.longitude);
    const ports = (item.route.ports ?? []).map((port) => ({
      ...project(port.latitude, port.longitude),
      name: port.name,
    }));

    return {
      id: item.meta.id,
      color: item.meta.color,
      heading: displayed.heading,
      plannedPath: lineFromPoints(planned),
      ports,
      vesselPoint,
      selected: item.meta.id === selectedRouteId.value,
    };
  });
});

const selectedRoute = computed(() => {
  if (!latestFleet.value) {
    return null;
  }

  const item = latestFleet.value.items.find((entry) => entry.meta.id === selectedRouteId.value);
  if (!item) {
    return null;
  }

  const displayed = displayedPositionFor(item.meta.id, item.ship);
  const navigation = item.navigation ?? {};
  const operations = item.operations ?? {};
  const machinery = item.machinery ?? {};
  const power = item.power ?? {};
  const hull = item.hull ?? {};
  const cargo = item.cargo ?? {};
  const environment = item.environment ?? {};
  const activeWaypointIndex = Number(item.route.active_waypoint_index ?? 0);
  const nextWaypointIndex = Number(item.route.next_waypoint_index ?? activeWaypointIndex);
  const focusLandPaths = countriesFeature.features.flatMap((entry, index) =>
    buildFocusLandPaths(entry.geometry, displayed.latitude, displayed.longitude).map((d, pathIndex) => ({
      id: `${entry.id ?? index}-${pathIndex}`,
      d,
    }))
  );
  const focusWaypoints = item.route.waypoints.map((point, index) => ({
    ...projectFocusPoint(point.latitude, point.longitude, displayed.latitude, displayed.longitude),
    name: point.name,
    active: index === activeWaypointIndex,
    next: index === nextWaypointIndex,
  }));
  const focusPorts = (item.route.ports ?? []).map((port) => ({
    ...projectFocusPoint(port.latitude, port.longitude, displayed.latitude, displayed.longitude),
    name: port.name,
  }));
  const focusShip = {
    ...projectFocusPoint(displayed.latitude, displayed.longitude, displayed.latitude, displayed.longitude),
    heading: displayed.heading,
  };
  const sensors = Object.values(item.sensors ?? {}).map((sensor) => ({
    label: sensorLabel(sensor.name),
    value: formatMetric(sensor.value, 1, sensor.unit ?? ""),
    status: sensor.status,
  }));

  return {
    id: item.meta.id,
    color: item.meta.color,
    name: item.meta.name,
    shipName: item.meta.ship_name,
    origin: `${item.meta.origin_port}, ${item.meta.origin_country}`,
    destination: `${item.meta.destination_port}, ${item.meta.destination_country}`,
    classLine: `${formatMetric(operations.ship_role)} / ${formatMetric(operations.ship_class)}`,
    focusView: {
      landPaths: focusLandPaths,
      plannedPath: lineFromPoints(focusWaypoints),
      waypoints: focusWaypoints,
      ports: focusPorts,
      ship: focusShip,
      centerLabel: `${formatNumber(displayed.latitude, 3)}, ${formatNumber(displayed.longitude, 3)}`,
    },
    topMetrics: [
      { label: "SOG", value: formatMetric(navigation.speed_over_ground_knots, 1, "kn") },
      { label: "COG", value: formatMetric(navigation.course_over_ground_deg, 0, "deg") },
      { label: "RPM", value: formatMetric(item.ship.engine_rpm, 0) },
      { label: "Mode", value: formatMetric(operations.operation_mode) },
      { label: "Load", value: formatMetric(machinery.engine_load_percent, 0, "%") },
      { label: "Fuel Flow", value: formatMetric(machinery.fuel_flow_lph, 0, "lph") },
      { label: "Draft", value: formatMetric(hull.draft_aft_m, 2, "m") },
      { label: "ETA", value: formatMetric(navigation.eta_hours, 1, "h") },
      { label: "Roll", value: formatMetric(hull.roll_deg, 1, "deg") },
    ],
    sections: [
      {
        title: "Operations",
        items: [
          { label: "Role", value: formatMetric(operations.ship_role) },
          { label: "Class", value: formatMetric(operations.ship_class) },
          { label: "Mission", value: formatMetric(operations.mission_status) },
          { label: "Mode", value: formatMetric(operations.operation_mode) },
          { label: "Maneuvering", value: formatMetric(operations.maneuvering_mode) },
          { label: "Bow Thruster", value: formatMetric(operations.bow_thruster_active) },
          { label: "Berth Wait", value: formatMetric(operations.berth_ticks_remaining, 0, "tick") },
          { label: "Cargo Progress", value: formatMetric(operations.loading_progress_percent, 0, "%") },
          { label: "LOA", value: formatMetric(operations.length_m, 0, "m") },
          { label: "Beam", value: formatMetric(operations.beam_m, 0, "m") },
        ],
      },
      {
        title: "Navigation",
        items: [
          { label: "Position", value: `${formatNumber(displayed.latitude, 3)}, ${formatNumber(displayed.longitude, 3)}` },
          { label: "Route Direction", value: formatMetric(item.ship.route_direction) },
          { label: "Heading", value: formatMetric(navigation.heading_deg, 0, "deg") },
          { label: "Desired Heading", value: formatMetric(navigation.desired_heading_deg, 0, "deg") },
          { label: "Rate Of Turn", value: formatMetric(navigation.rate_of_turn_deg_min, 2, "deg/min") },
          { label: "Rudder Angle", value: formatMetric(navigation.rudder_angle_deg, 1, "deg") },
          { label: "Drift", value: formatMetric(navigation.drift_angle_deg, 1, "deg") },
          { label: "Turn Radius", value: formatMetric(navigation.turn_radius_nm, 2, "nm") },
          { label: "Next Waypoint", value: formatMetric(navigation.next_waypoint_name) },
          { label: "Remaining", value: formatMetric(navigation.remaining_distance_nm, 1, "nm") },
          { label: "Deviation", value: formatMetric(item.route.deviation_nm, 2, "nm") },
          { label: "GPS HDOP", value: formatMetric(navigation.gps_hdop, 2) },
        ],
      },
      {
        title: "Machinery",
        items: [
          { label: "Engine Temp", value: formatMetric(item.sensors.engine_temperature?.value ?? machinery.coolant_temp_c, 1, "C") },
          { label: "Shaft Power", value: formatMetric(machinery.shaft_power_kw, 0, "kW") },
          { label: "Oil Pressure", value: formatMetric(machinery.lube_oil_pressure_bar, 2, "bar") },
          { label: "Oil Temp", value: formatMetric(machinery.lube_oil_temp_c, 1, "C") },
          { label: "Coolant Temp", value: formatMetric(machinery.coolant_temp_c, 1, "C") },
          { label: "Exhaust Temp", value: formatMetric(machinery.exhaust_temp_c, 1, "C") },
          { label: "Turbo RPM", value: formatMetric(machinery.turbo_rpm, 0) },
          { label: "Vibration", value: formatMetric(machinery.vibration_mm_s, 2, "mm/s") },
          { label: "Propulsion", value: formatMetric(machinery.propulsion_mode) },
          { label: "Main Engine", value: formatMetric(machinery.main_engine_status) },
        ],
      },
      {
        title: "Power",
        items: [
          { label: "Generator Load", value: formatMetric(power.generator_load_kw, 0, "kW") },
          { label: "Hotel Load", value: formatMetric(power.hotel_load_kw, 0, "kW") },
          { label: "Battery Bus", value: formatMetric(power.battery_voltage_v, 2, "V") },
          { label: "Emergency Bus", value: formatMetric(power.emergency_bus_status) },
          { label: "Shore Power", value: formatMetric(power.shore_power_connected) },
          { label: "Bow Thruster", value: formatMetric(power.bow_thruster_ready) },
        ],
      },
      {
        title: "Hull",
        items: [
          { label: "Draft Forward", value: formatMetric(hull.draft_forward_m, 2, "m") },
          { label: "Draft Aft", value: formatMetric(hull.draft_aft_m, 2, "m") },
          { label: "Trim", value: formatMetric(hull.trim_m, 2, "m") },
          { label: "Heel", value: formatMetric(hull.heel_deg, 1, "deg") },
          { label: "Pitch", value: formatMetric(hull.pitch_deg, 1, "deg") },
          { label: "Bilge", value: formatMetric(hull.bilge_level_percent, 1, "%") },
          { label: "Ballast", value: formatMetric(hull.ballast_percent, 1, "%") },
          { label: "Echo Depth", value: formatMetric(environment.depth_m, 1, "m") },
        ],
      },
      {
        title: "Cargo",
        items: [
          { label: "Cargo Mode", value: formatMetric(cargo.cargo_mode) },
          { label: "Utilization", value: formatMetric(cargo.cargo_utilization_percent, 1, "%") },
          { label: "Cargo Amount", value: `${formatMetric(cargo.cargo_amount, 0)} ${formatMetric(cargo.cargo_unit)}` },
          { label: "Reefer Online", value: formatMetric(cargo.reefer_containers_online, 0) },
          { label: "Freshwater", value: formatMetric(cargo.freshwater_percent, 1, "%") },
          { label: "Waste Tank", value: formatMetric(cargo.waste_tank_percent, 1, "%") },
          { label: "Sludge Tank", value: formatMetric(cargo.sludge_tank_percent, 1, "%") },
        ],
      },
      {
        title: "Environment",
        items: [
          { label: "Wave Height", value: formatMetric(environment.wave_height_m, 1, "m") },
          { label: "True Wind", value: formatMetric(environment.wind_speed_knots, 0, "kn") },
          { label: "App Wind", value: formatMetric(environment.apparent_wind_knots, 0, "kn") },
          { label: "Visibility", value: formatMetric(environment.visibility_nm, 1, "nm") },
          { label: "Air Temp", value: formatMetric(environment.air_temperature_c, 1, "C") },
          { label: "Sea Temp", value: formatMetric(environment.water_temperature_c, 1, "C") },
          { label: "Humidity", value: formatMetric(environment.humidity_percent, 0, "%") },
          { label: "Pressure", value: formatMetric(environment.barometric_pressure_hpa, 0, "hPa") },
          { label: "Current", value: formatMetric(environment.current_knots, 1, "kn") },
          { label: "Current Set", value: formatMetric(environment.current_set_deg, 0, "deg") },
          { label: "Sea State", value: formatMetric(environment.sea_state_beaufort, 0, "Bft") },
        ],
      },
    ],
    alerts: item.alerts,
    sensors,
  };
});

onMounted(async () => {
  await loadInitialState();
  connectWebSocket();
});

onBeforeUnmount(() => {
  stopAnimation();
  if (socket) {
    socket.close();
  }
  if (reconnectTimer) {
    window.clearTimeout(reconnectTimer);
  }
});
</script>

<template>
  <div class="viewport-shell">
    <div class="map-stage">
      <svg class="world-map" :viewBox="`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`" preserveAspectRatio="none" aria-label="Shipsim dunya haritasi">
        <rect x="0" y="0" :width="MAP_WIDTH" :height="MAP_HEIGHT" class="map-sea"></rect>
        <g class="map-graticule">
          <path :d="graticulePath"></path>
        </g>
        <g class="continent-layer">
          <path v-for="country in countryPaths" :key="country.id" :d="country.d"></path>
        </g>

        <g v-for="route in mapRoutes" :key="route.id">
          <path :d="route.plannedPath" class="planned-route" :style="{ '--route-color': route.color }"></path>

          <g
            v-for="(port, index) in route.ports"
            :key="`${route.id}-port-${index}`"
            class="port-marker"
            :transform="`translate(${port.x} ${port.y})`"
          >
            <rect x="-5" y="-5" width="10" height="10" rx="2"></rect>
            <text x="9" y="-8">{{ port.name }}</text>
          </g>

          <g
            class="vessel-marker"
            :class="{ selected: route.selected }"
            :transform="`translate(${route.vesselPoint.x} ${route.vesselPoint.y}) rotate(${route.heading})`"
            @click="selectedRouteId = route.id"
          >
            <circle r="18" class="vessel-halo" :style="{ '--route-color': route.color }"></circle>
            <path class="vessel-ship" :style="{ '--route-color': route.color }" d="M0 -16 L10 10 L0 6 L-10 10 Z"></path>
          </g>
        </g>
      </svg>

      <div class="overlay top-left">
        <div class="brand-row">
          <span class="metric-pill">{{ summary.active_routes }} gemi</span>
          <span class="live-indicator">{{ connectionState }}</span>
        </div>
      </div>

      <div v-if="selectedRoute" class="modal-backdrop" @click="closeSelectedRoute">
        <div class="detail-layout" @click.stop>
          <article class="detail-modal">
            <div class="detail-head">
              <div>
                <p class="detail-kicker">Secili gemi</p>
                <h2>{{ selectedRoute.shipName }}</h2>
                <p class="detail-route">{{ selectedRoute.name }}</p>
                <p class="detail-subline">{{ selectedRoute.classLine }}</p>
              </div>
              <div class="detail-actions">
                <span class="route-badge" :style="{ background: selectedRoute.color }"></span>
                <button type="button" class="close-button" @click="closeSelectedRoute">Kapat</button>
              </div>
            </div>

            <div class="detail-wide-grid">
              <div class="detail-block">
                <span class="metric-label">Hat</span>
                <strong>{{ selectedRoute.origin }}</strong>
                <strong>{{ selectedRoute.destination }}</strong>
              </div>

              <div class="detail-summary-grid">
                <div v-for="metric in selectedRoute.topMetrics" :key="metric.label">
                  <span class="metric-label">{{ metric.label }}</span>
                  <strong>{{ metric.value }}</strong>
                </div>
              </div>
            </div>

            <div class="detail-section-grid">
              <section v-for="section in selectedRoute.sections" :key="section.title" class="detail-section">
                <span class="metric-label">{{ section.title }}</span>
                <div class="metric-list">
                  <div v-for="metric in section.items" :key="`${section.title}-${metric.label}`" class="metric-row">
                    <span>{{ metric.label }}</span>
                    <strong>{{ metric.value }}</strong>
                  </div>
                </div>
              </section>
            </div>

            <div class="detail-block full-width">
              <span class="metric-label">Sensor Stack</span>
              <div class="sensor-list sensor-grid">
                <div v-for="sensor in selectedRoute.sensors" :key="sensor.label" class="sensor-row">
                  <span>{{ sensor.label }}</span>
                  <strong>{{ sensor.value }}</strong>
                  <em class="sensor-status" :class="sensor.status.toLowerCase()">{{ sensor.status }}</em>
                </div>
              </div>
            </div>

            <div class="detail-block full-width">
              <span class="metric-label">Alarm Durumu</span>
              <div v-if="selectedRoute.alerts.length" class="alert-list horizontal">
                <span v-for="alert in selectedRoute.alerts" :key="alert.code" class="alert-chip" :class="alert.level">
                  {{ alert.title }}
                </span>
              </div>
              <p v-else class="clean-state">Bu gemide aktif alarm yok.</p>
            </div>
          </article>

          <aside class="detail-side-camera">
            <div class="detail-focus-head">
              <div>
                <span class="metric-label">Konum Kamerasi</span>
                <strong>{{ selectedRoute.focusView.centerLabel }}</strong>
              </div>
              <span class="detail-focus-tag">Canli Takip</span>
            </div>
            <svg class="focus-map" :viewBox="`0 0 ${FOCUS_WIDTH} ${FOCUS_HEIGHT}`" preserveAspectRatio="none" aria-label="Secili gemi konum kutusu">
              <rect x="0" y="0" :width="FOCUS_WIDTH" :height="FOCUS_HEIGHT" class="focus-sea"></rect>
              <g class="focus-grid">
                <path d="M0 150 H300"></path>
                <path d="M150 0 V300"></path>
                <path d="M0 75 H300"></path>
                <path d="M0 225 H300"></path>
                <path d="M75 0 V300"></path>
                <path d="M225 0 V300"></path>
              </g>
              <g class="focus-land">
                <path v-for="land in selectedRoute.focusView.landPaths" :key="`focus-land-${land.id}`" :d="land.d"></path>
              </g>
              <path :d="selectedRoute.focusView.plannedPath" class="focus-route" :style="{ '--route-color': selectedRoute.color }"></path>
              <g v-for="port in selectedRoute.focusView.ports" :key="`focus-port-${port.name}`" class="focus-port" :transform="`translate(${port.x} ${port.y})`">
                <rect x="-4" y="-4" width="8" height="8" rx="2"></rect>
                <text x="8" y="-6">{{ port.name }}</text>
              </g>
              <g v-for="waypoint in selectedRoute.focusView.waypoints" :key="`focus-waypoint-${waypoint.name}`" class="focus-waypoint" :class="{ active: waypoint.active, next: waypoint.next }" :transform="`translate(${waypoint.x} ${waypoint.y})`">
                <circle r="3"></circle>
              </g>
              <g class="focus-vessel" :transform="`translate(${selectedRoute.focusView.ship.x} ${selectedRoute.focusView.ship.y}) rotate(${selectedRoute.focusView.ship.heading})`">
                <circle r="16" class="focus-vessel-halo" :style="{ '--route-color': selectedRoute.color }"></circle>
                <path class="focus-vessel-ship" :style="{ '--route-color': selectedRoute.color }" d="M0 -14 L9 9 L0 5 L-9 9 Z"></path>
              </g>
            </svg>
          </aside>
        </div>
      </div>
    </div>
  </div>
</template>
