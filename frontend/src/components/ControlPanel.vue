<script setup>
const model = defineModel({ type: String, default: "" });

defineProps({
  scenarios: { type: Array, required: true },
  message: { type: String, required: true },
});

defineEmits(["start", "stop"]);
</script>

<template>
  <section class="panel control-panel">
    <div class="panel-heading">
      <h2>Simulasyon Kontrolu</h2>
      <p>Senaryo sec, baslat, durdur.</p>
    </div>

    <div class="controls">
      <label for="scenario-select">Senaryo</label>
      <select id="scenario-select" v-model="model">
        <option v-for="scenario in scenarios" :key="scenario.path" :value="scenario.path">
          {{ scenario.name }}
        </option>
      </select>

      <div class="button-row">
        <button class="primary" @click="$emit('start')">Baslat</button>
        <button class="ghost" @click="$emit('stop')">Durdur</button>
      </div>
    </div>

    <p class="control-message">{{ message }}</p>
  </section>
</template>
