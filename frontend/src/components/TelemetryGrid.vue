<script setup>
import { computed } from "vue";

const props = defineProps({
  snapshot: { type: Object, default: null },
  formatNumber: { type: Function, required: true },
});

const cards = computed(() => {
  if (!props.snapshot) {
    return [
      { title: "Konum", value: "-", note: "Heading -", accent: "accent-sand" },
      { title: "Hiz", value: "-", note: "RPM -", accent: "accent-sea" },
      { title: "Yakit", value: "-", note: "Temp -", accent: "accent-coral" },
      { title: "Deniz Durumu", value: "-", note: "Wind -", accent: "accent-foam" },
    ];
  }

  const { ship, environment, sensors } = props.snapshot;

  return [
    {
      title: "Konum",
      value: `${props.formatNumber(ship.latitude, 4)}, ${props.formatNumber(ship.longitude, 4)}`,
      note: `Heading ${props.formatNumber(ship.heading_deg, 1)} deg`,
      accent: "accent-sand",
    },
    {
      title: "Hiz",
      value: `${props.formatNumber(ship.speed_knots, 2)} kn`,
      note: `RPM ${props.formatNumber(ship.engine_rpm, 0)}`,
      accent: "accent-sea",
    },
    {
      title: "Yakit",
      value: `${props.formatNumber(ship.fuel_percent, 1)} %`,
      note: `Temp ${props.formatNumber(sensors.engine_temperature.value, 1)} C`,
      accent: "accent-coral",
    },
    {
      title: "Deniz Durumu",
      value: `${props.formatNumber(environment.wave_height_m, 1)} m`,
      note: `Wind ${props.formatNumber(environment.wind_speed_knots, 1)} kn | Depth ${props.formatNumber(environment.depth_m, 1)} m`,
      accent: "accent-foam",
    },
  ];
});
</script>

<template>
  <section class="panel telemetry-grid">
    <article v-for="card in cards" :key="card.title" class="metric-card" :class="card.accent">
      <span class="metric-label">{{ card.title }}</span>
      <strong>{{ card.value }}</strong>
      <small>{{ card.note }}</small>
    </article>
  </section>
</template>
