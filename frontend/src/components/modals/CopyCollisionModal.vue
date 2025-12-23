<template>
  <BaseModal
    v-model="isOpen"
    title="⚠️ Destination Files Already Exist"
    size="medium"
    @close="handleClose"
  >
    <p class="warning-text">
      Some or all of the files you're trying to copy already exist at the destination.
      Choose how to proceed:
    </p>

    <div class="file-list">
      <div v-for="(file, index) in files" :key="index" class="file-item">
        • {{ file }}
      </div>
    </div>

    <div class="path-info">
      <div class="path-row source-path">
        <span class="path-label">From:</span>
        <span class="path-value">{{ sourcePath }}</span>
      </div>
      <div class="path-row dest-path">
        <span class="path-label">To:</span>
        <span class="path-value">{{ destPath }}</span>
      </div>
    </div>

    <div class="options-container">
      <button
        class="option-btn option-check"
        :class="{ 'option-selected': selectedOption === 0 }"
        @click="selectOption(0)"
      >
        <div class="option-icon">🔍</div>
        <div class="option-content">
          <div class="option-title">Check Integrity</div>
          <div class="option-description">Verify files match without modifying anything</div>
        </div>
      </button>

      <button
        class="option-btn option-resume"
        :class="{ 'option-selected': selectedOption === 1 }"
        @click="selectOption(1)"
      >
        <div class="option-icon">▶️</div>
        <div class="option-content">
          <div class="option-title">Resume Copy</div>
          <div class="option-description">
            Copy missing and modified files.<br>
            <span class="danger-text">Different files will be overwritten.</span>
          </div>
        </div>
      </button>

      <button
        v-if="showSyncOption"
        class="option-btn option-sync"
        :class="{ 'option-selected': selectedOption === 2 }"
        @click="selectOption(2)"
      >
        <div class="option-icon">👥</div>
        <div class="option-content">
          <div class="option-title">Sync</div>
          <div class="option-description">
            Make destination identical to source.<br>
            <span class="danger-text">Deletes extra files at destination.</span>
          </div>
        </div>
      </button>
    </div>

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="btn btn-primary" @click="handleContinue">
        Continue
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  files: {
    type: Array,
    default: () => []
  },
  sourcePath: {
    type: String,
    default: ''
  },
  destPath: {
    type: String,
    default: ''
  },
  showSyncOption: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'check-integrity', 'resume-copy', 'sync', 'cancel'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

// Keyboard navigation: 0 = Check Integrity (default), 1 = Resume Copy, 2 = Sync
const selectedOption = ref(0)

// Compute available options based on showSyncOption
const availableOptions = computed(() => {
  const options = ['check', 'resume']
  if (props.showSyncOption) {
    options.push('sync')
  }
  return options
})

// Reset selected option when modal opens
watch(isOpen, (newVal) => {
  if (newVal) {
    selectedOption.value = 0 // Default to Check Integrity
  }
})

function handleKeyDown(event) {
  if (!isOpen.value) return

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    selectedOption.value = (selectedOption.value + 1) % availableOptions.value.length
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    selectedOption.value = (selectedOption.value - 1 + availableOptions.value.length) % availableOptions.value.length
  } else if (event.key === 'Enter') {
    event.preventDefault()
    executeSelectedOption()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    handleClose()
  }
}

function executeSelectedOption() {
  const option = availableOptions.value[selectedOption.value]
  if (option === 'check') {
    handleCheckIntegrity()
  } else if (option === 'resume') {
    handleResumeCopy()
  } else if (option === 'sync') {
    handleSync()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})

function selectOption(index) {
  selectedOption.value = index
}

function handleContinue() {
  executeSelectedOption()
}

function handleCheckIntegrity() {
  emit('check-integrity')
  isOpen.value = false
}

function handleResumeCopy() {
  emit('resume-copy')
  isOpen.value = false
}

function handleSync() {
  emit('sync')
  isOpen.value = false
}

function handleClose() {
  emit('cancel')
  isOpen.value = false
}
</script>

<script>
export default {
  name: 'CopyCollisionModal'
}
</script>

<style scoped>
.warning-text {
  margin: 0 0 var(--spacing-lg) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
}

.file-list {
  max-height: 150px;
  overflow-y: auto;
  padding: var(--spacing-xs) 0;
  margin: var(--spacing-xs) 0;
}

.file-item {
  padding: 4px var(--spacing-xs);
  font-family: monospace;
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.path-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  padding: var(--spacing-md) 0;
  margin-bottom: var(--spacing-md);
  border-top: 1px solid var(--color-border-lighter);
  border-bottom: 1px solid var(--color-border-lighter);
}

.path-row {
  display: flex;
  gap: var(--spacing-sm);
  font-size: var(--font-size-md);
  padding: var(--spacing-sm) var(--spacing-md);
  border-radius: var(--radius-md);
  transition: var(--transition-fast);
}

.path-row.source-path {
  background: var(--color-primary-light);
  border-left: 3px solid var(--color-primary);
}

.path-row.dest-path {
  background: var(--color-success-light);
  border-left: 3px solid var(--color-success);
}

.path-label {
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-secondary);
  min-width: 50px;
}

.path-value {
  font-family: monospace;
  color: var(--color-text-primary);
  word-break: break-all;
  flex: 1;
}

.options-container {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  margin-top: var(--spacing-md);
}

.option-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--color-bg-primary);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: var(--transition-fast);
  text-align: left;
  width: 100%;
}

.option-btn:hover {
  border-color: var(--color-primary);
  background: var(--color-bg-secondary);
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.option-btn:active {
  transform: translateY(0);
}

.option-btn.option-selected {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
}

.option-icon {
  font-size: 32px;
  line-height: 1;
  flex-shrink: 0;
}

.option-content {
  flex: 1;
}

.option-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.option-description {
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
}

.warning-subtext {
  color: var(--color-warning);
  font-weight: var(--font-weight-medium);
}

.danger-text {
  color: var(--color-danger);
  font-weight: var(--font-weight-semibold);
  display: inline-block;
  margin-top: 0.5em;
}
</style>
