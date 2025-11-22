<template>
  <BaseModal
    v-model="isOpen"
    title="Confirm Delete"
    size="small"
    @close="handleClose"
  >
    <div class="modal-content">
      <p class="warning-text">
        <strong>⚠️ Warning:</strong> This action cannot be undone!
      </p>
      <p>Are you sure you want to delete the following {{ items.length }} item(s)?</p>
      <div class="file-list">
        <div v-for="(item, index) in items" :key="index" class="file-item">
          • {{ item }}
        </div>
      </div>
    </div>

    <template #footer>
      <button class="modal-button modal-button-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="modal-button modal-button-danger" @click="handleConfirm">
        Delete
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
  items: {
    type: Array,
    default: () => []
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
  name: 'DeleteConfirmModal'
}
</script>

<style scoped>
.modal-content {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.modal-content p {
  margin: 0;
  color: #555;
  font-size: 14px;
}

.warning-text {
  color: #dc3545;
  padding: 10px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
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

.modal-button {
  padding: 8px 20px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.modal-button-danger {
  background: #dc3545;
  color: white;
}

.modal-button-danger:hover {
  background: #c82333;
}

.modal-button-secondary {
  background: #6c757d;
  color: white;
}

.modal-button-secondary:hover {
  background: #5a6268;
}
</style>
