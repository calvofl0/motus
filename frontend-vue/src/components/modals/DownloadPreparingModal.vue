<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="false"
  >
    <template #header>📥 Preparing Download</template>
    <template #body>
      <div style="margin-bottom: 15px; color: #333; text-align: center;">
        <div style="font-weight: 500; margin-bottom: 20px; font-size: 16px;">
          {{ message }}
        </div>

        <!-- Spinner animation -->
        <div style="margin: 20px auto; width: 50px; height: 50px;">
          <div class="spinner"></div>
        </div>

        <div style="font-size: 12px; color: #666; margin-top: 15px;">
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
.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #28a745;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
