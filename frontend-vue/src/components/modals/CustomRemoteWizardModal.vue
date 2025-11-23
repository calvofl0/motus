<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="medium"
  >
    <template #header>
      {{ wizardStep === 1 ? '🧙 Create Custom Remote' : '⚙️ Configure Remote' }}
    </template>
    <template #body>
      <!-- Step 1: Remote name and type selection -->
      <div v-if="wizardStep === 1">
        <div style="margin-bottom: 15px;">
          <label style="display: block; margin-bottom: 5px; font-weight: 500;">Remote Name:</label>
          <input
            ref="remoteNameInput"
            type="text"
            v-model="remoteName"
            @keydown.enter="handleRemoteNameEnter"
            placeholder="e.g., my_remote"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          />
        </div>
        <div>
          <label style="display: block; margin-bottom: 5px; font-weight: 500;">Remote Type:</label>
          <select
            ref="remoteTypeSelect"
            v-model="remoteType"
            @keydown.enter="handleRemoteTypeEnter"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          >
            <option value="">-- Select a type --</option>
            <option v-for="provider in providers" :key="provider.name" :value="provider.name">
              {{ provider.name }} - {{ provider.description }}
            </option>
          </select>
        </div>
      </div>

      <!-- Step 2+: Dynamic question from rclone -->
      <div v-else-if="currentQuestion">
        <div style="margin-bottom: 15px;">
          <label style="display: block; margin-bottom: 5px; font-weight: 500;">
            {{ currentQuestion.name }}
            <span v-if="currentQuestion.required" style="color: red;">*</span>
          </label>
          <div v-if="currentQuestion.help" v-html="formatHelp(currentQuestion.help)" style="margin-bottom: 8px; color: #666; font-size: 14px;"></div>

          <!-- Password field -->
          <input
            v-if="currentQuestion.is_password"
            ref="answerInput"
            type="password"
            v-model="currentAnswer"
            @keydown.enter="handleAnswerEnter"
            :placeholder="getPlaceholder()"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          />

          <!-- Boolean field -->
          <select
            v-else-if="currentQuestion.type === 'bool'"
            ref="answerInput"
            v-model="currentAnswer"
            @keydown.enter="handleAnswerEnter"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          >
            <option value="">-- Select --</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>

          <!-- Integer field -->
          <input
            v-else-if="currentQuestion.type === 'int'"
            ref="answerInput"
            type="number"
            v-model="currentAnswer"
            @keydown.enter="handleAnswerEnter"
            :placeholder="getPlaceholder()"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          />

          <!-- Text field (default) -->
          <input
            v-else
            ref="answerInput"
            type="text"
            v-model="currentAnswer"
            @keydown.enter="handleAnswerEnter"
            :placeholder="getPlaceholder()"
            style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          />

          <!-- Examples if available -->
          <div v-if="currentQuestion.examples && currentQuestion.examples.length > 0" style="margin-top: 8px; font-size: 13px; color: #888;">
            <div>Examples:</div>
            <div v-for="(example, idx) in currentQuestion.examples" :key="idx" style="margin-left: 10px;">
              • {{ example.Value }} <span v-if="example.Help" style="color: #999;">({{ example.Help }})</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading state -->
      <div v-else-if="isProcessing" style="text-align: center; padding: 20px;">
        <div style="color: #666;">Processing...</div>
      </div>
    </template>
    <template #footer>
      <button @click="handleBack" class="btn-secondary">
        {{ wizardStep === 1 ? 'Cancel' : 'Back' }}
      </button>
      <button @click="handleNext" :disabled="!canProceed" class="btn-primary">
        {{ getNextButtonText() }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'
import { apiCall } from '../../services/api'

const props = defineProps({
  modelValue: Boolean
})

const emit = defineEmits(['update:modelValue', 'remote-created'])

// Step 1 state
const wizardStep = ref(1)
const providers = ref([])
const remoteName = ref('')
const remoteType = ref('')

// Step 2+ state
const sessionId = ref(null)
const currentQuestion = ref(null)
const currentAnswer = ref('')
const isProcessing = ref(false)

// Refs for inputs
const remoteNameInput = ref(null)
const remoteTypeSelect = ref(null)
const answerInput = ref(null)

// Computed
const canProceed = computed(() => {
  if (wizardStep.value === 1) {
    return remoteName.value.trim() && remoteType.value
  } else {
    // For subsequent steps, check if required field is filled
    if (currentQuestion.value?.required) {
      return currentAnswer.value.trim() !== ''
    }
    return true // Optional fields can be empty
  }
})

// Load providers on mount
onMounted(async () => {
  await loadProviders()
})

// Watch modal open/close
watch(() => props.modelValue, (isOpen) => {
  if (isOpen) {
    // Focus first input when modal opens
    nextTick(() => {
      if (wizardStep.value === 1 && remoteNameInput.value) {
        remoteNameInput.value.focus()
      }
    })
  } else {
    // Reset wizard when modal closes
    resetWizard()
  }
})

// Watch wizard step changes
watch(wizardStep, () => {
  nextTick(() => {
    // Focus appropriate input when step changes
    if (wizardStep.value === 1 && remoteNameInput.value) {
      remoteNameInput.value.focus()
    } else if (wizardStep.value > 1 && answerInput.value) {
      answerInput.value.focus()
    }
  })
})

async function loadProviders() {
  try {
    const data = await apiCall('/api/remotes/providers')
    providers.value = data.providers || []
  } catch (error) {
    console.error('Failed to load providers:', error)
    alert(`Failed to load providers: ${error.message}`)
  }
}

function resetWizard() {
  wizardStep.value = 1
  remoteName.value = ''
  remoteType.value = ''
  sessionId.value = null
  currentQuestion.value = null
  currentAnswer.value = ''
  isProcessing.value = false
}

function handleRemoteNameEnter() {
  if (remoteName.value.trim()) {
    // Move to type selection
    nextTick(() => {
      if (remoteTypeSelect.value) {
        remoteTypeSelect.value.focus()
      }
    })
  }
}

function handleRemoteTypeEnter() {
  if (canProceed.value) {
    handleNext()
  }
}

function handleAnswerEnter() {
  if (canProceed.value) {
    handleNext()
  }
}

async function handleNext() {
  if (!canProceed.value) return

  if (wizardStep.value === 1) {
    // Start the creation flow
    await startCreation()
  } else {
    // Continue with current answer
    await submitAnswer()
  }
}

function handleBack() {
  if (wizardStep.value === 1) {
    // Cancel the entire wizard
    cancelWizard()
  } else {
    // Go back to step 1 (restart)
    // Note: rclone state machine doesn't support going back,
    // so we need to cancel and restart
    cancelSession()
    resetWizard()
  }
}

async function startCreation() {
  isProcessing.value = true

  try {
    const result = await apiCall('/api/remotes/custom/start', 'POST', {
      name: remoteName.value.trim(),
      type: remoteType.value
    })

    if (result.status === 'complete') {
      // Remote created successfully (no questions needed)
      emit('remote-created', remoteName.value)
      emit('update:modelValue', false)
      resetWizard()
    } else if (result.status === 'needs_input') {
      // Move to next step with question
      wizardStep.value = 2
      sessionId.value = result.session_id
      currentQuestion.value = result.question
      currentAnswer.value = result.question.default || ''
    } else if (result.status === 'error') {
      alert(`Error: ${result.message}`)
    }
  } catch (error) {
    console.error('Failed to start creation:', error)
    alert(`Failed to start creation: ${error.message}`)
  } finally {
    isProcessing.value = false
  }
}

async function submitAnswer() {
  isProcessing.value = true

  try {
    const result = await apiCall('/api/remotes/custom/continue', 'POST', {
      session_id: sessionId.value,
      answer: currentAnswer.value.trim()
    })

    if (result.status === 'complete') {
      // Remote created successfully
      emit('remote-created', sessionId.value)
      emit('update:modelValue', false)
      resetWizard()
    } else if (result.status === 'needs_input') {
      // Show next question
      currentQuestion.value = result.question
      currentAnswer.value = result.question.default || ''
    } else if (result.status === 'error') {
      alert(`Error: ${result.message}`)
    }
  } catch (error) {
    console.error('Failed to submit answer:', error)
    alert(`Failed to submit answer: ${error.message}`)
  } finally {
    isProcessing.value = false
  }
}

async function cancelSession() {
  if (sessionId.value) {
    try {
      await apiCall('/api/remotes/custom/cancel', 'POST', {
        session_id: sessionId.value
      })
    } catch (error) {
      console.error('Failed to cancel session:', error)
    }
  }
}

function cancelWizard() {
  cancelSession()
  emit('update:modelValue', false)
  resetWizard()
}

function getNextButtonText() {
  if (wizardStep.value === 1) {
    return 'Start'
  }
  return 'Next'
}

function getPlaceholder() {
  if (currentQuestion.value?.default) {
    return `Default: ${currentQuestion.value.default}`
  }
  return currentQuestion.value?.required ? 'Required' : 'Optional (press Enter to skip)'
}

/**
 * Format help text to convert URLs to clickable links
 */
function formatHelp(helpText) {
  if (!helpText) return ''

  // Escape HTML first
  let escaped = helpText
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')

  // Convert URLs to links
  // Match http(s):// URLs
  const urlRegex = /(https?:\/\/[^\s<>"{}|\\^`\[\]]+)/g
  escaped = escaped.replace(urlRegex, '<a href="$1" target="_blank" style="color: #007bff; text-decoration: underline;">$1</a>')

  // Convert newlines to <br>
  escaped = escaped.replace(/\n/g, '<br>')

  return escaped
}
</script>

<style scoped>
.btn-secondary {
  background: #6c757d;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-right: 10px;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn-primary {
  background: #28a745;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover:not(:disabled) {
  background: #218838;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

input, select {
  font-family: inherit;
}
</style>
