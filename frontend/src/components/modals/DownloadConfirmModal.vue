<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="true"
  >
    <template #header>📥 Download File</template>
    <template #body>
      <div style="margin-bottom: 15px; color: #333;">
        <div style="font-weight: 500; margin-bottom: 10px; font-size: 16px;">
          Do you want to download this file?
        </div>
        <div style="background: #f5f5f5; padding: 12px; border-radius: 6px; margin-top: 15px;">
          <div style="font-weight: 500; color: #555; margin-bottom: 5px;">{{ fileName }}</div>
          <div style="font-size: 13px; color: #777;">Size: {{ fileSize }}</div>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="$emit('cancel')" style="background: #6c757d;">
        Cancel
      </button>
      <button @click="$emit('confirm')" style="background: #28a745;">
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
