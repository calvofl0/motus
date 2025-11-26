<template>
  <BaseModal :model-value="show" @close="$emit('close')" size="large">
    <template #header>📋 Job Log - Job #{{ job?.job_id }}</template>

    <template #body>
      <div class="job-log-container">
        <div class="job-info">
          <div class="info-row">
            <span class="label">Operation:</span>
            <span class="value">{{ job?.operation }}</span>
          </div>
          <div class="info-row">
            <span class="label">Status:</span>
            <span class="value" :class="`status-${job?.status}`">{{ job?.status }}</span>
          </div>
          <div class="info-row">
            <span class="label">Source:</span>
            <span class="value path">{{ job?.src_path }}</span>
          </div>
          <div class="info-row">
            <span class="label">Destination:</span>
            <span class="value path">{{ job?.dst_path }}</span>
          </div>
          <div v-if="job?.error_text" class="info-row">
            <span class="label">Error:</span>
            <span class="value error">{{ job?.error_text }}</span>
          </div>
        </div>

        <div class="log-section">
          <div class="log-header">
            <h3>Log Output</h3>
          </div>
          <div ref="logContainer" class="log-content">
            <pre v-if="job?.log_text">{{ job.log_text }}</pre>
            <div v-else class="no-log">No log output available</div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <button v-if="job?.log_text" @click="downloadLog" class="btn download-btn">⬇️ Download Log</button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  show: Boolean,
  job: Object
})

defineEmits(['close'])

const logContainer = ref(null)

// Auto-scroll to bottom when log is displayed
watch(() => props.show, async (newVal) => {
  if (newVal && logContainer.value) {
    await nextTick()
    logContainer.value.scrollTop = logContainer.value.scrollHeight
  }
})

// Download log as text file
function downloadLog() {
  if (!props.job || !props.job.log_text) return

  const blob = new Blob([props.job.log_text], { type: 'text/plain' })
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `job_${props.job.job_id}_log.txt`
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}
</script>

<style scoped>
.job-log-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-height: 70vh;
}

.job-info {
  background: #f5f5f5;
  border-radius: 6px;
  padding: 15px;
}

.info-row {
  display: flex;
  margin-bottom: 8px;
  font-size: 14px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  font-weight: 600;
  min-width: 100px;
  color: #666;
}

.info-row .value {
  flex: 1;
  color: #333;
}

.info-row .value.path {
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  word-break: break-all;
}

.info-row .value.error {
  color: #d32f2f;
  font-weight: 500;
}

.status-completed {
  color: #28a745;
  font-weight: 600;
}

.status-failed {
  color: #d32f2f;
  font-weight: 600;
}

.status-interrupted {
  color: #ff9800;
  font-weight: 600;
}

.log-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.log-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.log-header h3 {
  margin: 0;
  font-size: 16px;
  color: #333;
}

.download-btn {
  background: #17a2b8;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.download-btn:hover {
  background: #138496;
}

.log-content {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  padding: 15px;
  overflow-y: auto;
  flex: 1;
  font-family: 'Courier New', Courier, monospace;
  font-size: 13px;
  line-height: 1.5;
  max-height: 400px;
}

.log-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-wrap: break-word;
}

.no-log {
  color: #888;
  font-style: italic;
  text-align: center;
  padding: 40px 0;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: opacity 0.2s;
}

.btn:hover {
  opacity: 0.9;
}

.btn-primary {
  background: #007bff;
  color: white;
}

/* Override BaseModal footer alignment to space buttons */
:deep(.modal-footer) {
  justify-content: space-between;
}
</style>
