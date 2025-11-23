<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>⚠️ Interrupted Jobs Found</template>
    <template #body>
      <p style="margin-bottom: 15px;">
        Some jobs were interrupted when the server was last stopped. Would you like to resume them?
      </p>
      <div class="jobs-list">
        <div v-for="job in jobs" :key="job.job_id" class="job-item">
          Job #{{ job.job_id }}: {{ job.operation }} - {{ job.src_path }} → {{ job.dst_path }}
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="skip" class="btn-secondary">Skip</button>
      <button @click="resumeAll" class="btn-primary">Resume All</button>
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
.jobs-list {
  max-height: 300px;
  overflow-y: auto;
}

.job-item {
  padding: 10px;
  background: #f8f9fa;
  margin: 8px 0;
  border-radius: 4px;
  font-size: 14px;
  color: #333;
}

.btn-secondary {
  background: #6c757d;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-right: 10px;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn-primary {
  background: #28a745;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #218838;
}
</style>
