<template>
  <BaseModal
    ref="modalRef"
    v-model="isOpen"
    title="✅ Completed Jobs"
    size="large"
    @close="handleClose"
  >
    <div class="completed-jobs-container" tabindex="-1">
      <div v-if="loading" class="loading">Loading completed jobs...</div>

      <div v-else-if="completedJobs.length === 0" class="no-jobs">
        No completed jobs found.
      </div>

      <div v-else class="jobs-table">
        <div class="table-header">
          <div class="col-id">ID</div>
          <div class="col-operation">Op</div>
          <div class="col-source">Source</div>
          <div class="col-dest">Destination</div>
          <div class="col-time">Completed</div>
          <div class="col-actions"></div>
        </div>
        <div class="table-body">
          <div
            v-for="job in completedJobs"
            :key="job.job_id"
            class="job-row"
            @click="handleShowJobLog(job)"
          >
            <div class="col-id">#{{ job.job_id }}</div>
            <div class="col-operation">{{ formatOperation(job.operation) }}</div>
            <div class="col-source" :title="job.src_path">{{ truncatePath(job.src_path) }}</div>
            <div class="col-dest" :title="job.dst_path">{{ truncatePath(job.dst_path) }}</div>
            <div class="col-time">{{ formatRelativeTime(job.finished_at) }}</div>
            <div class="col-actions">
              <button
                class="delete-btn"
                @click.stop="handleDeleteJob(job.job_id)"
                title="Delete this job"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <button
        v-if="completedJobs.length > 0"
        class="btn btn-danger"
        @click="handlePurge"
      >
        Purge All
      </button>
      <button class="btn btn-secondary" @click="handleClose">
        Close
      </button>
    </template>
  </BaseModal>

  <!-- Job Log Modal -->
  <JobLogModal
    :show="showJobLogModal"
    :job="selectedJob"
    @close="handleJobLogClose"
  />

  <!-- Purge Confirmation Modal -->
  <ConfirmModal
    v-model="showPurgeConfirm"
    title="⚠️ Confirm Purge"
    message="Are you sure you want to delete ALL completed jobs? This cannot be undone."
    @confirm="confirmPurge"
  />
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { apiCall } from '../../services/api'
import BaseModal from './BaseModal.vue'
import JobLogModal from './JobLogModal.vue'
import ConfirmModal from './ConfirmModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['update:modelValue'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const completedJobs = ref([])
const loading = ref(false)
const selectedJob = ref(null)
const showJobLogModal = ref(false)
const showPurgeConfirm = ref(false)
const modalRef = ref(null)

// Fetch completed jobs when modal opens
watch(isOpen, async (newVal) => {
  if (newVal) {
    await fetchCompletedJobs()
  }
})

async function fetchCompletedJobs() {
  loading.value = true
  try {
    const response = await apiCall('/api/jobs?status=completed&limit=1000')
    completedJobs.value = response.jobs || []
  } catch (error) {
    console.error('Failed to fetch completed jobs:', error)
    completedJobs.value = []
  } finally {
    loading.value = false
  }
}

async function handleShowJobLog(job) {
  // Fetch full job details including log
  try {
    const fullJob = await apiCall(`/api/jobs/${job.job_id}`)
    // Also fetch the log separately to ensure we have it
    const logData = await apiCall(`/api/jobs/${job.job_id}/log`)
    fullJob.log_text = logData.log_text
    selectedJob.value = fullJob
    showJobLogModal.value = true
  } catch (error) {
    console.error('Failed to fetch job log:', error)
  }
}

async function handleDeleteJob(jobId) {
  if (!confirm(`Delete job #${jobId}?`)) return

  try {
    await apiCall(`/api/jobs/${jobId}`, 'DELETE')
    // Remove from list
    completedJobs.value = completedJobs.value.filter(j => j.job_id !== jobId)
  } catch (error) {
    console.error('Failed to delete job:', error)
    alert(`Failed to delete job: ${error.message}`)
  }
}

function handlePurge() {
  showPurgeConfirm.value = true
}

async function confirmPurge() {
  try {
    await apiCall('/api/jobs/clear_stopped', 'POST')
    // Clear the list
    completedJobs.value = []
    showPurgeConfirm.value = false
  } catch (error) {
    console.error('Failed to purge completed jobs:', error)
    alert(`Failed to purge jobs: ${error.message}`)
  }
}

function handleClose() {
  isOpen.value = false
}

async function handleJobLogClose() {
  showJobLogModal.value = false
  // Restore focus to parent modal after child modal closes
  await nextTick()
  if (modalRef.value && modalRef.value.$el) {
    const focusable = modalRef.value.$el.querySelector('[tabindex]')
    if (focusable) {
      focusable.focus()
    }
  }
}

function formatOperation(op) {
  return op.charAt(0).toUpperCase() + op.slice(1)
}

function truncatePath(path) {
  if (!path) return ''

  // Extract remote and path parts
  const colonIndex = path.indexOf(':')
  let remote = ''
  let actualPath = path

  if (colonIndex > 0) {
    remote = path.substring(0, colonIndex + 1)
    actualPath = path.substring(colonIndex + 1)
  }

  // If path is short enough, return as-is
  const maxLength = 40
  if (path.length <= maxLength) {
    return path
  }

  // Extract filename
  const lastSlash = actualPath.lastIndexOf('/')
  let filename = actualPath
  let dirPath = ''

  if (lastSlash >= 0) {
    dirPath = actualPath.substring(0, lastSlash + 1)
    filename = actualPath.substring(lastSlash + 1)
  }

  // Calculate available space for middle part
  const remoteLen = remote.length
  const filenameLen = filename.length
  const ellipsisLen = 3
  const availableForDir = maxLength - remoteLen - filenameLen - ellipsisLen

  if (availableForDir <= 0) {
    // Not enough space, just show remote + ... + filename
    return `${remote}...${filename}`
  }

  // Truncate directory path from the start
  if (dirPath.length > availableForDir) {
    dirPath = '...' + dirPath.substring(dirPath.length - availableForDir + 3)
  }

  return `${remote}${dirPath}${filename}`
}

function formatRelativeTime(isoString) {
  if (!isoString) return 'Unknown'

  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now - date
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  // Today: show time only
  if (diffDays === 0) {
    const hours = date.getHours().toString().padStart(2, '0')
    const minutes = date.getMinutes().toString().padStart(2, '0')
    return `${hours}:${minutes}`
  }

  // Yesterday
  if (diffDays === 1) {
    return 'Yesterday'
  }

  // Less than 7 days: show day name
  if (diffDays < 7) {
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    return dayNames[date.getDay()]
  }

  // Older: show "23 Nov" format
  const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
  const day = date.getDate()
  const month = monthNames[date.getMonth()]
  return `${day} ${month}`
}
</script>

<style scoped>
.completed-jobs-container {
  max-height: 60vh;
  min-height: 300px;
}

.loading,
.no-jobs {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--color-text-secondary);
  font-style: italic;
}

.jobs-table {
  display: flex;
  flex-direction: column;
  font-size: var(--font-size-sm);
}

.table-header {
  display: grid;
  grid-template-columns: 50px 60px 1fr 1fr 100px 40px;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-secondary);
  border-bottom: 2px solid var(--color-border);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.table-body {
  max-height: 50vh;
  overflow-y: auto;
}

.job-row {
  display: grid;
  grid-template-columns: 50px 60px 1fr 1fr 100px 40px;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  border-bottom: 1px solid var(--color-border-light);
  cursor: pointer;
  transition: var(--transition-fast);
  align-items: center;
}

.job-row:hover {
  background: var(--color-bg-light);
  border-left: 3px solid var(--color-primary);
  padding-left: calc(var(--spacing-md) - 3px);
}

.col-id {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
}

.col-operation {
  color: var(--color-text-secondary);
}

.col-source,
.col-dest {
  font-family: monospace;
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-time {
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  text-align: right;
}

.col-actions {
  text-align: center;
}

.delete-btn {
  font-size: 14px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: var(--transition-fast);
}

.delete-btn:hover {
  background: var(--color-danger-light);
  transform: scale(1.1);
}

.delete-btn:active {
  transform: scale(0.95);
}
</style>
