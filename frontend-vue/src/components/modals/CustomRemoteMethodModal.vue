<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>⚙️ Add Custom Remote</template>
    <template #body>
      <p style="margin-bottom: 15px; color: #666;">Choose how you want to configure your custom remote:</p>
      <div style="display: flex; flex-direction: column; gap: 10px;">
        <div
          @click="selectMethod('wizard')"
          style="padding: 16px; border: 1px solid #ddd; background: white; border-radius: 6px; cursor: pointer; transition: all 0.2s;"
          @mouseenter="$event.currentTarget.style.background = '#e7f3ff'; $event.currentTarget.style.borderColor = '#007bff'"
          @mouseleave="$event.currentTarget.style.background = 'white'; $event.currentTarget.style.borderColor = '#ddd'"
        >
          <strong style="display: block; margin-bottom: 4px; font-size: 16px;">🧙 Wizard</strong>
          <small style="color: #666;">Step-by-step configuration</small>
        </div>

        <div
          @click="selectMethod('manual')"
          style="padding: 16px; border: 1px solid #ddd; background: white; border-radius: 6px; cursor: pointer; transition: all 0.2s;"
          @mouseenter="$event.currentTarget.style.background = '#e7f3ff'; $event.currentTarget.style.borderColor = '#007bff'"
          @mouseleave="$event.currentTarget.style.background = 'white'; $event.currentTarget.style.borderColor = '#ddd'"
        >
          <strong style="display: block; margin-bottom: 4px; font-size: 16px;">⚡ Manual Configuration</strong>
          <small style="color: #666;">For experts: edit rclone config directly</small>
        </div>
      </div>
    </template>
    <template #footer>
      <!-- No footer buttons - selection closes the modal -->
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'

defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'method-selected'])

function selectMethod(method) {
  emit('method-selected', method)
  emit('update:modelValue', false)
}
</script>

<style scoped>
/* Styles are inline for this component */
</style>
