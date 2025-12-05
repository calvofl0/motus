<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>⚙️ Add Custom Remote</template>
    <template #body>
      <p class="method-intro">Choose how you want to configure your custom remote:</p>
      <div
        ref="containerRef"
        tabindex="0"
        @keydown="handleKeydown"
        class="method-container"
      >
        <div
          ref="wizardOption"
          @click="selectMethod('wizard')"
          :style="getOptionStyle(0)"
          @mouseenter="hoveredIndex = 0"
          @mouseleave="hoveredIndex = -1"
          class="method-option"
        >
          <strong class="method-title">🧙 Wizard</strong>
          <small class="method-desc">Step-by-step configuration</small>
        </div>

        <div
          ref="manualOption"
          @click="selectMethod('manual')"
          :style="getOptionStyle(1)"
          @mouseenter="hoveredIndex = 1"
          @mouseleave="hoveredIndex = -1"
          class="method-option"
        >
          <strong class="method-title">⚡ Manual Configuration</strong>
          <small class="method-desc">For experts: edit rclone config directly</small>
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
const selectedIndex = ref(-1)
const hoveredIndex = ref(-1)
const methods = ['wizard', 'manual']

function selectMethod(method) {
  emit('method-selected', method)
  emit('update:modelValue', false)
}

function getOptionStyle(index) {
  const isSelected = selectedIndex.value === index && selectedIndex.value !== -1
  const isHovered = hoveredIndex.value === index

  return {
    border: isSelected ? '2px solid var(--color-primary)' : '1px solid var(--color-border)',
    background: (isSelected || isHovered) ? 'var(--color-bg-primary-light)' : 'var(--color-bg-white)'
  }
}

function handleKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (selectedIndex.value === -1) {
      selectedIndex.value = 0
    } else {
      selectedIndex.value = (selectedIndex.value + 1) % methods.length
    }
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (selectedIndex.value === -1) {
      selectedIndex.value = methods.length - 1
    } else {
      selectedIndex.value = (selectedIndex.value - 1 + methods.length) % methods.length
    }
  } else if (event.key === 'Enter') {
    event.preventDefault()
    if (selectedIndex.value !== -1) {
      selectMethod(methods[selectedIndex.value])
    }
  }
}

// Auto-focus container when modal opens
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    selectedIndex.value = -1
    await nextTick()
    setTimeout(() => {
      if (containerRef.value) {
        containerRef.value.focus()
      }
    }, 100)
  }
})
</script>

<style scoped>
.method-intro {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-secondary);
}

.method-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  outline: none;
}

.method-option {
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-fast);
}

.method-title {
  display: block;
  margin-bottom: 4px;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}

.method-desc {
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
}
</style>
