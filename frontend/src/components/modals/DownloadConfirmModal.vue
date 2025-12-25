<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
  >
    <template #header>📥 Download File</template>
    <template #body>
      <div class="download-content">
        <div class="download-question">
          Do you want to download this file?
        </div>
        <div class="file-info">
          <div class="file-name">{{ fileName }}</div>
          <div class="file-size">Size: {{ fileSize }}</div>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="$emit('cancel')" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="$emit('confirm')" class="btn btn-success">
        Download
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

defineProps({
  modelValue: Boolean,
  fileName: {
    type: String,
    default: ''
  },
  fileSize: {
    type: String,
    default: ''
  }
})

defineEmits(['update:modelValue', 'confirm', 'cancel'])
</script>

<style scoped>
.download-content {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
}

.download-question {
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--spacing-sm);
  font-size: var(--font-size-lg);
}

.file-info {
  background: var(--color-bg-light);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  margin-top: var(--spacing-lg);
}

.file-name {
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: 5px;
}

.file-size {
  font-size: var(--font-size-md);
  color: var(--color-text-muted);
}
</style>
