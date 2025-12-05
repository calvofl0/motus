<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-overlay"
        @click.self="handleOverlayClick"
        @keydown.esc.stop="close"
        @keydown.enter="handleEnter"
        tabindex="-1"
        ref="overlayRef"
      >
        <div class="modal-dialog" :class="sizeClass">
          <div class="modal-header">
            <h3 v-if="!$slots.header">{{ title }}</h3>
            <slot v-else name="header"></slot>
            <button class="modal-close" @click="close" aria-label="Close">&times;</button>
          </div>
          <div class="modal-body">
            <slot v-if="!$slots.body"></slot>
            <slot v-else name="body"></slot>
          </div>
          <div class="modal-footer" v-if="$slots.footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  title: {
    type: String,
    default: ''
  },
  size: {
    type: String,
    default: 'medium',
    validator: (value) => ['small', 'medium', 'large'].includes(value)
  },
  closeOnOverlayClick: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['update:modelValue', 'close', 'confirm'])

const overlayRef = ref(null)
const sizeClass = computed(() => `modal-${props.size}`)

function close() {
  emit('update:modelValue', false)
  emit('close')
}

function handleOverlayClick() {
  if (props.closeOnOverlayClick) {
    close()
  }
}

function handleEnter(event) {
  // Don't trigger if focus is on a textarea
  if (event.target.tagName === 'TEXTAREA') {
    return
  }
  // Emit confirm event for parent to handle
  emit('confirm')
}

// Focus overlay when modal opens to capture keyboard events
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    await nextTick()
    if (overlayRef.value) {
      // Always focus overlay to capture ESC and other keyboard events
      overlayRef.value.focus()
    }
  }
})
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: var(--modal-overlay-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  overflow-y: auto;
  outline: none;
}

.modal-dialog {
  background: var(--color-bg-white);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  margin: var(--spacing-xl);
}

.modal-small {
  width: 400px;
  max-width: 90vw;
}

.modal-medium {
  width: 600px;
  max-width: 90vw;
}

.modal-large {
  width: 900px;
  max-width: 95vw;
}

.modal-header {
  padding: var(--spacing-xl);
  border-bottom: 1px solid var(--color-border-light);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.modal-header h3 {
  margin: 0;
  font-size: var(--font-size-xxl);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.modal-close {
  background: none;
  border: none;
  font-size: 32px;
  line-height: 1;
  color: var(--color-text-muted);
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 0.2s;
}

.modal-close:hover {
  color: var(--color-text-primary);
}

.modal-body {
  padding: var(--spacing-xl);
  overflow-y: auto;
  flex: 1 1 auto;
  min-height: 0;
}

.modal-footer {
  padding: var(--spacing-lg) var(--spacing-xl);
  border-top: 1px solid var(--color-border-light);
  display: flex;
  gap: var(--spacing-sm);
  justify-content: flex-end;
  flex-shrink: 0;
  background: var(--color-bg-white);
}

/* Transition */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.2s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-active .modal-dialog,
.modal-leave-active .modal-dialog {
  transition: transform 0.2s ease;
}

.modal-enter-from .modal-dialog,
.modal-leave-to .modal-dialog {
  transform: scale(0.95);
}
</style>
