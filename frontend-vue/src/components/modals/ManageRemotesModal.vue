<template>
  <!-- Main Manage Remotes Modal -->
  <BaseModal
    :modelValue="appStore.showManageRemotesModal"
    @update:modelValue="handleMainModalClose"
    size="large"
  >
    <template #header>
      <span v-if="currentStep === 1">🔧 Manage Remotes</span>
      <span v-else-if="currentStep === 2">📋 Add Remote</span>
      <span v-else-if="currentStep === 3">⚙️ Configure Remote</span>
    </template>

    <template #body>
      <!-- Step 1: List Remotes -->
      <div v-if="currentStep === 1" style="margin-bottom: 15px; overflow-y: auto; max-height: 50vh;">
        <p v-if="loading" style="color: #666; text-align: center;">Loading remotes...</p>
        <p v-else-if="remotes.length === 0" style="color: #666; text-align: center;">No remotes configured</p>
        <table v-else style="width: 100%; border-collapse: collapse;">
          <thead>
            <tr style="border-bottom: 2px solid #ddd;">
              <th style="text-align: left; padding: 8px;">Name</th>
              <th style="text-align: left; padding: 8px;">Type</th>
              <th style="text-align: center; padding: 8px; width: 140px;">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="remote in remotes"
              :key="remote.name"
              @dblclick="viewRemoteConfig(remote.name)"
              style="border-bottom: 1px solid #eee; cursor: pointer; transition: background-color 0.2s;"
              @mouseenter="$event.currentTarget.style.backgroundColor = '#f8f9fa'"
              @mouseleave="$event.currentTarget.style.backgroundColor = ''"
              title="Double-click to view configuration"
            >
              <td style="padding: 8px;">{{ remote.name }}</td>
              <td style="padding: 8px;">{{ remote.type }}</td>
              <td style="padding: 8px; text-align: center;">
                <button
                  v-if="remote.is_oauth"
                  @click.stop="refreshOAuth(remote.name)"
                  style="background: none; border: none; font-size: 18px; cursor: pointer; color: #28a745; padding: 4px 8px; margin-right: 4px;"
                  title="Refresh OAuth token"
                >↻</button>
                <span v-else style="display: inline-block; width: 32px; margin-right: 4px;"></span>

                <button
                  @click.stop="editRemoteConfig(remote.name)"
                  :disabled="isActiveRemote(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '14px',
                    cursor: isActiveRemote(remote.name) ? 'not-allowed' : 'pointer',
                    color: isActiveRemote(remote.name) ? '#ccc' : '#007bff',
                    padding: '4px 8px',
                    marginRight: '4px'
                  }"
                  :title="isActiveRemote(remote.name) ? 'Cannot edit remote while in use' : 'Edit remote'"
                >✏️</button>

                <button
                  @click.stop="deleteRemote(remote.name)"
                  :disabled="isActiveRemote(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '18px',
                    cursor: isActiveRemote(remote.name) ? 'not-allowed' : 'pointer',
                    color: isActiveRemote(remote.name) ? '#ccc' : '#dc3545',
                    padding: '4px 8px'
                  }"
                  :title="isActiveRemote(remote.name) ? 'Cannot delete remote while in use' : 'Delete remote'"
                >🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Step 2: Select Template -->
      <div v-else-if="currentStep === 2">
        <p style="margin-bottom: 15px; color: #666;">Choose a template for the new remote:</p>
        <div style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px; display: flex; flex-direction: column; gap: 10px;">
          <div
            v-for="template in templates"
            :key="template.name"
            @click="selectTemplate(template.name)"
            :style="{
              padding: '12px',
              border: selectedTemplate?.name === template.name ? '2px solid #007bff' : '1px solid #ddd',
              background: selectedTemplate?.name === template.name ? '#e7f3ff' : '',
              borderRadius: '6px',
              cursor: 'pointer'
            }"
          >
            <strong style="display: block; margin-bottom: 4px;">{{ template.name }}</strong>
            <small v-if="template.fields && template.fields.length > 0" style="color: #666;">
              Fields: {{ template.fields.map(f => f.label).join(', ') }}
            </small>
          </div>
        </div>
      </div>

      <!-- Step 3: Configure Remote -->
      <div v-else-if="currentStep === 3" style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px;">
        <!-- Template Form -->
        <div v-if="selectedTemplate">
          <p style="margin-bottom: 15px;"><strong>Template:</strong> {{ selectedTemplate.name }}</p>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <!-- Remote Name field -->
            <div>
              <label style="display: block; margin-bottom: 4px; font-weight: 500;">Remote Name</label>
              <input
                v-model="remoteName"
                type="text"
                placeholder="Enter remote name"
                pattern="[a-zA-Z0-9_-]+"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
              />
              <small style="color: #666;">Use only letters, numbers, underscores, and hyphens</small>
            </div>

            <!-- Template fields -->
            <div v-for="field in selectedTemplate.fields" :key="field.key">
              <label style="display: block; margin-bottom: 4px; font-weight: 500;">
                {{ field.label }}
                <span v-if="field.help" class="help-icon" style="display: inline-block; cursor: help; position: relative; margin-left: 4px;">
                  <svg width="16" height="16" viewBox="0 0 16 16" style="vertical-align: middle;">
                    <circle cx="8" cy="8" r="7" fill="none" stroke="#007bff" stroke-width="1.5"/>
                    <text x="8" y="11" text-anchor="middle" fill="#007bff" font-size="11" font-weight="bold" font-family="serif">i</text>
                  </svg>
                  <span class="help-tooltip" style="display: none; position: absolute; left: 20px; top: -5px; background: #2c3e50; color: white; padding: 10px 14px; border-radius: 6px; z-index: 1000; font-size: 13px; font-weight: normal; min-width: 250px; max-width: 400px; white-space: normal; line-height: 1.4; box-shadow: 0 4px 12px rgba(0,0,0,0.3);" v-html="field.help"></span>
                </span>
              </label>
              <input
                v-model="formValues[field.key]"
                :type="isSecretField(field) ? 'password' : 'text'"
                :placeholder="`Enter ${field.label}`"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
              />
            </div>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <!-- Step 1 Footer -->
      <template v-if="currentStep === 1">
        <button
          v-if="templatesAvailable"
          @click="showTemplateSelection"
          style="background: #28a745;"
        >+ Add Remote</button>
      </template>

      <!-- Step 2 Footer -->
      <template v-else-if="currentStep === 2">
        <button
          @click="showCustomRemoteForm"
          style="background: #6c757d; margin-right: auto;"
        >Custom Remote</button>
        <button @click="showRemotesList">Back</button>
        <button
          @click="showRemoteForm"
          :disabled="!selectedTemplate"
          style="background: #007bff;"
        >Next</button>
      </template>

      <!-- Step 3 Footer -->
      <template v-else-if="currentStep === 3">
        <button @click="showTemplateSelection">Back</button>
        <button
          @click="createRemote"
          :disabled="!isFormValid"
          style="background: #28a745;"
        >Create Remote</button>
      </template>
    </template>
  </BaseModal>

  <!-- Custom Remote Config Modal -->
  <BaseModal
    v-model="showCustomConfigModal"
    size="medium"
  >
    <template #header>⚙️ Custom Remote Configuration</template>
    <template #body>
      <p style="margin-bottom: 15px;"><strong>Custom Remote Configuration</strong></p>
      <p style="color: #666; margin-bottom: 10px;">Enter the rclone configuration for your custom remote. Must include the [remote_name] section header.</p>
      <textarea
        v-model="customConfig"
        style="width: 100%; min-height: 300px; max-height: 50vh; font-family: monospace; font-size: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; resize: vertical;"
        placeholder="[myremote]&#10;type = s3&#10;access_key_id = YOUR_ACCESS_KEY&#10;secret_access_key = YOUR_SECRET_KEY&#10;region = us-east-1&#10;..."
      ></textarea>
    </template>
    <template #footer>
      <button @click="showCustomConfigModal = false">Cancel</button>
      <button
        @click="createCustomRemote"
        :disabled="!isCustomConfigValid"
        style="background: #28a745;"
      >Create Remote</button>
    </template>
  </BaseModal>

  <!-- View Remote Config Modal -->
  <BaseModal
    v-model="showViewConfigModal"
    size="medium"
  >
    <template #header>📄 Remote Configuration</template>
    <template #body>
      <div style="margin-bottom: 15px; max-height: 50vh; overflow-y: auto;">
        <h4 style="margin-top: 0; margin-bottom: 15px; color: #333;">{{ currentViewedRemote?.name }}</h4>
        <div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6;">
          <table style="width: 100%; border-collapse: collapse;">
            <tr
              v-for="([key, value], index) in Object.entries(currentViewedRemote?.config || {})"
              :key="key"
              :style="{ borderBottom: index < Object.keys(currentViewedRemote?.config || {}).length - 1 ? '1px solid #e0e0e0' : '' }"
            >
              <td style="padding: 8px; font-weight: 500; color: #495057; width: 40%;">{{ key }}</td>
              <td style="padding: 8px; color: #212529; font-family: monospace; word-break: break-all;">
                {{ isSensitiveKey(key) ? '••••••••' : value }}
              </td>
            </tr>
          </table>
        </div>
      </div>
    </template>
    <template #footer>
      <button @click="copyConfigToClipboard" style="background: #28a745; position: relative;">
        📋 Copy to Clipboard
        <span
          v-if="showCopyTooltip"
          style="display: inline; position: absolute; top: -30px; left: 50%; transform: translateX(-50%); background: #333; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; white-space: nowrap;"
        >Copied!</span>
      </button>
    </template>
  </BaseModal>

  <!-- Edit Remote Config Modal -->
  <BaseModal
    v-model="showEditConfigModal"
    size="medium"
  >
    <template #header>✏️ Edit Remote Configuration</template>
    <template #body>
      <p style="color: #666; margin-bottom: 10px;">Edit the rclone configuration for this remote. You can rename the remote by changing the value between [brackets].</p>
      <textarea
        v-model="editConfigText"
        style="width: 100%; min-height: 300px; max-height: 50vh; font-family: monospace; font-size: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; resize: vertical;"
        placeholder="[remote_name]&#10;type = s3&#10;..."
      ></textarea>
    </template>
    <template #footer>
      <button @click="showEditConfigModal = false">Cancel</button>
      <button @click="saveRemoteConfig" style="background: #28a745;">Save</button>
    </template>
  </BaseModal>

  <!-- OAuth Interactive Modal -->
  <OAuthInteractiveModal
    v-model="showOAuthModal"
    :remote-name="oauthRemoteName"
    @token-refreshed="handleOAuthRefreshed"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../../stores/app'
import { apiCall } from '../../services/api'
import BaseModal from './BaseModal.vue'
import OAuthInteractiveModal from './OAuthInteractiveModal.vue'

const appStore = useAppStore()

// State
const currentStep = ref(1)
const loading = ref(false)
const remotes = ref([])
const templates = ref([])
const templatesAvailable = ref(false)
const selectedTemplate = ref(null)
const remoteName = ref('')
const formValues = ref({})
const customConfig = ref('')

// Modals
const showCustomConfigModal = ref(false)
const showViewConfigModal = ref(false)
const currentViewedRemote = ref(null)
const showCopyTooltip = ref(false)
const showEditConfigModal = ref(false)
const editConfigText = ref('')
const editingRemoteName = ref('')
const showOAuthModal = ref(false)
const oauthRemoteName = ref('')

// Computed
const isFormValid = computed(() => {
  if (!selectedTemplate.value) return false
  if (!remoteName.value.trim()) return false

  for (const field of selectedTemplate.value.fields || []) {
    if (!formValues.value[field.key]?.trim()) return false
  }

  return true
})

const isCustomConfigValid = computed(() => {
  return customConfig.value.trim() && /^\[.+?\]/m.test(customConfig.value)
})

// Handle ESC key for main modal
function handleMainModalClose() {
  // If on step 2 or 3, go back to step 1
  if (currentStep.value === 2 || currentStep.value === 3) {
    showRemotesList()
  } else {
    // Close the modal
    appStore.closeManageRemotes()
  }
}

// Watch modal open/close
watch(() => appStore.showManageRemotesModal, async (isOpen) => {
  if (isOpen) {
    currentStep.value = 1
    await loadRemotesList()
    await loadTemplatesList()
  }
})

// Watch for step changes to add tooltip listeners and refocus
watch(currentStep, async (newStep) => {
  await nextTick()

  // Setup tooltips for step 3
  if (newStep === 3) {
    setupHelpTooltips()
  }

  // Refocus main modal overlay after step change
  const mainOverlay = document.querySelector('.modal-overlay')
  if (mainOverlay) {
    mainOverlay.focus()
  }
})

// Watch child modals closing to refocus parent modal
watch([showCustomConfigModal, showViewConfigModal, showEditConfigModal, showOAuthModal], async ([custom, view, edit, oauth], [prevCustom, prevView, prevEdit, prevOAuth]) => {
  // If any child modal just closed (was true, now false) and main modal is still open
  if (appStore.showManageRemotesModal) {
    if ((prevCustom && !custom) || (prevView && !view) || (prevEdit && !edit) || (prevOAuth && !oauth)) {
      // Wait for DOM update, then refocus main modal overlay
      await nextTick()
      const mainOverlay = document.querySelector('.modal-overlay')
      if (mainOverlay) {
        mainOverlay.focus()
      }
    }
  }
})

// Setup help tooltips
function setupHelpTooltips() {
  const helpIcons = document.querySelectorAll('.help-icon')
  helpIcons.forEach(icon => {
    const tooltip = icon.querySelector('.help-tooltip')
    if (tooltip) {
      let hideTimeout

      icon.addEventListener('mouseenter', () => {
        tooltip.style.display = 'block'
      })

      icon.addEventListener('mouseleave', () => {
        hideTimeout = setTimeout(() => {
          if (!tooltip.matches(':hover')) {
            tooltip.style.display = 'none'
          }
        }, 100)
      })

      tooltip.addEventListener('mouseenter', () => {
        clearTimeout(hideTimeout)
        tooltip.style.display = 'block'
      })

      tooltip.addEventListener('mouseleave', () => {
        tooltip.style.display = 'none'
      })
    }
  })
}

// Load remotes list
async function loadRemotesList() {
  loading.value = true
  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes || []
  } catch (error) {
    console.error('Failed to load remotes:', error)
    alert(`Failed to load remotes: ${error.message}`)
  } finally {
    loading.value = false
  }
}

// Load templates list
async function loadTemplatesList() {
  try {
    const data = await apiCall('/api/templates')
    templates.value = data.templates || []
    templatesAvailable.value = data.available && data.templates.length > 0
  } catch (error) {
    console.error('Failed to load templates:', error)
    templatesAvailable.value = false
  }
}

// Check if remote is active
function isActiveRemote(remoteName) {
  return appStore.leftPane.remote === remoteName || appStore.rightPane.remote === remoteName
}

// Show custom remote form
function showCustomRemoteForm() {
  customConfig.value = ''
  showCustomConfigModal.value = true
}

// Show template selection
function showTemplateSelection() {
  currentStep.value = 2
  selectedTemplate.value = null
  formValues.value = {}
}

// Show remotes list
function showRemotesList() {
  currentStep.value = 1
  selectedTemplate.value = null
  formValues.value = {}
  remoteName.value = ''
}

// Show remote form
function showRemoteForm() {
  currentStep.value = 3
}

// Select template
function selectTemplate(templateName) {
  selectedTemplate.value = templates.value.find(t => t.name === templateName)
}

// Is secret field
function isSecretField(field) {
  const label = field.label.toLowerCase()
  return label.includes('password') || label.includes('secret') || label.includes('key')
}

// Is sensitive key
function isSensitiveKey(key) {
  const lowerKey = key.toLowerCase()
  return lowerKey.includes('password') || lowerKey.includes('secret') || lowerKey.includes('key') || lowerKey.includes('token')
}

// Create remote from template
async function createRemote() {
  try {
    const config = { type: selectedTemplate.value.name }

    for (const field of selectedTemplate.value.fields) {
      config[field.key] = formValues.value[field.key].trim()
    }

    await apiCall('/api/remotes', 'POST', {
      name: remoteName.value.trim(),
      config: config
    })

    await loadRemotesList()
    showRemotesList()

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))

    alert('Remote created successfully')
  } catch (error) {
    alert(`Failed to create remote: ${error.message}`)
  }
}

// Create custom remote
async function createCustomRemote() {
  try {
    await apiCall('/api/remotes/raw', 'POST', {
      raw_config: customConfig.value
    })

    await loadRemotesList()
    showCustomConfigModal.value = false

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))

    alert('Remote created successfully')
  } catch (error) {
    alert(`Failed to create remote: ${error.message}`)
  }
}

// View remote config
async function viewRemoteConfig(name) {
  const remote = remotes.value.find(r => r.name === name)
  if (!remote) return

  currentViewedRemote.value = remote
  showViewConfigModal.value = true
}

// Copy config to clipboard
async function copyConfigToClipboard() {
  if (!currentViewedRemote.value) return

  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(currentViewedRemote.value.name)}/raw`)
    await navigator.clipboard.writeText(data.raw_config)

    showCopyTooltip.value = true
    setTimeout(() => {
      showCopyTooltip.value = false
    }, 1000)
  } catch (error) {
    console.error('Failed to copy to clipboard:', error)
    alert('Failed to copy to clipboard')
  }
}

// Handle Ctrl+C to copy remote config when view modal is open
function handleViewConfigKeyDown(event) {
  if (!showViewConfigModal.value) return

  if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
    const selection = window.getSelection()
    if (!selection || selection.toString().length === 0) {
      // No text selected, copy the entire config
      event.preventDefault()
      copyConfigToClipboard()
    }
  }
}

// Watch view config modal to add/remove keyboard listener
watch(showViewConfigModal, (isOpen) => {
  if (isOpen) {
    document.addEventListener('keydown', handleViewConfigKeyDown)
  } else {
    document.removeEventListener('keydown', handleViewConfigKeyDown)
  }
})

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('keydown', handleViewConfigKeyDown)
})

// Edit remote config
async function editRemoteConfig(name) {
  if (isActiveRemote(name)) {
    alert(`Cannot edit remote "${name}" while it is in use. Please select a different remote first.`)
    return
  }

  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(name)}/raw`)
    editConfigText.value = data.raw_config
    editingRemoteName.value = name
    showEditConfigModal.value = true
  } catch (error) {
    console.error('Error loading remote config:', error)
    alert(`Failed to load remote config: ${error.message}`)
  }
}

// Save remote config
async function saveRemoteConfig() {
  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(editingRemoteName.value)}/raw`, 'PUT', {
      raw_config: editConfigText.value
    })

    const newName = data.new_name
    const isRename = newName !== editingRemoteName.value

    showEditConfigModal.value = false
    await loadRemotesList()

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))

    alert(isRename ?
      `Remote successfully renamed from "${editingRemoteName.value}" to "${newName}"` :
      `Remote "${newName}" updated successfully`)
  } catch (error) {
    alert(`Failed to save remote: ${error.message}`)
  }
}

// Delete remote
async function deleteRemote(name) {
  if (isActiveRemote(name)) {
    alert(`Cannot delete remote "${name}" while it is in use. Please select a different remote first.`)
    return
  }

  if (!confirm(`Are you sure you want to delete the remote "${name}"?`)) {
    return
  }

  try {
    await apiCall(`/api/remotes/${name}`, 'DELETE')
    await loadRemotesList()

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))
  } catch (error) {
    alert(`Failed to delete remote: ${error.message}`)
  }
}

// Refresh OAuth
function refreshOAuth(name) {
  oauthRemoteName.value = name
  showOAuthModal.value = true
}

// Handle OAuth token refreshed
async function handleOAuthRefreshed() {
  await loadRemotesList()
  // Trigger remotes changed event
  window.dispatchEvent(new CustomEvent('remotes-changed'))
}
</script>

<style scoped>
.help-icon svg {
  vertical-align: middle;
}

.help-tooltip {
  pointer-events: auto;
}

.help-tooltip::before {
  content: '';
  position: absolute;
  left: -6px;
  top: 8px;
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 6px solid #2c3e50;
}
</style>
