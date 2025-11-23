<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="true"
    maxWidth="700px"
  >
    <!-- Step 1: List Remotes -->
    <template v-if="step === 1" #header>🔧 Manage Remotes</template>
    <template v-if="step === 1" #body>
      <div style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px;">
        <!-- Loading State -->
        <p v-if="loading" style="color: #666; text-align: center;">Loading remotes...</p>

        <!-- Error State -->
        <p v-else-if="error" style="color: #dc3545;">{{ error }}</p>

        <!-- Empty State -->
        <p v-else-if="remotes.length === 0" style="color: #666; text-align: center;">No remotes configured</p>

        <!-- Remotes Table -->
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
              @click="viewRemote(remote.name)"
              style="border-bottom: 1px solid #eee; cursor: pointer; transition: background-color 0.2s;"
              :style="{ backgroundColor: hoveredRemote === remote.name ? '#f5f5f5' : 'transparent' }"
              @mouseenter="hoveredRemote = remote.name"
              @mouseleave="hoveredRemote = null"
              :title="`Click to view ${remote.name} configuration`"
            >
              <td style="padding: 8px;">{{ remote.name }}</td>
              <td style="padding: 8px;">{{ remote.type }}</td>
              <td class="remote-actions" style="padding: 8px; text-align: center;" @click.stop>
                <!-- OAuth Refresh Button -->
                <button
                  v-if="remote.is_oauth"
                  @click="refreshOAuth(remote.name)"
                  style="background: none; border: none; font-size: 18px; cursor: pointer; color: #28a745; padding: 4px 8px; margin-right: 4px;"
                  title="Refresh OAuth token"
                >
                  ↻
                </button>
                <span v-else style="display: inline-block; width: 32px; margin-right: 4px;"></span>

                <!-- Edit Button -->
                <button
                  @click="editRemote(remote.name)"
                  :disabled="isRemoteActive(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '14px',
                    cursor: isRemoteActive(remote.name) ? 'not-allowed' : 'pointer',
                    color: isRemoteActive(remote.name) ? '#ccc' : '#007bff',
                    padding: '4px 8px',
                    marginRight: '4px'
                  }"
                  :title="isRemoteActive(remote.name) ? 'Cannot edit remote while in use' : 'Edit remote'"
                >
                  ✏️
                </button>

                <!-- Delete Button -->
                <button
                  @click="deleteRemote(remote.name)"
                  :disabled="isRemoteActive(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '18px',
                    cursor: isRemoteActive(remote.name) ? 'not-allowed' : 'pointer',
                    color: isRemoteActive(remote.name) ? '#ccc' : '#dc3545',
                    padding: '4px 8px'
                  }"
                  :title="isRemoteActive(remote.name) ? 'Cannot delete remote while in use' : 'Delete remote'"
                >
                  🗑️
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <template v-if="step === 1" #footer>
      <button
        v-if="templates.length > 0"
        @click="goToTemplateSelection"
        style="background: #28a745;"
      >
        + Add Remote
      </button>
    </template>

    <!-- Step 2: Select Template -->
    <template v-if="step === 2" #header>📋 Select Template</template>
    <template v-if="step === 2" #body>
      <p style="margin-bottom: 15px; color: #666;">Choose a template for the new remote:</p>
      <div style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px;">
        <div style="display: flex; flex-direction: column; gap: 10px;">
          <!-- Template Items -->
          <div
            v-for="template in templates"
            :key="template.name"
            @click="selectTemplate(template)"
            :style="{
              padding: '12px',
              border: selectedTemplate?.name === template.name ? '2px solid #007bff' : '1px solid #ddd',
              background: selectedTemplate?.name === template.name ? '#e7f3ff' : 'transparent',
              borderRadius: '6px',
              cursor: 'pointer'
            }"
          >
            <strong style="display: block; margin-bottom: 4px;">{{ template.name }}</strong>
            <small v-if="template.fields && template.fields.length > 0" style="color: #666;">
              Fields: {{ template.fields.map(f => f.label).join(', ') }}
            </small>
          </div>

          <!-- Custom Remote Option -->
          <div
            @click="selectCustomTemplate"
            :style="{
              padding: '12px',
              border: selectedTemplate?.name === '__custom__' ? '2px solid #007bff' : '1px solid #ddd',
              background: selectedTemplate?.name === '__custom__' ? '#e7f3ff' : 'transparent',
              borderRadius: '6px',
              cursor: 'pointer'
            }"
          >
            <strong style="display: block; margin-bottom: 4px;">Custom Remote</strong>
            <small style="color: #666;">Manually enter remote configuration</small>
          </div>
        </div>
      </div>
    </template>
    <template v-if="step === 2" #footer>
      <button @click="step = 1">Back</button>
      <button @click="goToConfiguration" :disabled="!selectedTemplate" style="background: #007bff;">
        Next
      </button>
    </template>

    <!-- Step 3: Configure Remote -->
    <template v-if="step === 3" #header>⚙️ Configure Remote</template>
    <template v-if="step === 3" #body>
      <div style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px;">
        <!-- Custom Configuration -->
        <div v-if="selectedTemplate?.name === '__custom__'">
          <p style="margin-bottom: 15px;"><strong>Custom Remote Configuration</strong></p>
          <p style="color: #666; margin-bottom: 10px;">
            Enter the rclone configuration for your custom remote. Must include the [remote_name] section header.
          </p>
          <textarea
            v-model="customConfig"
            style="width: 100%; min-height: 300px; font-family: monospace; font-size: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; resize: vertical;"
            placeholder="[myremote]&#10;type = s3&#10;access_key_id = YOUR_ACCESS_KEY&#10;secret_access_key = YOUR_SECRET_KEY&#10;region = us-east-1&#10;..."
          ></textarea>
        </div>

        <!-- Template-Based Configuration -->
        <div v-else-if="selectedTemplate">
          <p style="margin-bottom: 15px;"><strong>Template:</strong> {{ selectedTemplate.name }}</p>
          <div style="display: flex; flex-direction: column; gap: 12px;">
            <!-- Remote Name Field -->
            <div>
              <label style="display: block; margin-bottom: 4px; font-weight: 500;">Remote Name</label>
              <input
                type="text"
                v-model="remoteName"
                placeholder="Enter remote name"
                pattern="[a-zA-Z0-9_-]+"
                title="Use only letters, numbers, underscores, and hyphens"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
              />
              <small style="color: #666;">Use only letters, numbers, underscores, and hyphens</small>
            </div>

            <!-- Template Fields -->
            <div v-for="field in selectedTemplate.fields" :key="field.key">
              <label style="display: block; margin-bottom: 4px; font-weight: 500;">
                {{ field.label }}
                <span
                  v-if="field.help"
                  class="help-icon"
                  style="display: inline-block; cursor: help; position: relative; margin-left: 4px;"
                  @mouseenter="showTooltip(field.key)"
                  @mouseleave="hideTooltip(field.key)"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" style="vertical-align: middle;">
                    <circle cx="8" cy="8" r="7" fill="none" stroke="#007bff" stroke-width="1.5"/>
                    <text x="8" y="11" text-anchor="middle" fill="#007bff" font-size="11" font-weight="bold" font-family="serif">i</text>
                  </svg>
                  <span
                    v-if="activeTooltip === field.key"
                    style="display: block; position: absolute; left: 20px; top: -5px; background: #2c3e50; color: white; padding: 10px 14px; border-radius: 6px; z-index: 1000; font-size: 13px; font-weight: normal; min-width: 250px; max-width: 400px; white-space: normal; line-height: 1.4; box-shadow: 0 4px 12px rgba(0,0,0,0.3);"
                    v-html="field.help"
                  ></span>
                </span>
              </label>

              <!-- Password Field with Toggle -->
              <div v-if="isSecretField(field)" style="position: relative;">
                <input
                  :type="showPassword[field.key] ? 'text' : 'password'"
                  v-model="formValues[field.key]"
                  :placeholder="`Enter ${field.label}`"
                  style="width: 100%; padding: 8px; padding-right: 40px; border: 1px solid #ddd; border-radius: 4px;"
                />
                <button
                  type="button"
                  @click="togglePassword(field.key)"
                  style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 18px; color: #666; padding: 4px;"
                  :title="showPassword[field.key] ? 'Hide password' : 'Show password'"
                >
                  {{ showPassword[field.key] ? '👁️‍🗨️' : '👁️' }}
                </button>
              </div>

              <!-- Regular Text Field -->
              <input
                v-else
                type="text"
                v-model="formValues[field.key]"
                :placeholder="`Enter ${field.label}`"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
              />
            </div>
          </div>
        </div>
      </div>
    </template>
    <template v-if="step === 3" #footer>
      <button @click="step = 2">Back</button>
      <button @click="createRemote" :disabled="!isFormValid" style="background: #28a745;">
        Create Remote
      </button>
    </template>
  </BaseModal>

  <!-- View Remote Config Modal -->
  <BaseModal
    v-model="showViewConfigModal"
    :canClose="true"
    maxWidth="700px"
  >
    <template #header>📄 Remote Configuration: {{ viewingRemoteName }}</template>
    <template #body>
      <div style="position: relative;">
        <pre style="background: #f5f5f5; padding: 15px; border-radius: 4px; overflow-x: auto; max-height: 50vh; font-family: monospace; font-size: 12px; margin: 0;">{{ viewConfigText }}</pre>
        <button
          @click="copyConfig"
          style="position: absolute; top: 10px; right: 10px; background: #007bff; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 12px;"
          title="Copy to clipboard"
        >
          📋 Copy
        </button>
        <span
          v-if="showCopyTooltip"
          style="position: absolute; top: 10px; right: 80px; background: #28a745; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px;"
        >
          Copied!
        </span>
      </div>
    </template>
    <template #footer>
      <button @click="showViewConfigModal = false">Close</button>
    </template>
  </BaseModal>

  <!-- Edit Remote Config Modal -->
  <BaseModal
    v-model="showEditConfigModal"
    :canClose="true"
    maxWidth="700px"
  >
    <template #header>✏️ Edit Remote: {{ editingRemoteName }}</template>
    <template #body>
      <p style="margin-bottom: 10px; color: #666;">
        Edit the remote configuration. You can modify any field or rename the remote.
      </p>
      <textarea
        v-model="editConfigText"
        style="width: 100%; min-height: 400px; font-family: monospace; font-size: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; resize: vertical;"
      ></textarea>
    </template>
    <template #footer>
      <button @click="showEditConfigModal = false">Cancel</button>
      <button @click="saveEditedRemote" style="background: #28a745;">Save</button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import { apiCall } from '../../services/api'
import { useAppStore } from '../../stores/app'

const props = defineProps({
  modelValue: Boolean,
  activeRemotes: {
    type: Object,
    default: () => ({ left: '', right: '' })
  }
})

const emit = defineEmits(['update:modelValue', 'remotesChanged'])

const appStore = useAppStore()

// State
const step = ref(1)
const loading = ref(false)
const error = ref('')
const remotes = ref([])
const templates = ref([])
const selectedTemplate = ref(null)
const remoteName = ref('')
const formValues = ref({})
const customConfig = ref('')
const showPassword = ref({})
const activeTooltip = ref(null)
const hoveredRemote = ref(null)

// View Config Modal
const showViewConfigModal = ref(false)
const viewingRemoteName = ref('')
const viewConfigText = ref('')
const showCopyTooltip = ref(false)

// Edit Config Modal
const showEditConfigModal = ref(false)
const editingRemoteName = ref('')
const editConfigText = ref('')

/**
 * Check if remote is currently active in either pane
 */
function isRemoteActive(remoteName) {
  return props.activeRemotes.left === remoteName || props.activeRemotes.right === remoteName
}

/**
 * Check if field is a secret field
 */
function isSecretField(field) {
  const label = field.label.toLowerCase()
  return label.includes('password') || label.includes('secret') || label.includes('key')
}

/**
 * Form validation
 */
const isFormValid = computed(() => {
  if (selectedTemplate.value?.name === '__custom__') {
    return customConfig.value.trim().length > 0
  }

  if (!remoteName.value.trim()) return false
  if (!selectedTemplate.value?.fields) return true

  return selectedTemplate.value.fields.every(field => {
    return formValues.value[field.key]?.trim().length > 0
  })
})

/**
 * Load remotes and templates when modal opens
 */
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    step.value = 1
    await loadRemotes()
    await loadTemplates()
  }
})

/**
 * Load remotes from API
 */
async function loadRemotes() {
  loading.value = true
  error.value = ''

  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes || []
  } catch (err) {
    error.value = `Error loading remotes: ${err.message}`
  } finally {
    loading.value = false
  }
}

/**
 * Load templates from API
 */
async function loadTemplates() {
  try {
    const data = await apiCall('/api/templates')
    templates.value = data.templates || []
  } catch (err) {
    console.error('Error loading templates:', err)
  }
}

/**
 * Go to template selection
 */
function goToTemplateSelection() {
  step.value = 2
  selectedTemplate.value = null
  remoteName.value = ''
  formValues.value = {}
  customConfig.value = ''
  showPassword.value = {}
}

/**
 * Select a template
 */
function selectTemplate(template) {
  selectedTemplate.value = template
}

/**
 * Select custom template
 */
function selectCustomTemplate() {
  selectedTemplate.value = {
    name: '__custom__',
    fields: []
  }
}

/**
 * Go to configuration step
 */
function goToConfiguration() {
  step.value = 3
}

/**
 * Toggle password visibility
 */
function togglePassword(fieldKey) {
  showPassword.value[fieldKey] = !showPassword.value[fieldKey]
}

/**
 * Show tooltip
 */
function showTooltip(fieldKey) {
  activeTooltip.value = fieldKey
}

/**
 * Hide tooltip
 */
function hideTooltip(fieldKey) {
  activeTooltip.value = null
}

/**
 * Create remote
 */
async function createRemote() {
  try {
    if (selectedTemplate.value.name === '__custom__') {
      await apiCall('/api/remotes', 'POST', {
        raw_config: customConfig.value
      })
    } else {
      const config = { type: selectedTemplate.value.name }

      selectedTemplate.value.fields.forEach(field => {
        config[field.key] = formValues.value[field.key]?.trim() || ''
      })

      await apiCall('/api/remotes', 'POST', {
        name: remoteName.value.trim(),
        config
      })
    }

    emit('update:modelValue', false)
    emit('remotesChanged')
    alert('Remote created successfully!')
  } catch (err) {
    alert(`Failed to create remote: ${err.message}`)
  }
}

/**
 * View remote configuration
 */
async function viewRemote(name) {
  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(name)}/raw`)
    viewingRemoteName.value = name
    viewConfigText.value = data.raw_config
    showViewConfigModal.value = true
  } catch (err) {
    alert(`Failed to load remote configuration: ${err.message}`)
  }
}

/**
 * Copy config to clipboard
 */
async function copyConfig() {
  try {
    await navigator.clipboard.writeText(viewConfigText.value)
    showCopyTooltip.value = true
    setTimeout(() => {
      showCopyTooltip.value = false
    }, 1000)
  } catch (err) {
    console.error('Failed to copy to clipboard:', err)
    alert('Failed to copy to clipboard')
  }
}

/**
 * Edit remote
 */
async function editRemote(name) {
  if (isRemoteActive(name)) {
    alert(`Cannot edit remote "${name}" while it is in use. Please select a different remote first.`)
    return
  }

  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(name)}/raw`)
    editingRemoteName.value = name
    editConfigText.value = data.raw_config
    showEditConfigModal.value = true
  } catch (err) {
    alert(`Failed to load remote configuration: ${err.message}`)
  }
}

/**
 * Save edited remote
 */
async function saveEditedRemote() {
  try {
    const data = await apiCall(`/api/remotes/${encodeURIComponent(editingRemoteName.value)}`, 'PUT', {
      raw_config: editConfigText.value
    })

    const newName = data.new_name
    const isRename = newName !== editingRemoteName.value

    showEditConfigModal.value = false
    await loadRemotes()
    emit('remotesChanged')

    alert(isRename ?
      `Remote successfully renamed from "${editingRemoteName.value}" to "${newName}"` :
      `Remote "${newName}" updated successfully`)
  } catch (err) {
    alert(`Failed to save remote: ${err.message}`)
  }
}

/**
 * Delete remote
 */
async function deleteRemote(name) {
  if (isRemoteActive(name)) {
    alert(`Cannot delete remote "${name}" while it is in use. Please select a different remote first.`)
    return
  }

  if (!confirm(`Are you sure you want to delete the remote "${name}"?`)) {
    return
  }

  try {
    await apiCall(`/api/remotes/${encodeURIComponent(name)}`, 'DELETE')
    await loadRemotes()
    emit('remotesChanged')
    alert(`Remote "${name}" deleted successfully`)
  } catch (err) {
    alert(`Failed to delete remote: ${err.message}`)
  }
}

/**
 * Refresh OAuth token
 */
async function refreshOAuth(name) {
  alert('OAuth refresh functionality will be implemented with the OAuth modal')
  // TODO: Implement OAuth refresh when OAuth modal is ready
}
</script>
