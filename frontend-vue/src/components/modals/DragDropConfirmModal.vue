<template>
  <BaseModal
    v-model="isOpen"
    title="Confirm Copy"
    size="medium"
    @close="handleClose"
    @confirm="handleConfirm"
  >
    <div class="modal-content">
      <p>Copy the following {{ files.length }} file(s)?</p>

      <div class="file-list">
        <div v-for="(file, index) in files" :key="index" class="file-item">
          • {{ file }}
        </div>
      </div>

      <div class="path-info">
        <div class="path-row">
          <span class="path-label">From:</span>
          <span class="path-value">{{ sourcePath }}</span>
        </div>
        <div class="path-row">
          <span class="path-label">To:</span>
          <span class="path-value">{{ destPath }}</span>
        </div>
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
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.modal-content > p {
  margin: 0;
  color: #555;
  font-size: 14px;
  font-weight: 500;
}

.file-list {
  max-height: 200px;
  overflow-y: auto;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
}

.file-item {
  padding: 4px 0;
  font-family: monospace;
  font-size: 13px;
  color: #333;
}

.path-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 4px;
  border: 1px solid #e0e0e0;
  border-left: 3px solid #007bff;
}

.path-row {
  display: flex;
  gap: 10px;
  font-size: 13px;
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
