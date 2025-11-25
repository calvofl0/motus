<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>⚙️ Add Custom Remote</template>
    <template #body>
      <p style="margin-bottom: 15px; color: #666;">Choose how you want to configure your custom remote:</p>
      <div
        ref="containerRef"
        tabindex="0"
        @keydown="handleKeydown"
        style="display: flex; flex-direction: column; gap: 10px; outline: none;"
      >
        <div
          ref="wizardOption"
          @click="selectMethod('wizard')"
          :style="getOptionStyle(0)"
          @mouseenter="hoveredIndex = 0"
          @mouseleave="hoveredIndex = -1"
        >
          <strong style="display: block; margin-bottom: 4px; font-size: 16px;">🧙 Wizard</strong>
          <small style="color: #666;">Step-by-step configuration</small>
        </div>

        <div
          ref="manualOption"
          @click="selectMethod('manual')"
          :style="getOptionStyle(1)"
          @mouseenter="hoveredIndex = 1"
          @mouseleave="hoveredIndex = -1"
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
import { ref, watch, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'method-selected'])

const containerRef = ref(null)
const selectedIndex = ref(0)
const hoveredIndex = ref(-1)
const methods = ['wizard', 'manual']

function selectMethod(method) {
  emit('method-selected', method)
  emit('update:modelValue', false)
}

function getOptionStyle(index) {
  const isSelected = selectedIndex.value === index
  const isHovered = hoveredIndex.value === index

  return {
    padding: '16px',
    border: isSelected ? '2px solid #007bff' : '1px solid #ddd',
    background: (isSelected || isHovered) ? '#e7f3ff' : 'white',
    borderRadius: '6px',
    cursor: 'pointer',
    transition: 'all 0.2s'
  }
}

function handleKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    selectedIndex.value = (selectedIndex.value + 1) % methods.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    selectedIndex.value = (selectedIndex.value - 1 + methods.length) % methods.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    selectMethod(methods[selectedIndex.value])
  }
}

// Auto-focus container when modal opens
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    selectedIndex.value = 0
    await nextTick()
    if (containerRef.value) {
      containerRef.value.focus()
    }
  }
})
</script>

<style scoped>
/* Styles are inline for this component */
</style>
