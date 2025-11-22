<template>
  <div>
    <!-- Active Jobs Panel -->
    <div class="job-panel" :class="{ collapsed: activeJobsCollapsed }">
      <div class="job-panel-header" @click="toggleActiveJobs">
        <span class="job-panel-title">📊 Active Jobs ({{ activeJobs.length }})</span>
        <span class="collapse-icon">{{ activeJobsCollapsed ? '▼' : '▲' }}</span>
      </div>
      <div v-if="!activeJobsCollapsed" class="job-list">
        <div v-if="activeJobs.length === 0" style="padding: 20px; text-align: center; color: #666;">
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

    <!-- Interrupted Jobs Dropdown -->
    <div
      v-if="interruptedJobs.length > 0"
      class="interrupted-jobs-dropdown"
    >
      <div class="interrupted-jobs-header" @click="toggleInterruptedJobs">
        <span>⚠️ Interrupted Jobs ({{ interruptedJobs.length }})</span>
        <span class="collapse-icon">{{ interruptedJobsCollapsed ? '▼' : '▲' }}</span>
      </div>
      <div v-if="!interruptedJobsCollapsed" class="interrupted-jobs-list">
        <!-- Interrupted jobs will be populated here -->
        <p style="padding: 20px; text-align: center; color: #666;">
          Interrupted jobs in progress...
        </p>
      </div>
    </div>

    <!-- Failed Jobs Dropdown -->
    <div
      v-if="failedJobs.length > 0"
      class="failed-jobs-dropdown"
    >
      <div class="failed-jobs-header" @click="toggleFailedJobs">
        <span>❌ Failed Jobs ({{ failedJobs.length }})</span>
        <span class="collapse-icon">{{ failedJobsCollapsed ? '▼' : '▲' }}</span>
      </div>
      <div v-if="!failedJobsCollapsed" class="failed-jobs-list">
        <!-- Failed jobs will be populated here -->
        <p style="padding: 20px; text-align: center; color: #666;">
          Failed jobs in progress...
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

// Collapsible state
const activeJobsCollapsed = ref(true)
const interruptedJobsCollapsed = ref(true)
const failedJobsCollapsed = ref(true)

// Job lists - will be populated via SSE when job management is implemented
const activeJobs = ref([])
const interruptedJobs = ref([])
const failedJobs = ref([])

// Toggle functions
function toggleActiveJobs() {
  activeJobsCollapsed.value = !activeJobsCollapsed.value
}

function toggleInterruptedJobs() {
  interruptedJobsCollapsed.value = !interruptedJobsCollapsed.value
}

function toggleFailedJobs() {
  failedJobsCollapsed.value = !failedJobsCollapsed.value
}
</script>

<style scoped>
/* Job Panel */
.job-panel {
  background: white;
  border-top: 2px solid #007bff;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
}

.job-panel.collapsed {
  height: 50px;
}

.job-panel:not(.collapsed) {
  height: 300px;
}

.job-panel-header {
  padding: 12px 20px;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  user-select: none;
}

.job-panel-header:hover {
  background: #e9ecef;
}

.job-panel-title {
  font-weight: 600;
  font-size: 14px;
  color: #333;
}

.collapse-icon {
  transition: transform 0.3s;
}

.job-list {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
}

/* Interrupted Jobs Dropdown */
.interrupted-jobs-dropdown {
  background: #fff8e1;
  border: 1px solid #ffc107;
  border-radius: 6px;
  margin: 15px;
  padding: 0;
  overflow: hidden;
}

.interrupted-jobs-header {
  background: #ffc107;
  color: #000;
  padding: 10px 15px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.interrupted-jobs-header:hover {
  background: #ffb300;
}

.interrupted-jobs-list {
  max-height: 200px;
  overflow-y: auto;
  padding: 10px;
}

/* Failed Jobs Dropdown */
.failed-jobs-dropdown {
  background: #ffebee;
  border: 1px solid #dc3545;
  border-radius: 6px;
  margin: 15px;
  padding: 0;
  overflow: hidden;
}

.failed-jobs-header {
  background: #dc3545;
  color: white;
  padding: 10px 15px;
  font-weight: 600;
  cursor: pointer;
  user-select: none;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.failed-jobs-header:hover {
  background: #c82333;
}

.failed-jobs-list {
  max-height: 200px;
  overflow-y: auto;
  padding: 10px;
}
</style>
