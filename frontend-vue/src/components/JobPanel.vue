<template>
  <div class="job-panel collapsed">
    <div class="job-panel-header" @click="togglePanel">
      <span class="job-panel-title">📊 Active Jobs ({{ jobCount }})</span>
      <span class="collapse-icon">{{ collapsed ? '▼' : '▲' }}</span>
    </div>
    <div v-if="!collapsed" class="job-list">
      <div v-if="jobs.length === 0" style="padding: 20px; text-align: center; color: #666;">
        No active jobs
      </div>
      <div v-else>
        <!-- Job list items will be added here -->
        <p style="padding: 20px; text-align: center; color: #666;">
          Job panel in progress...
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const collapsed = ref(true)
const jobs = ref([])

const jobCount = computed(() => jobs.value.length)

function togglePanel() {
  collapsed.value = !collapsed.value
}
</script>

<style scoped>
.job-panel {
  /* Styles from jobs.css will apply */
}
</style>
