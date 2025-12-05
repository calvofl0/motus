<template>
  <BaseModal
    :modelValue="modelValue"
    size="large"
    @update:modelValue="$emit('update:modelValue', $event)"
  >
    <template #header>🔐 OAuth Token Refresh</template>
    <template #body>
      <p class="oauth-intro">
        To refresh your OAuth token, please run the following command on your local machine where you have a browser:
      </p>

      <!-- Step 1: Install rclone -->
      <div class="oauth-step">
        <strong class="step-title">Step 1: Install rclone (if not already installed)</strong>
        <p class="step-text">
          Download rclone from:
          <a href="https://rclone.org/downloads/" target="_blank" class="oauth-link">https://rclone.org/downloads/</a>
        </p>
      </div>

      <!-- Step 2: Run authorize command -->
      <div class="oauth-step">
        <strong class="step-title">Step 2: Run this command</strong>
        <div class="command-box">
          <div class="command-text">{{ authorizeCommand }}</div>
        </div>
        <button @click="copyCommand" class="btn btn-success copy-button">
          📋 Copy to Clipboard
          <span v-if="showCopyTooltip" class="copy-tooltip">Copied!</span>
        </button>
      </div>

      <!-- Step 3: Paste token -->
      <div class="oauth-step">
        <strong class="step-title">Step 3: Paste the token here</strong>
        <p class="step-text">
          After running the command, you will see a long token string. Copy and paste it below:
        </p>
        <textarea
          v-model="tokenInput"
          placeholder="Paste the token string here..."
          class="token-input"
        ></textarea>
      </div>

      <!-- Status message -->
      <div
        v-if="statusMessage"
        class="status-message"
        :class="`status-${statusType}`"
      >
        {{ statusMessage }}
      </div>
    </template>
    <template #footer>
      <button @click="$emit('update:modelValue', false)" class="btn btn-secondary">Cancel</button>
      <button @click="submitToken" :disabled="submitting" class="btn btn-success">
        {{ submitting ? 'Submitting...' : 'Submit' }}
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { apiCall } from '../../services/api'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  remoteName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'token-refreshed'])

// State
const authorizeCommand = ref('Loading...')
const tokenInput = ref('')
const showCopyTooltip = ref(false)
const statusMessage = ref('')
const statusType = ref('success') // 'success' or 'error'
const submitting = ref(false)

// Watch for modal opening to fetch authorize command
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen && props.remoteName) {
    await startOAuthRefresh()
  } else {
    // Reset state when modal closes
    authorizeCommand.value = 'Loading...'
    tokenInput.value = ''
    statusMessage.value = ''
    submitting.value = false
  }
})

// Start OAuth refresh process
async function startOAuthRefresh() {
  try {
    const response = await apiCall(`/api/remotes/${encodeURIComponent(props.remoteName)}/oauth/refresh`, 'POST')

    if (response.status === 'needs_token') {
      authorizeCommand.value = response.authorize_command
    } else if (response.status === 'complete') {
      // Token refresh completed immediately (shouldn't normally happen, but handle it)
      showStatus(`OAuth token successfully refreshed for "${props.remoteName}"`, 'success')
      emit('token-refreshed')
      setTimeout(() => {
        emit('update:modelValue', false)
      }, 2000)
    } else if (response.status === 'error') {
      showStatus(`Failed to refresh OAuth token: ${response.message || 'Unknown error'}`, 'error')
    } else {
      showStatus(`Unexpected response from server: ${response.status}`, 'error')
    }
  } catch (error) {
    showStatus(`Failed to start OAuth refresh: ${error.message}`, 'error')
  }
}

// Copy command to clipboard
async function copyCommand() {
  try {
    await navigator.clipboard.writeText(authorizeCommand.value)
    showCopyTooltip.value = true
    setTimeout(() => {
      showCopyTooltip.value = false
    }, 1000)
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    showStatus('Failed to copy to clipboard', 'error')
  }
}

// Submit OAuth token
async function submitToken() {
  if (!tokenInput.value.trim()) {
    showStatus('Please paste the token before submitting', 'error')
    return
  }

  submitting.value = true
  statusMessage.value = ''

  try {
    const response = await apiCall(`/api/remotes/${encodeURIComponent(props.remoteName)}/oauth/submit-token`, 'POST', {
      token: tokenInput.value.trim()
    })

    if (response.status === 'complete') {
      showStatus(`OAuth token successfully refreshed for "${props.remoteName}"`, 'success')
      emit('token-refreshed')
      setTimeout(() => {
        emit('update:modelValue', false)
      }, 2000)
    } else if (response.status === 'error') {
      showStatus(`Failed to refresh token: ${response.message || 'Unknown error'}`, 'error')
    } else {
      showStatus(`Unexpected response from server: ${response.status}`, 'error')
    }
  } catch (error) {
    showStatus(`Failed to submit token: ${error.message}`, 'error')
  } finally {
    submitting.value = false
  }
}

// Show status message
function showStatus(message, type = 'success') {
  statusMessage.value = message
  statusType.value = type
}

// Handle Ctrl+C to copy authorize command
function handleKeyDown(event) {
  // Only handle if this modal is actually open
  if (!props.modelValue) return

  if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
    const selection = window.getSelection()
    if (!selection || selection.toString().length === 0) {
      // No text selected, copy the authorize command
      event.preventDefault()
      copyCommand()
    }
  }
}

// Add/remove keyboard event listener
onMounted(() => {
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.oauth-intro {
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-lg);
}

.oauth-step {
  background: var(--color-bg-light);
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-lg);
  border: 1px solid var(--color-border-light);
}

.step-title {
  display: block;
  color: var(--color-text-primary);
  margin-bottom: var(--spacing-xs);
}

.step-text {
  margin: var(--spacing-sm) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-md);
}

.oauth-link {
  color: var(--color-primary);
  text-decoration: underline;
}

.command-box {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: var(--spacing-md);
  border-radius: var(--radius-sm);
  margin: var(--spacing-sm) 0;
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-sm);
  word-break: break-all;
}

.command-text {
  white-space: pre-wrap;
}

.copy-button {
  position: relative;
}

.copy-tooltip {
  display: inline;
  position: absolute;
  top: -30px;
  left: 50%;
  transform: translateX(-50%);
  background: var(--color-text-primary);
  color: var(--color-bg-white);
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  white-space: nowrap;
}

.token-input {
  width: 100%;
  min-height: 120px;
  padding: var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-xs);
  resize: vertical;
}

.status-message {
  padding: var(--spacing-md);
  border-radius: var(--radius-sm);
  margin-bottom: var(--spacing-lg);
}

.status-success {
  background: var(--color-bg-success-light);
  color: var(--color-text-success);
  border: 1px solid var(--color-success);
}

.status-error {
  background: var(--color-bg-danger-light);
  color: var(--color-text-danger);
  border: 1px solid var(--color-danger);
}
</style>
