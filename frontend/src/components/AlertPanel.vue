<script setup>
import { computed } from "vue";

const props = defineProps({
  alerts: { type: Array, required: true },
  route: { type: Object, required: true },
});

const summary = computed(() => {
  if (!props.alerts.length) {
    const deviation = typeof props.route.deviation_nm === "number" ? `Rota sapmasi ${props.route.deviation_nm.toFixed(3)} nm.` : "";
    return `Aktif alarm yok. ${deviation}`.trim();
  }

  const criticalCount = props.alerts.filter((alert) => alert.level === "critical").length;
  return criticalCount > 0
    ? `${criticalCount} kritik alarm var. Hemen mudahale gerektiriyor.`
    : `${props.alerts.length} alarm izleniyor. Sistem dikkat gerektiriyor.`;
});
</script>

<template>
  <section class="panel alert-panel">
    <div class="panel-heading">
      <h2>Alarm Paneli</h2>
      <p>Rota, motor, yakit ve deniz kosullarina gore canli uyarilar.</p>
    </div>

    <div class="alert-summary">{{ summary }}</div>

    <div class="alert-list">
      <article v-for="alert in alerts" :key="alert.code" class="alert-card" :class="alert.level">
        <div class="alert-top">
          <h3 class="alert-title">{{ alert.title }}</h3>
          <span class="alert-badge" :class="alert.level">{{ alert.level }}</span>
        </div>
        <p class="alert-message">{{ alert.message }}</p>
        <div class="alert-value">Deger: {{ alert.value }}{{ alert.unit ? ` ${alert.unit}` : "" }}</div>
      </article>
    </div>
  </section>
</template>
