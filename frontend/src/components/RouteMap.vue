<script setup>
import { computed } from "vue";

const props = defineProps({
  snapshot: { type: Object, default: null },
  trackHistory: { type: Array, required: true },
});

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

const mapData = computed(() => {
  const route = props.snapshot?.route ?? {};
  const waypoints = Array.isArray(route.waypoints) ? route.waypoints : [];
  const ports = Array.isArray(route.ports) ? route.ports : [];
  const allRoutePoints = [
    ...waypoints.map((point) => ({
      latitude: Number(point.latitude),
      longitude: Number(point.longitude),
      name: point.name,
    })),
    ...ports.map((point) => ({
      latitude: Number(point.latitude),
      longitude: Number(point.longitude),
      name: point.name,
      kind: point.kind,
    })),
  ];

  if (!props.trackHistory.length && !allRoutePoints.length) {
    return {
      routeLine: "",
      trackLine: "",
      routePointsMarkup: "",
      portPointsMarkup: "",
      startPoint: { x: 300, y: 160 },
      currentPoint: { x: 300, y: 160, heading: 0 },
      originLabel: "Baslangic: -",
      currentLabel: "Guncel: -",
      northCoast: "",
      southCoast: "",
    };
  }

  const width = 600;
  const height = 320;
  const padding = 26;
  const boundsPoints = [...props.trackHistory, ...allRoutePoints];
  const latitudes = boundsPoints.map((point) => point.latitude);
  const longitudes = boundsPoints.map((point) => point.longitude);
  const minLat = Math.min(...latitudes);
  const maxLat = Math.max(...latitudes);
  const minLon = Math.min(...longitudes);
  const maxLon = Math.max(...longitudes);
  const latSpan = Math.max(maxLat - minLat, 0.00025);
  const lonSpan = Math.max(maxLon - minLon, 0.00025);

  const project = (point) => {
    const x = padding + ((Number(point.longitude) - minLon) / lonSpan) * (width - padding * 2);
    const y = height - padding - ((Number(point.latitude) - minLat) / latSpan) * (height - padding * 2);
    return {
      x,
      y,
      heading: Number(point.heading ?? 0),
      name: point.name,
    };
  };

  const projectedTrack = props.trackHistory.map(project);
  const projectedWaypoints = waypoints.map(project);
  const projectedPorts = ports.map(project);
  const northCoastY = Math.max(18, padding + (height - padding * 2) * 0.12);
  const southCoastY = height - Math.max(18, padding + (height - padding * 2) * 0.1);
  const routeLine = projectedWaypoints.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");
  const trackLine = projectedTrack.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" ");

  return {
    routeLine,
    trackLine,
    routePointsMarkup: projectedWaypoints
      .map(
        (point) => `
          <g class="route-marker" transform="translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})">
            <circle r="6"></circle>
            <text x="10" y="-10">${esc(point.name)}</text>
          </g>
        `
      )
      .join(""),
    portPointsMarkup: projectedPorts
      .map(
        (point) => `
          <g class="port-marker" transform="translate(${point.x.toFixed(2)} ${point.y.toFixed(2)})">
            <rect x="-9" y="-24" width="18" height="18" rx="4"></rect>
            <path d="M-5 -10 H5 V-17 H1 V-20 H-1 V-17 H-5 Z"></path>
            <text x="12" y="-10">${esc(point.name)}</text>
          </g>
        `
      )
      .join(""),
    startPoint: projectedTrack[0] ?? { x: 300, y: 160 },
    currentPoint: projectedTrack.at(-1) ?? { x: 300, y: 160, heading: 0 },
    originLabel: projectedTrack.length
      ? `Baslangic: ${props.trackHistory[0].latitude.toFixed(4)}, ${props.trackHistory[0].longitude.toFixed(4)}`
      : "Baslangic: -",
    currentLabel: projectedTrack.length
      ? `Guncel: ${props.trackHistory.at(-1).latitude.toFixed(4)}, ${props.trackHistory.at(-1).longitude.toFixed(4)}`
      : "Guncel: -",
    northCoast: `M 0 0 L 0 ${northCoastY.toFixed(2)} C 90 ${(northCoastY - 18).toFixed(2)}, 170 ${(northCoastY + 22).toFixed(2)}, 250 ${(northCoastY + 8).toFixed(2)} C 335 ${(northCoastY - 6).toFixed(2)}, 420 ${(northCoastY + 18).toFixed(2)}, 520 ${(northCoastY - 8).toFixed(2)} C 555 ${(northCoastY - 16).toFixed(2)}, 580 ${(northCoastY - 4).toFixed(2)}, 600 ${(northCoastY - 12).toFixed(2)} L 600 0 Z`,
    southCoast: `M 0 320 L 0 ${southCoastY.toFixed(2)} C 95 ${(southCoastY + 16).toFixed(2)}, 200 ${(southCoastY - 14).toFixed(2)}, 300 ${(southCoastY + 10).toFixed(2)} C 410 ${(southCoastY + 28).toFixed(2)}, 505 ${(southCoastY - 8).toFixed(2)}, 600 ${(southCoastY + 14).toFixed(2)} L 600 320 Z`,
  };
});
</script>

<template>
  <section class="panel map-panel">
    <div class="panel-heading">
      <h2>Canli Rota</h2>
      <p>Harita benzeri izleme panelinde geminin anlik konumu.</p>
    </div>

    <div class="map-meta">
      <span>{{ mapData.originLabel }}</span>
      <span>{{ mapData.currentLabel }}</span>
    </div>

    <svg id="track-map" viewBox="0 0 600 320" preserveAspectRatio="none" aria-label="Rota haritasi">
      <rect x="0" y="0" width="600" height="320" rx="22" class="map-sea"></rect>
      <path :d="mapData.northCoast" class="coast-shape"></path>
      <path :d="mapData.southCoast" class="coast-shape coast-shape-soft"></path>
      <g class="map-grid">
        <path d="M120 0 V320 M240 0 V320 M360 0 V320 M480 0 V320"></path>
        <path d="M0 64 H600 M0 128 H600 M0 192 H600 M0 256 H600"></path>
      </g>
      <path :d="mapData.routeLine" class="route-line"></path>
      <path :d="mapData.trackLine" class="track-line"></path>
      <g v-html="mapData.routePointsMarkup"></g>
      <g v-html="mapData.portPointsMarkup"></g>
      <circle :cx="mapData.startPoint.x" :cy="mapData.startPoint.y" r="7" class="track-start"></circle>
      <g :transform="`translate(${mapData.currentPoint.x} ${mapData.currentPoint.y}) rotate(${mapData.currentPoint.heading})`">
        <circle cx="0" cy="0" r="19" class="ship-halo"></circle>
        <path d="M0 -18 L11 14 L0 8 L-11 14 Z" class="ship-body"></path>
      </g>
    </svg>

    <div class="map-legend">
      <span class="legend-chip"><span class="legend-line"></span>Planli rota</span>
      <span class="legend-chip"><span class="legend-dot"></span>Waypoint</span>
      <span class="legend-chip"><span class="legend-square"></span>Liman</span>
    </div>
  </section>
</template>
