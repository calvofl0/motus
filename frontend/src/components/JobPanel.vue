<template>
  <div>
    <!-- Active Jobs Panel -->
    <div class="job-panel" :class="{ collapsed: activeJobsCollapsed }">
      <div class="job-panel-header" @click="toggleActiveJobs">
        <span class="job-panel-title">📊 Active Jobs ({{ activeJobs.length }})</span>
        <span class="collapse-icon">{{ activeJobsCollapsed ? '▼' : '▲' }}</span>
      </div>
      <div v-if="!activeJobsCollapsed" class="job-list">
        <div v-if="activeJobs.length === 0" class="empty-jobs-message">
          No active jobs
        </div>
        <div v-else class="job-items">
          <div v-for="job in activeJobs" :key="job.job_id" :class="['job-item', job.status]">
            <span class="job-id">Job #{{ job.job_id }} - {{ job.operation }}</span>
            <span class="job-path">{{ job.src_path }} → {{ job.dst_path }} ({{ formatTime(getElapsedTime(job.created_at)) }})</span>
            <span class="job-time-info">{{ getTransferStatus(job) }}</span>
            <div v-if="job.log_text" class="job-log-text">{{ job.log_text }}</div>
            <div class="progress-bar-container">
              <div class="progress-bar" :style="{ width: `${job.progress || 0}%` }">
                {{ job.progress || 0 }}%
              </div>
            </div>
            <span class="job-status">{{ job.status }}</span>
            <button class="job-icon-btn cancel" @click="cancelJob(job.job_id)" title="Cancel job">×</button>
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
        <div v-for="job in interruptedJobs" :key="job.job_id" class="interrupted-job-item">
          <div class="interrupted-job-info">
            Job #{{ job.job_id }} ({{ job.operation }}): {{ job.src_path }} → {{ job.dst_path }}
          </div>
          <div class="interrupted-job-actions">
            <button class="job-icon-btn resume" @click="resumeJob(job.job_id)" title="Resume this job">↻</button>
            <button class="job-icon-btn cancel" @click="cancelInterruptedJob(job.job_id)" title="Cancel this job">×</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Failed Jobs Dropdown -->
    <div
      v-if="failedJobs.length > 0"
      ref="failedJobsRef"
      class="failed-jobs-dropdown"
      tabindex="-1"
    >
      <div class="failed-jobs-header" @click="toggleFailedJobs">
        <span><span class="tour-failed-icon">❌</span> Failed Jobs ({{ failedJobs.length }})</span>
        <span class="collapse-icon">{{ failedJobsCollapsed ? '▼' : '▲' }}</span>
      </div>
      <div v-if="!failedJobsCollapsed" class="failed-jobs-list">
        <div
          v-for="job in failedJobs"
          :key="job.job_id"
          class="failed-job-item"
          @click="showJobLog(job)"
          title="Click to view log"
        >
          <div class="failed-job-info">
            Job #{{ job.job_id }} ({{ job.operation }}): {{ job.src_path }} → {{ job.dst_path }}
          </div>
          <div class="failed-job-actions">
            <button class="job-icon-btn resume" @click.stop="resumeFailedJob(job.job_id)" title="Resume this job">↻</button>
            <button class="job-icon-btn cancel" @click.stop="clearFailedJob(job.job_id)" title="Remove from list">×</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Job Log Modal -->
  <JobLogModal
    :show="showLogModal"
    :job="selectedJob"
    @close="handleJobLogClose"
  />
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { apiCall } from '../services/api'
import JobLogModal from './modals/JobLogModal.vue'

// Collapsible state
const activeJobsCollapsed = ref(true)
const interruptedJobsCollapsed = ref(true)
const failedJobsCollapsed = ref(true)

// Job lists
const activeJobs = ref([])
const interruptedJobs = ref([])
const failedJobs = ref([])

// Job log modal state
const showLogModal = ref(false)
const selectedJob = ref(null)
const failedJobsRef = ref(null)

// Tracking
const trackedJobs = ref(new Set())
const jobPanelManuallyToggled = ref(false)
const previousJobState = ref('empty')

// Update intervals
let jobUpdateInterval = null
let interruptedJobsInterval = null
let failedJobsInterval = null

// Shutdown flag to prevent API calls after shutdown event
let isShuttingDown = false

// Toggle functions
function toggleActiveJobs() {
  const willOpen = activeJobsCollapsed.value
  activeJobsCollapsed.value = !activeJobsCollapsed.value
  jobPanelManuallyToggled.value = !activeJobsCollapsed.value

  // Close other dropdowns when opening this one
  if (willOpen) {
    interruptedJobsCollapsed.value = true
    failedJobsCollapsed.value = true
  }
}

function toggleInterruptedJobs() {
  const willOpen = interruptedJobsCollapsed.value
  interruptedJobsCollapsed.value = !interruptedJobsCollapsed.value

  // Close other dropdowns when opening this one
  if (willOpen) {
    activeJobsCollapsed.value = true
    failedJobsCollapsed.value = true
  }
}

function toggleFailedJobs() {
  const willOpen = failedJobsCollapsed.value
  failedJobsCollapsed.value = !failedJobsCollapsed.value

  // Close other dropdowns when opening this one
  if (willOpen) {
    activeJobsCollapsed.value = true
    interruptedJobsCollapsed.value = true
  }
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

  // Match pattern like: "Transferred: 123.45 MiB / 500.00 MiB, 50%, 10.50 MiB/s, ETA 30s"
  const transferMatch = text.match(/Transferred(?:\s+\(bytes\))?:\s+([0-9.]+)\s*([A-Za-z]+)\s*\/\s*([0-9.]+)\s*([A-Za-z]+).*?([0-9.]+)\s*([A-Za-z/]+s).*?ETA\s+(.+?)$/m)
  if (transferMatch) {
    return {
      transferred: `${transferMatch[1]} ${transferMatch[2]}`,
      total: `${transferMatch[3]} ${transferMatch[4]}`,
      speed: `${transferMatch[5]} ${transferMatch[6]}`,  // transferMatch[6] already includes /s
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
  // Don't make API calls if server is shutting down
  if (isShuttingDown) {
    return
  }

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
          // Dispatch event to refresh panes and trigger downloads
          window.dispatchEvent(new CustomEvent('job-completed', {
            detail: jobDetails  // Pass full job details including download_token
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
        // Close other dropdowns when auto-opening this one
        interruptedJobsCollapsed.value = true
        failedJobsCollapsed.value = true
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
  // Don't make API calls if server is shutting down
  if (isShuttingDown) {
    return
  }

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
  // Don't make API calls if server is shutting down
  if (isShuttingDown) {
    return
  }

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
 * Resume an interrupted job
 */
async function resumeJob(jobId) {
  try {
    await apiCall(`/api/jobs/${jobId}/resume`, 'POST')
    await updateInterruptedJobs()
    await updateJobs()
  } catch (error) {
    alert(`Failed to resume job: ${error.message}`)
  }
}

/**
 * Cancel an interrupted job
 */
async function cancelInterruptedJob(jobId) {
  try {
    await apiCall(`/api/jobs/${jobId}/stop`, 'POST')
    await updateInterruptedJobs()
  } catch (error) {
    alert(`Failed to cancel job: ${error.message}`)
  }
}

/**
 * Clear a failed job from the list
 */
async function clearFailedJob(jobId) {
  try {
    await apiCall(`/api/jobs/${jobId}`, 'DELETE')
    await updateFailedJobs()
  } catch (error) {
    alert(`Failed to clear job: ${error.message}`)
  }
}

/**
 * Resume a failed job
 */
async function resumeFailedJob(jobId) {
  try {
    await apiCall(`/api/jobs/${jobId}/resume`, 'POST')
    await updateFailedJobs()
    await updateJobs() // Refresh active jobs list
  } catch (error) {
    alert(`Failed to resume job: ${error.message}`)
  }
}

/**
 * Show job log modal for a failed job
 */
async function showJobLog(job) {
  try {
    // Fetch full job details including log
    const fullJob = await apiCall(`/api/jobs/${job.job_id}`)
    selectedJob.value = fullJob
    showLogModal.value = true
  } catch (error) {
    alert(`Failed to load job log: ${error.message}`)
  }
}

/**
 * Handle job log modal close - restore focus to failed jobs dropdown
 */
async function handleJobLogClose() {
  showLogModal.value = false
  // Restore focus to failed jobs dropdown after modal closes
  await nextTick()
  if (failedJobsRef.value) {
    failedJobsRef.value.focus()
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

// Handle server shutdown - stop polling immediately
function handleServerShutdown() {
  console.log('[JobPanel] Server shutting down, stopping all polling')
  isShuttingDown = true
  stopJobUpdates()
}

onMounted(() => {
  startJobUpdates()
  window.addEventListener('update-jobs', handleUpdateJobs)
  window.addEventListener('server-shutting-down', handleServerShutdown)
})

onUnmounted(() => {
  stopJobUpdates()
  window.removeEventListener('update-jobs', handleUpdateJobs)
  window.removeEventListener('server-shutting-down', handleServerShutdown)
})
</script>

<style scoped>
/* Failed jobs hover effect to indicate clickability */
.failed-job-item {
  cursor: pointer;
  transition: var(--transition-fast);
}

.failed-job-item:hover {
  background: var(--color-bg-light);
  border-left: 3px solid var(--color-danger);
  padding-left: calc(var(--spacing-sm) - 3px);
}

/* Resume button green color */
.job-icon-btn.resume {
  color: var(--color-success);
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  font-size: 1.1em;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.job-icon-btn.resume:hover {
  transform: scale(1.2);
  opacity: 0.8;
}

/* Improve icon button hover effects - no blue rectangle */
.job-icon-btn {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.job-icon-btn:hover {
  transform: scale(1.2);
  opacity: 0.7;
}

/* Cancel button - light red to contrast with red background */
.job-icon-btn.cancel {
  color: #ffcccc;
  font-size: 1.3em;
  font-weight: bold;
}
</style>
