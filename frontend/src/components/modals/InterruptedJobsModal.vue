<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>⚠️ Interrupted Jobs Found</template>
    <template #body>
      <p class="message">
        Some jobs were interrupted when the server was last stopped. Would you like to resume them?
      </p>
      <div class="jobs-list">
        <div v-for="job in jobs" :key="job.job_id" class="job-item">
          Job #{{ job.job_id }}: {{ job.operation }} - {{ job.src_path }} → {{ job.dst_path }}
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="skip" class="btn btn-secondary">Skip</button>
      <button @click="resumeAll" class="btn btn-success">Resume All</button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'
import { apiCall } from '../../services/api'

const props = defineProps({
  modelValue: Boolean,
  jobs: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:modelValue', 'jobs-resumed'])

function skip() {
  emit('update:modelValue', false)
}

async function resumeAll() {
  try {
    // Resume all jobs
    for (const job of props.jobs) {
      try {
        await apiCall(`/api/jobs/${job.job_id}/resume`, 'POST')
      } catch (error) {
        console.error(`Failed to resume job ${job.job_id}:`, error)
      }
    }

    // Notify parent and close modal
    emit('jobs-resumed')
    emit('update:modelValue', false)
  } catch (error) {
    console.error('Error resuming jobs:', error)
  }
}
</script>

<style scoped>
.message {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
}

.jobs-list {
  max-height: 300px;
  overflow-y: auto;
}

.job-item {
  padding: var(--spacing-sm);
  background: var(--color-bg-light);
  margin: var(--spacing-xs) 0;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
}
</style>
