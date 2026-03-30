<script setup>
import { computed } from "vue";

const props = defineProps({
  values: { type: Array, required: true },
});

const lineData = computed(() => {
  if (!props.values.length) {
    return { line: "", area: "" };
  }

  const width = 600;
  const height = 180;
  const padding = 18;
  const min = Math.min(...props.values);
  const max = Math.max(...props.values);
  const span = Math.max(max - min, 0.2);

  const points = props.values.map((value, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(props.values.length - 1, 1);
    const y = height - padding - ((value - min) / span) * (height - padding * 2);
    return [x, y];
  });

  const line = points.map(([x, y], index) => `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`).join(" ");
  const area = `${line} L ${points.at(-1)[0].toFixed(2)} ${(height - padding).toFixed(2)} L ${points[0][0].toFixed(2)} ${(height - padding).toFixed(2)} Z`;

  return { line, area };
});
</script>

<template>
  <section class="panel chart-panel">
    <div class="panel-heading">
      <h2>Hiz Trendi</h2>
      <p>Son telemetriler uzerinden canli sparkline.</p>
    </div>
    <svg id="speed-chart" viewBox="0 0 600 180" preserveAspectRatio="none" aria-label="Hiz grafigi">
      <defs>
        <linearGradient id="chart-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="rgba(36, 112, 160, 0.45)"></stop>
          <stop offset="100%" stop-color="rgba(36, 112, 160, 0.02)"></stop>
        </linearGradient>
      </defs>
      <path :d="lineData.area" fill="url(#chart-fill)"></path>
      <path :d="lineData.line" fill="none" class="speed-line"></path>
    </svg>
  </section>
</template>
