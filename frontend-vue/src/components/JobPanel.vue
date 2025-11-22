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
        <div v-else class="job-items">
          <div v-for="job in activeJobs" :key="job.job_id" class="job-item">
            <div class="job-header">
              <span class="job-id">Job #{{ job.job_id }} - {{ job.operation }}</span>
              <button class="job-cancel-btn" @click="cancelJob(job.job_id)" title="Cancel job">×</button>
            </div>
            <div class="job-path">{{ job.src_path }} → {{ job.dst_path }} ({{ formatTime(getElapsedTime(job.created_at)) }})</div>
            <div class="job-time-info">{{ getTransferStatus(job) }}</div>
            <div class="progress-bar-container">
              <div class="progress-bar" :style="{ width: `${job.progress || 0}%` }">
                {{ job.progress || 0 }}%
              </div>
            </div>
          </div>
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
import { ref, onMounted, onUnmounted } from 'vue'
import { apiCall } from '../services/api'

// Collapsible state
const activeJobsCollapsed = ref(true)
const interruptedJobsCollapsed = ref(true)
const failedJobsCollapsed = ref(true)

// Job lists
const activeJobs = ref([])
const interruptedJobs = ref([])
const failedJobs = ref([])

// Tracking
const trackedJobs = ref(new Set())
const jobPanelManuallyToggled = ref(false)
const previousJobState = ref('empty')

// Update intervals
let jobUpdateInterval = null
let interruptedJobsInterval = null
let failedJobsInterval = null

// Toggle functions
function toggleActiveJobs() {
  activeJobsCollapsed.value = !activeJobsCollapsed.value
  jobPanelManuallyToggled.value = !activeJobsCollapsed.value
}

function toggleInterruptedJobs() {
  interruptedJobsCollapsed.value = !interruptedJobsCollapsed.value
}

function toggleFailedJobs() {
  failedJobsCollapsed.value = !failedJobsCollapsed.value
}

/**
 * Format seconds as "1h23min22s" or "10min5s" or "10s"
 */
function formatTime(seconds) {
  if (!seconds || seconds < 0) return '0s'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = seconds % 60

  if (hours > 0) {
    return `${hours}h${minutes}min${secs}s`
  } else if (minutes > 0) {
    return `${minutes}min${secs}s`
  } else {
    return `${secs}s`
  }
}

/**
 * Parse transfer info from rclone text output
 */
function parseTransferInfo(text) {
  if (!text) return null

  const transferMatch = text.match(/Transferred(?:\s+\(bytes\))?:\s+([0-9.]+)\s*([A-Za-z]+)\s*\/\s*([0-9.]+)\s*([A-Za-z]+).*?([0-9.]+)\s*([A-Za-z/]+)s.*?ETA\s+(.+?)$/m)
  if (transferMatch) {
    return {
      transferred: `${transferMatch[1]} ${transferMatch[2]}`,
      total: `${transferMatch[3]} ${transferMatch[4]}`,
      speed: `${transferMatch[5]} ${transferMatch[6]}/s`,
      eta: transferMatch[7].trim()
    }
  }

  return null
}

/**
 * Get elapsed time for a job
 */
function getElapsedTime(createdAt) {
  try {
    let timestamp
    if (createdAt.includes('T')) {
      timestamp = new Date(createdAt)
    } else {
      // SQLite format: "YYYY-MM-DD HH:MM:SS" (UTC)
      timestamp = new Date(createdAt.replace(' ', 'T') + 'Z')
    }

    if (!isNaN(timestamp.getTime())) {
      const now = new Date()
      const elapsedSec = Math.floor((now - timestamp) / 1000)

      if (elapsedSec >= 0 && elapsedSec <= 86400 * 365) {
        return elapsedSec
      }
    }
  } catch (e) {
    console.error('Error parsing job timestamp:', createdAt, e)
  }

  return 0
}

/**
 * Get transfer status string for a job
 */
function getTransferStatus(job) {
  const transferInfo = parseTransferInfo(job.text)
  const progress = job.progress || 0
  const elapsedSec = getElapsedTime(job.created_at)

  if (transferInfo) {
    return `${transferInfo.eta} left - ${transferInfo.transferred} of ${transferInfo.total} (${transferInfo.speed})`
  } else if (progress >= 100) {
    return 'Done'
  } else if (progress > 0) {
    if (elapsedSec > 1) {
      const remainingPercent = 100 - progress
      const etaSec = Math.floor((elapsedSec / progress) * remainingPercent)
      return `${formatTime(etaSec)} left (${progress}%)`
    } else {
      return `${progress}% - Starting...`
    }
  } else {
    return 'Starting...'
  }
}

/**
 * Update active jobs list
 */
async function updateJobs() {
  try {
    const data = await apiCall('/api/jobs?status=running')
    const previousJobs = new Set(activeJobs.value.map(j => j.job_id))
    activeJobs.value = data.jobs || []
    const currentJobs = new Set(activeJobs.value.map(j => j.job_id))

    // Detect completed jobs
    const completedJobs = [...trackedJobs.value].filter(id => !currentJobs.has(id))

    // Auto-refresh destination pane for completed jobs
    for (const jobId of completedJobs) {
      try {
        const jobDetails = await apiCall(`/api/jobs/${jobId}`)
        if (jobDetails && jobDetails.status === 'completed') {
          // Dispatch event to refresh panes
          window.dispatchEvent(new CustomEvent('job-completed', {
            detail: { jobId, dstPath: jobDetails.dst_path }
          }))
        }
      } catch (err) {
        console.error(`Failed to fetch completed job ${jobId}:`, err)
      }
    }

    // Update tracked jobs
    trackedJobs.value = currentJobs

    // Auto-expand/collapse logic
    const newCount = activeJobs.value.length
    const currentState = newCount === 0 ? 'empty' : 'non-empty'

    if (!jobPanelManuallyToggled.value) {
      // Transition from empty to non-empty: auto-open
      if (previousJobState.value === 'empty' && currentState === 'non-empty') {
        activeJobsCollapsed.value = false
      }
      // Transition from non-empty to empty: auto-close
      else if (previousJobState.value === 'non-empty' && currentState === 'empty') {
        activeJobsCollapsed.value = true
      }
    }

    previousJobState.value = currentState
  } catch (error) {
    console.error('Failed to update jobs:', error)
  }
}

/**
 * Update interrupted jobs list
 */
async function updateInterruptedJobs() {
  try {
    const data = await apiCall('/api/jobs?status=interrupted')
    interruptedJobs.value = data.jobs || []
  } catch (error) {
    console.error('Failed to update interrupted jobs:', error)
  }
}

/**
 * Update failed jobs list
 */
async function updateFailedJobs() {
  try {
    const data = await apiCall('/api/jobs?status=failed')
    failedJobs.value = data.jobs || []
  } catch (error) {
    console.error('Failed to update failed jobs:', error)
  }
}

/**
 * Cancel a running job
 */
async function cancelJob(jobId) {
  try {
    await apiCall(`/api/jobs/${jobId}/stop`, 'POST')
    await updateJobs()
  } catch (error) {
    alert(`Failed to cancel job: ${error.message}`)
  }
}

/**
 * Start all job update intervals
 */
function startJobUpdates() {
  updateJobs()
  jobUpdateInterval = setInterval(updateJobs, 2000)

  updateInterruptedJobs()
  interruptedJobsInterval = setInterval(updateInterruptedJobs, 5000)

  updateFailedJobs()
  failedJobsInterval = setInterval(updateFailedJobs, 5000)
}

/**
 * Stop all job update intervals
 */
function stopJobUpdates() {
  if (jobUpdateInterval) {
    clearInterval(jobUpdateInterval)
    jobUpdateInterval = null
  }
  if (interruptedJobsInterval) {
    clearInterval(interruptedJobsInterval)
    interruptedJobsInterval = null
  }
  if (failedJobsInterval) {
    clearInterval(failedJobsInterval)
    failedJobsInterval = null
  }
}

// Listen for manual job update triggers
function handleUpdateJobs() {
  updateJobs()
  updateInterruptedJobs()
  updateFailedJobs()
}

onMounted(() => {
  startJobUpdates()
  window.addEventListener('update-jobs', handleUpdateJobs)
})

onUnmounted(() => {
  stopJobUpdates()
  window.removeEventListener('update-jobs', handleUpdateJobs)
})
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

/* Job Items */
.job-items {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.job-item {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 12px;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.job-id {
  font-weight: 600;
  font-size: 13px;
  color: #333;
}

.job-cancel-btn {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  width: 24px;
  height: 24px;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.job-cancel-btn:hover {
  background: #c82333;
}

.job-path {
  font-size: 12px;
  color: #666;
  margin-bottom: 4px;
  word-break: break-all;
}

.job-time-info {
  font-size: 12px;
  color: #495057;
  margin-bottom: 8px;
}

.progress-bar-container {
  background: #e9ecef;
  border-radius: 4px;
  height: 24px;
  overflow: hidden;
  position: relative;
}

.progress-bar {
  background: linear-gradient(90deg, #007bff, #0056b3);
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 11px;
  font-weight: 600;
  transition: width 0.3s ease;
  min-width: 30px;
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
