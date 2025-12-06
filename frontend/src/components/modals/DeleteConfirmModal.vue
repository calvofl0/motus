<template>
  <BaseModal
    v-model="isOpen"
    title="🗑️ Confirm Delete Operation"
    size="small"
    @close="handleClose"
    @confirm="handleConfirm"
  >
    <p class="confirm-text">Are you sure you want to delete the following {{ items.length }} item(s)?</p>
    <div class="file-list">
      <div v-for="(item, index) in items" :key="index" class="file-item">
        • {{ item }}
      </div>
    </div>
    <p class="warning-text">
      <strong>⚠️ Warning:</strong> This action cannot be undone!
    </p>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="btn btn-danger" @click="handleConfirm">
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
.confirm-text {
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
}

.warning-text {
  color: var(--color-danger);
  padding: var(--spacing-sm);
  background: var(--color-warning-light);
  border: 1px solid var(--color-warning);
  border-radius: var(--radius-sm);
  margin-top: var(--spacing-lg);
}

.file-list {
  max-height: 200px;
  overflow-y: auto;
  padding: var(--spacing-sm);
  background: var(--color-bg-light);
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border-light);
}

.file-item {
  padding: 4px 0;
  font-family: monospace;
  font-size: var(--font-size-md);
  color: var(--color-text-primary);
}
</style>
