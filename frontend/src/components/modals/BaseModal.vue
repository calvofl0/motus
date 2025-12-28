<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="modelValue"
        class="modal-overlay"
        @click.self="handleOverlayClick"
        @keydown.esc.stop="close"
        @keydown.enter="handleEnter"
        @keydown="handleKeyDown"
        tabindex="-1"
        ref="overlayRef"
      >
        <div class="modal-dialog" :class="sizeClass" :style="modalStyle">
          <div class="modal-header">
            <h3 v-if="!$slots.header">{{ title }}</h3>
            <slot v-else name="header"></slot>
            <button class="modal-close" @click="close" aria-label="Close">&times;</button>
          </div>
          <div class="modal-body" ref="modalBodyRef">
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
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { useModalStack } from '../../stores/modalStack'

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
    validator: (value) => ['small', 'medium', 'large', 'xlarge'].includes(value)
  },
  closeOnOverlayClick: {
    type: Boolean,
    default: true
  },
  customWidth: {
    type: String,
    default: null
  }
})

const emit = defineEmits(['update:modelValue', 'close', 'confirm', 'keydown'])

const overlayRef = ref(null)
const modalBodyRef = ref(null)

// Modal Stack Integration
// Each modal instance gets a unique ID to track its position in the stack
const modalId = Symbol('modal')
const modalStack = useModalStack()

// Check if this modal is the topmost (active) modal
const isTopModal = computed(() => modalStack.isTopModal(modalId))

// Reactive window width for custom width calculations
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1600)

const updateWindowWidth = () => {
  if (typeof window !== 'undefined') {
    windowWidth.value = window.innerWidth
  }
}

// Add window resize listener for customWidth modals
onMounted(() => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', updateWindowWidth)
  }
})

onUnmounted(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', updateWindowWidth)
  }
})

const sizeClass = computed(() => {
  // If customWidth is provided, don't apply size class to avoid conflicts
  if (props.customWidth) {
    return ''
  }
  return `modal-${props.size}`
})

// Calculate maxWidth for customWidth case
const modalStyle = computed(() => {
  if (!props.customWidth) {
    return {}
  }

  // Calculate max width: min(80vw, 1400px) using reactive windowWidth
  const maxWidthVw = windowWidth.value * 0.8
  const maxWidth = Math.min(maxWidthVw, 1400)

  return {
    width: props.customWidth,
    maxWidth: `${maxWidth}px`
  }
})

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

function handleKeyDown(event) {
  // Only handle events if this modal is the topmost (active) modal
  if (!isTopModal.value) return

  // Handle arrow keys for scrolling
  if (!modalBodyRef.value) return

  // Find the scrollable element (either modal-body itself or a child with overflow)
  const scrollableElement = findScrollableElement(modalBodyRef.value)
  if (!scrollableElement) return

  const scrollAmount = 40 // pixels to scroll per key press

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    scrollableElement.scrollTop += scrollAmount
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    scrollableElement.scrollTop -= scrollAmount
  } else if (event.key === 'PageDown') {
    event.preventDefault()
    scrollableElement.scrollTop += scrollableElement.clientHeight
  } else if (event.key === 'PageUp') {
    event.preventDefault()
    scrollableElement.scrollTop -= scrollableElement.clientHeight
  } else if (event.key === 'Home') {
    event.preventDefault()
    scrollableElement.scrollTop = 0
  } else if (event.key === 'End') {
    event.preventDefault()
    scrollableElement.scrollTop = scrollableElement.scrollHeight
  }
}

// Find the first scrollable element (element with scrollbar)
function findScrollableElement(element) {
  // Check if the element itself is scrollable
  if (element.scrollHeight > element.clientHeight) {
    const overflowY = window.getComputedStyle(element).overflowY
    if (overflowY === 'auto' || overflowY === 'scroll') {
      return element
    }
  }

  // Recursively check children for scrollable elements
  for (const child of element.children) {
    // First check if this child is directly scrollable
    if (child.scrollHeight > child.clientHeight) {
      const overflowY = window.getComputedStyle(child).overflowY
      if (overflowY === 'auto' || overflowY === 'scroll') {
        return child
      }
    }
    // Recursively check nested children
    const scrollableChild = findScrollableElement(child)
    // Only return if we actually found a scrollable element (not the fallback)
    if (scrollableChild && scrollableChild.scrollHeight > scrollableChild.clientHeight) {
      const overflowY = window.getComputedStyle(scrollableChild).overflowY
      if (overflowY === 'auto' || overflowY === 'scroll') {
        return scrollableChild
      }
    }
  }

  // If no scrollable child found, return the original element as fallback
  return element
}

// Focus overlay when modal opens to capture keyboard events
// Also manage modal stack (push/pop)
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    // Push this modal onto the stack
    modalStack.pushModal(modalId)

    await nextTick()
    // Reset scroll position to top
    if (modalBodyRef.value) {
      modalBodyRef.value.scrollTop = 0
    }
    if (overlayRef.value) {
      // Always focus overlay to capture ESC and other keyboard events
      overlayRef.value.focus()
    }
  } else {
    // Pop this modal from the stack
    modalStack.popModal(modalId)
  }
})

// Expose method to focus the overlay (useful when child modals close)
function focusOverlay() {
  if (overlayRef.value) {
    overlayRef.value.focus()
  }
}

defineExpose({
  focusOverlay,
  isTopModal
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

.modal-xlarge {
  width: 80vw;
  max-width: 1400px;
}

.modal-header {
  padding: var(--spacing-xl);
  margin-bottom: 0;
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
