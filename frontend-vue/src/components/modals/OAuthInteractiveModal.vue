<template>
  <BaseModal
    :modelValue="modelValue"
    size="large"
    @update:modelValue="$emit('update:modelValue', $event)"
  >
    <template #header>🔐 OAuth Token Refresh</template>
    <template #body>
      <p style="color: #666; margin-bottom: 20px;">
        To refresh your OAuth token, please run the following command on your local machine where you have a browser:
      </p>

      <!-- Step 1: Install rclone -->
      <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #dee2e6;">
        <strong style="color: #333;">Step 1: Install rclone (if not already installed)</strong>
        <p style="margin: 10px 0; color: #666; font-size: 14px;">
          Download rclone from:
          <a href="https://rclone.org/downloads/" target="_blank" style="color: #007bff; text-decoration: underline;">https://rclone.org/downloads/</a>
        </p>
      </div>

      <!-- Step 2: Run authorize command -->
      <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #dee2e6;">
        <strong style="color: #333;">Step 2: Run this command</strong>
        <div style="background: #2d2d2d; color: #f8f8f2; padding: 12px; border-radius: 4px; margin: 10px 0; font-family: monospace; font-size: 13px; word-break: break-all;">
          <div style="white-space: pre-wrap;">{{ authorizeCommand }}</div>
        </div>
        <button @click="copyCommand" style="background: #28a745; color: white; border: none; border-radius: 4px; padding: 8px 16px; cursor: pointer; font-size: 14px; position: relative;">
          📋 Copy to Clipboard
          <span
            v-if="showCopyTooltip"
            style="display: inline; position: absolute; top: -30px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; white-space: nowrap;"
          >Copied!</span>
        </button>
      </div>

      <!-- Step 3: Paste token -->
      <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 15px; border: 1px solid #dee2e6;">
        <strong style="color: #333;">Step 3: Paste the token here</strong>
        <p style="margin: 10px 0; color: #666; font-size: 14px;">
          After running the command, you will see a long token string. Copy and paste it below:
        </p>
        <textarea
          v-model="tokenInput"
          placeholder="Paste the token string here..."
          style="width: 100%; min-height: 120px; padding: 10px; border: 1px solid #ced4da; border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical;"
        ></textarea>
      </div>

      <!-- Status message -->
      <div
        v-if="statusMessage"
        :style="{
          padding: '12px',
          borderRadius: '4px',
          marginBottom: '15px',
          background: statusType === 'error' ? '#f8d7da' : '#d4edda',
          color: statusType === 'error' ? '#721c24' : '#155724',
          border: statusType === 'error' ? '1px solid #f5c6cb' : '1px solid #c3e6cb'
        }"
      >
        {{ statusMessage }}
      </div>
    </template>
    <template #footer>
      <button @click="$emit('update:modelValue', false)" style="background: #6c757d;">Cancel</button>
      <button @click="submitToken" :disabled="submitting" style="background: #28a745;">
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
