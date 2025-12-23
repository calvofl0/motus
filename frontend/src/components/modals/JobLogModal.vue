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
          <div v-if="job?.finished_at" class="info-row">
            <span class="label">Completed:</span>
            <span class="value">{{ formatDateTime(job.finished_at) }}</span>
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
      <div style="display: flex; gap: var(--spacing-sm);">
        <button v-if="job?.log_text" @click="copyLog" class="btn btn-secondary copy-btn" title="Copy log to clipboard (Ctrl+C)">
          📋 Copy Log
          <span v-if="showCopyTooltip" class="copy-tooltip">Copied!</span>
        </button>
        <button v-if="job?.log_text" @click="downloadLog" class="btn btn-info">
          ⬇️ Download Log
        </button>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import BaseModal from './BaseModal.vue'
import { useClipboard } from '../../composables/useClipboard'

const props = defineProps({
  show: Boolean,
  job: Object
})

defineEmits(['close'])

const logContainer = ref(null)

// Use clipboard composable for copy functionality with tooltip
const { copyToClipboard, showCopyTooltip } = useClipboard()

// Auto-scroll to bottom when log is displayed
watch(() => props.show, async (newVal) => {
  if (newVal) {
    await nextTick()
    // Use setTimeout to ensure content is fully rendered
    setTimeout(() => {
      if (logContainer.value) {
        logContainer.value.scrollTop = logContainer.value.scrollHeight
      }
    }, 50)
  }
})

// Format date time for display
function formatDateTime(isoString) {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  return date.toLocaleString()
}

// Copy log to clipboard
async function copyLog() {
  if (!props.job || !props.job.log_text) return

  try {
    await copyToClipboard(props.job.log_text)
  } catch (error) {
    alert('Failed to copy log to clipboard')
  }
}

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

// Handle Ctrl+C to copy log
function handleKeydown(e) {
  if (props.show && (e.ctrlKey || e.metaKey) && e.key === 'c') {
    // Only copy if we're focused on the modal, not on an input field
    const activeElement = document.activeElement
    if (!activeElement || (activeElement.tagName !== 'INPUT' && activeElement.tagName !== 'TEXTAREA')) {
      e.preventDefault()
      copyLog()
    }
  }
}

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<style scoped>
.job-log-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
  max-height: 70vh;
}

.job-info {
  background: var(--color-bg-light);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
}

.info-row {
  display: flex;
  margin-bottom: var(--spacing-xs);
  font-size: var(--font-size-base);
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-row .label {
  font-weight: var(--font-weight-semibold);
  min-width: 100px;
  color: var(--color-text-tertiary);
}

.info-row .value {
  flex: 1;
  color: var(--color-text-primary);
}

.info-row .value.path {
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-md);
  word-break: break-all;
}

.info-row .value.error {
  color: var(--color-danger);
  font-weight: var(--font-weight-medium);
}

.status-completed {
  color: var(--color-success);
  font-weight: var(--font-weight-semibold);
}

.status-failed {
  color: var(--color-danger);
  font-weight: var(--font-weight-semibold);
}

.status-interrupted {
  color: var(--color-warning);
  font-weight: var(--font-weight-semibold);
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
  margin-bottom: var(--spacing-sm);
}

.log-header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}

.log-content {
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  overflow-y: auto;
  flex: 1;
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-md);
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

/* Override BaseModal footer alignment to space buttons */
:deep(.modal-footer) {
  justify-content: space-between;
}

/* Copy button with tooltip */
.copy-btn {
  position: relative;
}

.copy-tooltip {
  display: inline;
  position: absolute;
  top: -30px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-text-primary);
  color: var(--color-bg-white);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  white-space: nowrap;
  pointer-events: none;
  z-index: 1000;
  animation: fadeInOut 1s ease-in-out;
}

@keyframes fadeInOut {
  0% { opacity: 0; transform: translateX(-50%) translateY(5px); }
  20% { opacity: 1; transform: translateX(-50%) translateY(0); }
  80% { opacity: 1; transform: translateX(-50%) translateY(0); }
  100% { opacity: 0; transform: translateX(-50%) translateY(-5px); }
}
</style>
