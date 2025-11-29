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
      <button class="modal-button modal-button-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="modal-button modal-button-primary" @click="handleConfirm">
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
  margin: 0 0 15px 0;
  color: #555;
  font-size: 14px;
  font-weight: 500;
}

.file-list {
  max-height: 200px;
  overflow-y: auto;
  padding: 8px 0;
  margin: 8px 0;
}

.file-item {
  padding: 4px 8px;
  font-family: monospace;
  font-size: 13px;
  color: #555;
}

.path-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 0;
  margin-top: 8px;
  border-top: 1px solid #e9ecef;
}

.path-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
  padding: 10px 12px;
  border-radius: 6px;
  transition: all 0.2s;
}

.path-row.source-path {
  background: #e3f2fd;
  border-left: 3px solid #2196f3;
}

.path-row.dest-path {
  background: #e8f5e9;
  border-left: 3px solid #4caf50;
}

.path-label {
  font-weight: 600;
  color: #555;
  min-width: 50px;
}

.path-value {
  font-family: monospace;
  color: #333;
  word-break: break-all;
  flex: 1;
}

.modal-button {
  padding: 8px 20px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-button-primary {
  background: #007bff;
  color: white;
}

.modal-button-primary:hover {
  background: #0056b3;
}

.modal-button-secondary {
  background: #6c757d;
  color: white;
}

.modal-button-secondary:hover {
  background: #5a6268;
}
</style>
