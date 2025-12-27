<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    @confirm="$emit('update:modelValue', false)"
    :title="title"
    size="large"
    class="keyboard-shortcuts-modal"
    :style="{ '--modal-dynamic-width': modalWidth }"
  >
    <div class="shortcuts-container" :style="{ gridTemplateColumns: gridTemplateColumns }">
      <!-- Render each section -->
      <div v-for="section in displayedSections" :key="section.id" class="shortcut-section">
        <h4>{{ section.title }}</h4>
        <div class="shortcut-list">
          <div v-for="(shortcut, index) in section.shortcuts" :key="index" class="shortcut-item">
            <div class="shortcut-keys">
              <kbd v-for="(key, keyIndex) in shortcut.keys" :key="keyIndex">{{ key }}</kbd>
            </div>
            <span v-html="shortcut.description"></span>
          </div>
        </div>
      </div>
    </div>
  </BaseModal>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import BaseModal from './BaseModal.vue'
import { shortcutSections } from '../../data/shortcutSections'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  title: {
    type: String,
    default: 'Keyboard Shortcuts'
  },
  sectionIds: {
    type: Array,
    required: true
    // Array of section IDs to display (e.g., ['file-navigation', 'common-modal'])
  }
})

defineEmits(['update:modelValue'])

// Get sections to display based on sectionIds prop
const displayedSections = computed(() => {
  return props.sectionIds
    .map(id => shortcutSections[id])
    .filter(section => section !== undefined)
})

// Number of sections (for column calculation)
const sectionCount = computed(() => displayedSections.value.length)

// Constants for layout calculation
const MIN_COLUMN_WIDTH = 280 // Prevent content overflow
const MAX_COLUMN_WIDTH = 400 // Maximum reasonable column width
const MODAL_MAX_WIDTH_RATIO = 0.8 // Modal takes 80% of window width
const MIN_MODAL_WIDTH_RATIO = 0.25 // Columns should take at least 25% of window width

// Reactive window width for responsive calculations
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1600)

// Update window width on resize
const updateWidth = () => {
  windowWidth.value = window.innerWidth
}

onMounted(() => {
  window.addEventListener('resize', updateWidth)
})

onUnmounted(() => {
  window.removeEventListener('resize', updateWidth)
})

// Calculate optimal number of columns using the algorithm
const optimalColumnCount = computed(() => {
  const itemCount = sectionCount.value
  if (itemCount === 0) return 1

  // Calculate modal max width (80% of window or 1400px max)
  const modalMaxWidth = Math.min(windowWidth.value * MODAL_MAX_WIDTH_RATIO, 1400)

  // maxColumnsBeforeOverflow: Maximum columns that fit without content overflow
  const maxColumnsBeforeOverflow = Math.floor(modalMaxWidth / MIN_COLUMN_WIDTH)

  // columnsToFitAllContent: Minimum columns needed to avoid vertical scrolling
  // For simplicity, we use a reasonable upper limit of 6 columns
  const columnsToFitAllContent = 6

  // upperBound: min(columnsToFitAllContent, maxColumnsBeforeOverflow)
  const upperBound = Math.min(columnsToFitAllContent, maxColumnsBeforeOverflow)

  // minColumnsForMinWidth: Minimum columns for 25% window width constraint
  // Use MIN_COLUMN_WIDTH so we don't force modal wider than necessary
  const minModalWidth = windowWidth.value * MIN_MODAL_WIDTH_RATIO
  const minColumnsForMinWidth = Math.max(1, Math.ceil(minModalWidth / MIN_COLUMN_WIDTH))

  // Search range: [minColumnsForMinWidth, upperBound]
  // First pass: find the minimum number of empty cells
  let minEmptyCells = Infinity
  const emptyCellsMap = new Map()

  for (let cols = minColumnsForMinWidth; cols <= upperBound; cols++) {
    // Calculate empty cells in last row
    // Formula: cols - (itemCount % cols) when itemCount % cols != 0
    // Simplified: (cols - (itemCount % cols)) % cols
    const emptyCells = (cols - (itemCount % cols)) % cols
    emptyCellsMap.set(cols, emptyCells)
    minEmptyCells = Math.min(minEmptyCells, emptyCells)
  }

  // Second pass: accept columns with emptyCells = k or k+1
  // This allows one extra empty cell to get more columns (shorter modal)
  let bestColumnCount = minColumnsForMinWidth
  for (let cols = minColumnsForMinWidth; cols <= upperBound; cols++) {
    const emptyCells = emptyCellsMap.get(cols)
    // Accept if emptyCells is k or k+1, choose greatest column count
    if (emptyCells === minEmptyCells || emptyCells === minEmptyCells + 1) {
      bestColumnCount = cols // Always update to get the greatest
    }
  }

  return bestColumnCount
})

// Generate grid-template-columns CSS
const gridTemplateColumns = computed(() => {
  return `repeat(${optimalColumnCount.value}, 1fr)`
})

// Calculate actual modal width needed based on column count
// This allows the modal to be smaller than 80vw when content doesn't need it
const modalWidth = computed(() => {
  const cols = optimalColumnCount.value
  const gap = 24 // var(--spacing-lg) is typically 24px
  const padding = 48 // Modal body padding (24px each side)

  // Calculate width needed: columns * min width + gaps between columns + padding
  const neededWidth = cols * MIN_COLUMN_WIDTH + (cols - 1) * gap + padding

  // Apply max constraints: 80vw or 1400px
  const maxWidth = Math.min(windowWidth.value * MODAL_MAX_WIDTH_RATIO, 1400)

  // Return the smaller of needed width or max width
  const actualWidth = Math.min(neededWidth, maxWidth)

  return `${actualWidth}px`
})
</script>

<style scoped>
/* Override modal width to use dynamic width based on content */
.keyboard-shortcuts-modal :deep(.modal-content) {
  width: var(--modal-dynamic-width);
  max-width: min(80vw, 1400px);
}

.shortcuts-container {
  display: grid;
  /* grid-template-columns set dynamically via :style binding */
  gap: var(--spacing-lg);
}

.shortcut-section h4 {
  margin: 0 0 var(--spacing-md) 0;
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: var(--spacing-xs);
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.shortcut-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
}

.shortcut-keys {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  align-items: center;
}

.shortcut-item kbd {
  display: inline-block;
  padding: 2px 6px;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  min-width: 24px;
  text-align: center;
}

.shortcut-item span {
  flex: 1;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  line-height: 1.5;
}

/* Allow HTML in descriptions (for nested <kbd> tags) */
.shortcut-item span :deep(kbd) {
  display: inline-block;
  padding: 2px 6px;
  font-family: var(--font-family-mono);
  font-size: var(--font-size-xs);
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  min-width: 24px;
  text-align: center;
}
</style>
