<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="false"
  >
    <template #header>📤 Uploading Files</template>
    <template #body>
      <div class="upload-content">
        <div class="upload-message">
          {{ message }}
        </div>
        <div class="progress-bar-container">
          <div class="progress-bar" :style="{ width: `${progress}%` }">
            <span class="progress-text">{{ progress }}%</span>
          </div>
        </div>
        <div class="upload-details">
          {{ details }}
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="$emit('cancel')" :disabled="!canCancel" class="btn btn-danger">
        Cancel
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

defineProps({
  modelValue: Boolean,
  message: {
    type: String,
    default: 'Preparing upload...'
  },
  progress: {
    type: Number,
    default: 0
  },
  details: {
    type: String,
    default: ''
  },
  canCancel: {
    type: Boolean,
    default: true
  }
})

defineEmits(['update:modelValue', 'cancel'])
</script>

<style scoped>
.upload-content {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
}

.upload-message {
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--spacing-sm);
}

.progress-bar-container {
  background: var(--color-border-lighter);
  border-radius: var(--radius-sm);
  height: 24px;
  overflow: hidden;
  position: relative;
}

.progress-bar {
  background: linear-gradient(90deg, var(--color-success), #20c997);
  height: 100%;
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.progress-text {
  color: white;
  font-weight: var(--font-weight-bold);
  font-size: var(--font-size-sm);
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  text-shadow: 0 0 3px rgba(0, 0, 0, 0.3);
}

.upload-details {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-top: var(--spacing-xs);
}
</style>
