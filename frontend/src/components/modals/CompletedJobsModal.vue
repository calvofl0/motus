<template>
  <BaseModal
    ref="modalRef"
    v-model="isOpen"
    title="✅ Completed Jobs"
    size="large"
    @close="handleClose"
  >
    <div class="completed-jobs-container">
      <ModalTable
        ref="modalTableRef"
        :items="completedJobs"
        :columns="columns"
        v-model:selected-index="selectedJobIndex"
        :grid-template-columns="'50px 60px 1fr 1fr 100px 40px'"
        :row-key="job => job.job_id"
        :loading="loading"
        loading-message="Loading completed jobs..."
        empty-message="No completed jobs found."
        @row-click="handleJobRowClick"
        @keydown="handleCustomKeyDown"
      >
        <!-- Custom cell: ID -->
        <template #cell-id="{ item }">
          <span class="col-id">#{{ item.job_id }}</span>
        </template>

        <!-- Custom cell: Operation -->
        <template #cell-operation="{ item }">
          <span class="col-operation">{{ formatOperation(item.operation) }}</span>
        </template>

        <!-- Custom cell: Source -->
        <template #cell-source="{ item }">
          <span class="col-source" :title="item.src_path">{{ truncatePath(item.src_path) }}</span>
        </template>

        <!-- Custom cell: Destination -->
        <template #cell-destination="{ item }">
          <span class="col-dest" :title="item.dst_path">{{ truncatePath(item.dst_path) }}</span>
        </template>

        <!-- Custom cell: Completed -->
        <template #cell-completed="{ item }">
          <span class="col-time">{{ formatRelativeTime(item.finished_at) }}</span>
        </template>

        <!-- Custom cell: Actions -->
        <template #cell-actions="{ item }">
          <div class="col-actions">
            <button
              class="delete-btn"
              @click.stop="handleDeleteJob(item.job_id)"
              title="Delete the log of this job"
            >
              🗑️
            </button>
          </div>
        </template>
      </ModalTable>
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
    message="Are you sure you want to delete the logs of ALL completed jobs? This cannot be undone."
    @confirm="confirmPurge"
    @close="handlePurgeConfirmClose"
  />

  <!-- Keyboard Shortcuts Modal -->
  <CompletedJobsShortcutsModal
    v-model="showShortcutsModal"
    @close="handleShortcutsClose"
  />
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { apiCall } from '../../services/api'
import BaseModal from './BaseModal.vue'
import ModalTable from './ModalTable.vue'
import JobLogModal from './JobLogModal.vue'
import ConfirmModal from './ConfirmModal.vue'
import CompletedJobsShortcutsModal from './CompletedJobsShortcutsModal.vue'

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

// Column definitions
const columns = [
  { key: 'id', header: 'ID' },
  { key: 'operation', header: 'Op' },
  { key: 'source', header: 'Source' },
  { key: 'destination', header: 'Destination' },
  { key: 'completed', header: 'Completed' },
  { key: 'actions', header: '' }
]

const completedJobs = ref([])
const loading = ref(false)
const selectedJob = ref(null)
const selectedJobIndex = ref(-1) // For keyboard navigation
const showJobLogModal = ref(false)
const showPurgeConfirm = ref(false)
const showShortcutsModal = ref(false)
const modalRef = ref(null)
const modalTableRef = ref(null)

// Fetch completed jobs when modal opens
watch(isOpen, async (newVal) => {
  if (newVal) {
    await fetchCompletedJobs()
    selectedJobIndex.value = -1 // Reset selection
    // Start keyboard listener in ModalTable
    nextTick(() => {
      if (modalTableRef.value) {
        modalTableRef.value.startKeyboardListener()
      }
    })
  } else {
    selectedJobIndex.value = -1 // Reset when closing
    // Stop keyboard listener in ModalTable
    if (modalTableRef.value) {
      modalTableRef.value.stopKeyboardListener()
    }
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

function handleJobRowClick(job, index) {
  // Note: selectedJobIndex is already updated by v-model
  handleShowJobLog(job)
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
    await apiCall('/api/jobs/clear_completed', 'POST')
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
  if (modalRef.value && modalRef.value.focusOverlay) {
    modalRef.value.focusOverlay()
  }
}

async function handlePurgeConfirmClose() {
  // Restore focus to parent modal after confirmation modal closes
  await nextTick()
  if (modalRef.value && modalRef.value.focusOverlay) {
    modalRef.value.focusOverlay()
  }
}

async function handleShortcutsClose() {
  // Restore focus to parent modal after shortcuts modal closes
  await nextTick()
  if (modalRef.value && modalRef.value.focusOverlay) {
    modalRef.value.focusOverlay()
  }
}

function formatOperation(op) {
  return op.charAt(0).toUpperCase() + op.slice(1)
}

// Custom keyboard shortcuts (beyond basic navigation handled by ModalTable)
function handleCustomKeyDown(event) {
  // Don't handle if child modals are open
  if (showJobLogModal.value || showPurgeConfirm.value || showShortcutsModal.value) return

  // F1 - Show keyboard shortcuts
  if (event.key === 'F1') {
    event.preventDefault()
    event.stopPropagation()
    showShortcutsModal.value = true
    return
  }

  // p/P - Purge All (works even without selection)
  if ((event.key === 'p' || event.key === 'P') && completedJobs.value.length > 0) {
    event.preventDefault()
    event.stopPropagation()
    handlePurge()
    return
  }

  if (completedJobs.value.length === 0) return

  // Enter - View log
  if (event.key === 'Enter' && selectedJobIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    handleShowJobLog(completedJobs.value[selectedJobIndex.value])
  }
  // D/Delete - Delete job
  else if ((event.key === 'd' || event.key === 'D' || event.key === 'Delete') && selectedJobIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    const job = completedJobs.value[selectedJobIndex.value]
    handleDeleteJob(job.job_id)
  }
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

// Get user's timezone or fallback to UTC
function getUserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

function formatRelativeTime(isoString) {
  if (!isoString) return 'Unknown'

  const timezone = getUserTimezone()
  const date = new Date(isoString)
  const now = new Date()

  // Get date parts in user's timezone
  const dateFormatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit'
  })

  // Format both dates in user's timezone (returns YYYY-MM-DD)
  const jobDateStr = dateFormatter.format(date)
  const todayStr = dateFormatter.format(now)

  // Parse as Date objects in UTC (consistent comparison)
  const jobDateUTC = new Date(jobDateStr + 'T00:00:00Z')
  const todayUTC = new Date(todayStr + 'T00:00:00Z')

  // Calculate difference in calendar days
  const diffDays = Math.round((todayUTC - jobDateUTC) / (1000 * 60 * 60 * 24))

  // Today: show time only
  if (diffDays === 0) {
    const timeFormatter = new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
      timeZone: timezone
    })
    return timeFormatter.format(date)
  }

  // Yesterday
  if (diffDays === 1) {
    return 'Yesterday'
  }

  // Less than 7 days: show day name
  if (diffDays < 7) {
    const dayFormatter = new Intl.DateTimeFormat('en-US', {
      weekday: 'long',
      timeZone: timezone
    })
    return dayFormatter.format(date)
  }

  // Older: show "23 Nov" format
  const shortDateFormatter = new Intl.DateTimeFormat('en-GB', {
    day: 'numeric',
    month: 'short',
    timeZone: timezone
  })
  return shortDateFormatter.format(date)
}
</script>

<style scoped>
.completed-jobs-container {
  max-height: 60vh;
  min-height: 300px;
}

/* Custom column styling */
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
