<script setup>
defineProps({
  sensors: { type: Object, required: true },
});
</script>

<template>
  <section class="panel sensor-panel">
    <div class="panel-heading">
      <h2>Sensorler</h2>
      <p>Anlik sensor okumalari ve durumlari.</p>
    </div>

    <div class="sensor-list">
      <div v-for="(sensor, name) in sensors" :key="name" class="sensor-item">
        <div class="sensor-main">
          <strong>{{ name }}</strong>
          <span>{{ sensor.unit ? `${sensor.value} ${sensor.unit}` : sensor.value }}</span>
        </div>
        <span class="sensor-status" :class="String(sensor.status).toLowerCase()">{{ sensor.status }}</span>
      </div>
    </div>
  </section>
</template>
