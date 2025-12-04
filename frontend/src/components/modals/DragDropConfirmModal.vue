<template>
  <BaseModal
    v-model="isOpen"
    title="📋 Confirm Copy Operation"
    size="medium"
    @close="handleClose"
    @confirm="handleConfirm"
  >
    <p class="confirm-text">Copy the following {{ files.length }} file(s)?</p>

    <div class="file-list">
      <div v-for="(file, index) in files" :key="index" class="file-item">
        • {{ file }}
      </div>
    </div>

    <div class="path-info">
      <div class="path-row source-path">
        <span class="path-label">From:</span>
        <span class="path-value">{{ sourcePath }}</span>
      </div>
      <div class="path-row dest-path">
        <span class="path-label">To:</span>
        <span class="path-value">{{ destPath }}</span>
      </div>
    </div>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="btn btn-primary" @click="handleConfirm">
        Copy
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  files: {
    type: Array,
    default: () => []
  },
  sourcePath: {
    type: String,
    default: ''
  },
  destPath: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

function handleConfirm() {
  emit('confirm')
  isOpen.value = false
}

function handleClose() {
  emit('cancel')
  isOpen.value = false
}
</script>

<script>
import { computed } from 'vue'
export default {
  name: 'DragDropConfirmModal'
}
</script>

<style scoped>
.confirm-text {
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.file-list {
  max-height: 200px;
  overflow-y: auto;
  padding: var(--spacing-xs) 0;
  margin: var(--spacing-xs) 0;
}

.file-item {
  padding: 4px var(--spacing-xs);
  font-family: monospace;
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.path-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  padding: var(--spacing-md) 0;
  margin-top: var(--spacing-xs);
  border-top: 1px solid var(--color-border-lighter);
}

.path-row {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-md);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  transition: var(--transition-fast);
}

.path-row.source-path {
  background: var(--color-primary-light);
  border-left: 3px solid var(--color-primary);
}

.path-row.dest-path {
  background: var(--color-success-light);
  border-left: 3px solid var(--color-success);
}

.path-label {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
  min-width: 50px;
}

.path-value {
  font-family: monospace;
  color: var(--color-text-primary);
  word-break: break-all;
  flex: 1;
}
</style>
