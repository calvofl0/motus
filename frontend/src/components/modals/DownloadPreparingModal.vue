<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="false"
  >
    <template #header>📥 Preparing Download</template>
    <template #body>
      <div class="download-preparing-content">
        <div class="message">
          {{ message }}
        </div>

        <!-- Spinner animation -->
        <div class="spinner-container">
          <div class="spinner"></div>
        </div>

        <div class="wait-message">
          Please wait while we prepare your download...
        </div>
      </div>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

defineProps({
  modelValue: Boolean,
  message: {
    type: String,
    default: 'Downloading file from remote server...'
  }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.download-preparing-content {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
  text-align: center;
}

.message {
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--spacing-xl);
  font-size: var(--font-size-lg);
}

.spinner-container {
  margin: var(--spacing-xl) auto;
  width: 50px;
  height: 50px;
}

.spinner {
  border: 4px solid var(--color-bg-light);
  border-top: 4px solid var(--color-success);
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
}

.wait-message {
  font-size: var(--font-size-sm);
  color: var(--color-text-tertiary);
  margin-top: var(--spacing-lg);
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
