<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="false"
  >
    <template #header>📤 Uploading Files</template>
    <template #body>
      <div style="margin-bottom: 15px; color: #333;">
        <div style="font-weight: 500; margin-bottom: 10px;">
          {{ message }}
        </div>
        <div style="background: #f0f0f0; border-radius: 10px; height: 24px; overflow: hidden; position: relative;">
          <div
            :style="{
              background: 'linear-gradient(90deg, #28a745, #20c997)',
              height: '100%',
              width: `${progress}%`,
              transition: 'width 0.3s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }"
          >
            <span style="color: white; font-weight: bold; font-size: 12px; position: absolute; left: 50%; transform: translateX(-50%); text-shadow: 0 0 3px rgba(0,0,0,0.3);">
              {{ progress }}%
            </span>
          </div>
        </div>
        <div style="font-size: 12px; color: #666; margin-top: 8px;">
          {{ details }}
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="$emit('cancel')" :disabled="!canCancel" style="background: #dc3545;">
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
