<template>
  <div class="modal-table-container">
    <!-- Loading state -->
    <div v-if="loading" class="table-message">{{ loadingMessage }}</div>

    <!-- Empty state -->
    <div v-else-if="items.length === 0" class="table-message">{{ emptyMessage }}</div>

    <!-- Table -->
    <div v-else class="modal-table">
      <!-- Header -->
      <div class="table-header" :style="{ gridTemplateColumns: gridTemplateColumns }">
        <div v-for="(column, index) in columns" :key="index">
          <slot :name="`header-${column.key}`" :column="column">
            {{ column.header }}
          </slot>
        </div>
      </div>

      <!-- Body -->
      <div class="table-body" ref="tableBodyRef">
        <div
          v-for="(item, index) in items"
          :key="getRowKey(item, index)"
          class="table-row"
          :class="{ 'selected-row': index === selectedIndex }"
          :style="{ gridTemplateColumns: gridTemplateColumns }"
          @click="handleRowClick(item, index)"
        >
          <div v-for="column in columns" :key="column.key" :class="`col-${column.key}`">
            <slot :name="`cell-${column.key}`" :item="item" :index="index">
              {{ getCellValue(item, column.key) }}
            </slot>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, onUnmounted } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    required: true
  },
  columns: {
    type: Array,
    required: true
    // Format: [{ key: 'id', header: 'ID' }, ...]
  },
  selectedIndex: {
    type: Number,
    default: -1
  },
  gridTemplateColumns: {
    type: String,
    required: true
    // E.g., "50px 60px 1fr 1fr 100px 40px"
  },
  rowKey: {
    type: [String, Function],
    default: null
    // If string, use item[rowKey]. If function, call it with (item, index)
  },
  loading: {
    type: Boolean,
    default: false
  },
  loadingMessage: {
    type: String,
    default: 'Loading...'
  },
  emptyMessage: {
    type: String,
    default: 'No items found.'
  },
  // Allow parent to disable default keyboard handling for custom implementation
  disableDefaultKeyboard: {
    type: Boolean,
    default: false
  },
  // Parent modal's isTopModal value - used to check if parent is the top modal
  // When passed from template, Vue unwraps refs so this will be a boolean
  parentIsTopModal: {
    type: Boolean,
    default: null
  }
})

const emit = defineEmits(['update:selectedIndex', 'row-click', 'keydown'])

const tableBodyRef = ref(null)

function getRowKey(item, index) {
  if (typeof props.rowKey === 'function') {
    return props.rowKey(item, index)
  }
  if (typeof props.rowKey === 'string') {
    return item[props.rowKey]
  }
  return index
}

function getCellValue(item, key) {
  return item[key] ?? ''
}

function handleRowClick(item, index) {
  emit('update:selectedIndex', index)
  emit('row-click', item, index)
}

function scrollToSelectedRow() {
  if (!tableBodyRef.value || props.selectedIndex < 0) return

  const rows = tableBodyRef.value.children
  if (rows[props.selectedIndex]) {
    rows[props.selectedIndex].scrollIntoView({
      block: 'nearest',
      behavior: 'smooth'
    })
  }
}

// Keyboard navigation
function handleKeyDown(event) {
  // Check if parent modal is the top modal (if parentIsTopModal is provided)
  console.log('[ModalTable] handleKeyDown called:', event.key, '| parentIsTopModal:', props.parentIsTopModal, '| typeof:', typeof props.parentIsTopModal)

  // Only check if parentIsTopModal was explicitly provided (not null/undefined)
  if (props.parentIsTopModal !== null && props.parentIsTopModal !== undefined) {
    // If parent modal is not the top modal, don't handle keyboard events
    if (!props.parentIsTopModal) {
      console.log('[ModalTable] Ignoring keydown (parent not top):', event.key)
      return
    }
    console.log('[ModalTable] Handling keydown (parent is top):', event.key)
  } else {
    console.log('[ModalTable] No parentIsTopModal provided, handling keydown:', event.key)
  }

  if (props.disableDefaultKeyboard) {
    // Let parent handle everything
    emit('keydown', event)
    return
  }

  // Always emit keydown for parent to potentially handle custom shortcuts
  emit('keydown', event)

  // If parent prevented default, don't do anything else
  if (event.defaultPrevented) return

  if (props.items.length === 0) return

  // Arrow Down - Select next item
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    event.stopPropagation()
    if (props.selectedIndex < props.items.length - 1) {
      emit('update:selectedIndex', props.selectedIndex + 1)
      nextTick(() => scrollToSelectedRow())
    }
  }
  // Arrow Up - Select previous item
  else if (event.key === 'ArrowUp') {
    event.preventDefault()
    event.stopPropagation()
    if (props.selectedIndex > 0) {
      emit('update:selectedIndex', props.selectedIndex - 1)
      nextTick(() => scrollToSelectedRow())
    } else if (props.selectedIndex === -1 && props.items.length > 0) {
      emit('update:selectedIndex', 0)
      nextTick(() => scrollToSelectedRow())
    }
  }
  // PageDown - Scroll down by viewport height
  else if (event.key === 'PageDown') {
    event.preventDefault()
    event.stopPropagation()
    if (tableBodyRef.value) {
      tableBodyRef.value.scrollTop += tableBodyRef.value.clientHeight
    }
  }
  // PageUp - Scroll up by viewport height
  else if (event.key === 'PageUp') {
    event.preventDefault()
    event.stopPropagation()
    if (tableBodyRef.value) {
      tableBodyRef.value.scrollTop -= tableBodyRef.value.clientHeight
    }
  }
  // Home - Scroll to top
  else if (event.key === 'Home') {
    event.preventDefault()
    event.stopPropagation()
    if (tableBodyRef.value) {
      tableBodyRef.value.scrollTop = 0
    }
  }
  // End - Scroll to bottom
  else if (event.key === 'End') {
    event.preventDefault()
    event.stopPropagation()
    if (tableBodyRef.value) {
      tableBodyRef.value.scrollTop = tableBodyRef.value.scrollHeight
    }
  }
}

// Setup keyboard listener with capture phase
const isListening = ref(false)

function startKeyboardListener() {
  if (!isListening.value) {
    window.addEventListener('keydown', handleKeyDown, { capture: true })
    isListening.value = true
  }
}

function stopKeyboardListener() {
  if (isListening.value) {
    window.removeEventListener('keydown', handleKeyDown, { capture: true })
    isListening.value = false
  }
}

// Clean up listener when component is unmounted
onUnmounted(() => {
  stopKeyboardListener()
  console.log('[ModalTable] Component unmounted, listener cleaned up')
})

// Expose methods for parent components
defineExpose({
  startKeyboardListener,
  stopKeyboardListener,
  scrollToSelectedRow
})
</script>

<style scoped>
.modal-table-container {
  width: 100%;
}

.table-message {
  color: var(--color-text-secondary);
  text-align: center;
  padding: var(--spacing-xl);
}

.modal-table {
  width: 100%;
}

.table-header {
  display: grid;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) 0;
  background: var(--color-bg-secondary);
  border-bottom: 2px solid var(--color-border);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-tertiary);
  font-size: var(--font-size-sm);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.table-body {
  max-height: 50vh;
  overflow-y: auto;
}

.table-row {
  display: grid;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) 0;
  border-bottom: 1px solid var(--color-border-lighter);
  cursor: pointer;
  transition: var(--transition-fast);
  min-height: 44px;
  align-items: center;
}

.table-row:hover {
  background-color: var(--color-bg-light);
  border-left: 3px solid var(--color-primary);
}

.table-row.selected-row {
  background-color: var(--color-bg-primary-light);
  border-left: 3px solid var(--color-primary);
}

/* Column content styling */
.table-row > div {
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
}
</style>
