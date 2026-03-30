<script setup>
defineProps({
  connectionState: { type: String, required: true },
  scenario: { type: String, required: true },
  tickValue: { type: [String, Number], required: true },
  runState: { type: String, required: true },
  alertCount: { type: Number, required: true },
});
</script>

<template>
  <div class="status-card">
    <div class="status-top">
      <span class="live-indicator">{{ connectionState }}</span>
      <span class="scenario-label">{{ scenario }}</span>
    </div>

    <div class="status-grid">
      <div>
        <span class="metric-label">Tick</span>
        <strong>{{ tickValue }}</strong>
      </div>
      <div>
        <span class="metric-label">Durum</span>
        <strong>{{ runState }}</strong>
      </div>
      <div>
        <span class="metric-label">Alarm</span>
        <strong>{{ alertCount }}</strong>
      </div>
    </div>
  </div>
</template>
