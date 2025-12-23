<template>
  <BaseModal
    v-model="isOpen"
    title="✅ Completed Jobs"
    size="large"
    @close="handleClose"
  >
    <div class="completed-jobs-container">
      <div v-if="loading" class="loading">Loading completed jobs...</div>

      <div v-else-if="completedJobs.length === 0" class="no-jobs">
        No completed jobs found.
      </div>

      <div v-else class="jobs-list">
        <div
          v-for="job in completedJobs"
          :key="job.job_id"
          class="job-item"
          @click="handleShowJobLog(job)"
        >
          <div class="job-info">
            <div class="job-id">Job #{{ job.job_id }}</div>
            <div class="job-operation">{{ job.operation }}</div>
            <div class="job-paths">
              <div class="path-row">
                <span class="path-label">From:</span>
                <span class="path-value">{{ job.src_path }}</span>
              </div>
              <div class="path-row">
                <span class="path-label">To:</span>
                <span class="path-value">{{ job.dst_path }}</span>
              </div>
            </div>
            <div class="job-time">{{ formatTime(job.finished_at) }}</div>
          </div>
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
    @close="showJobLogModal = false"
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
import { ref, computed, watch } from 'vue'
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

function formatTime(isoString) {
  if (!isoString) return 'N/A'
  const date = new Date(isoString)
  return date.toLocaleString()
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

.jobs-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  max-height: 60vh;
  overflow-y: auto;
}

.job-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-bg-light);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-fast);
}

.job-item:hover {
  background: var(--color-bg-secondary);
  border-color: var(--color-primary);
  transform: translateX(4px);
}

.job-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.job-id {
  font-weight: var(--font-weight-semibold);
  color: var(--color-primary);
  font-size: var(--font-size-md);
}

.job-operation {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  text-transform: capitalize;
}

.job-paths {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: var(--spacing-xs);
}

.path-row {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-sm);
}

.path-label {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-tertiary);
  min-width: 50px;
}

.path-value {
  font-family: monospace;
  color: var(--color-text-secondary);
  word-break: break-all;
}

.job-time {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-top: var(--spacing-xs);
}

.delete-btn {
  font-size: 24px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: var(--spacing-sm);
  border-radius: var(--radius-sm);
  transition: var(--transition-fast);
  flex-shrink: 0;
}

.delete-btn:hover {
  background: var(--color-danger-light);
  transform: scale(1.1);
}

.delete-btn:active {
  transform: scale(0.95);
}
</style>
