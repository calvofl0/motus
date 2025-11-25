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
              v-for="remote in sortedRemotes"
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
                  :disabled="isActiveRemote(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '18px',
                    cursor: isActiveRemote(remote.name) ? 'not-allowed' : 'pointer',
                    color: isActiveRemote(remote.name) ? '#ccc' : '#28a745',
                    padding: '4px 8px',
                    marginRight: '4px'
                  }"
                  :title="isActiveRemote(remote.name) ? 'Cannot refresh OAuth while remote is in use' : 'Refresh OAuth token'"
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
                    padding: '4px 8px',
                    marginRight: '4px',
                    filter: isActiveRemote(remote.name) ? 'grayscale(100%) opacity(0.4)' : 'none'
                  }"
                  :title="isActiveRemote(remote.name) ? 'Cannot edit remote while in use' : 'Edit remote'"
                >✏️</button>

                <button
                  @click.stop="deleteRemote(remote.name)"
                  :disabled="isActiveRemote(remote.name)"
                  :style="{
                    background: 'none',
                    border: 'none',
                    fontSize: '14px',
                    cursor: isActiveRemote(remote.name) ? 'not-allowed' : 'pointer',
                    padding: '4px 8px',
                    filter: isActiveRemote(remote.name) ? 'grayscale(100%) opacity(0.4)' : 'none'
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
        <div
          ref="templateListContainer"
          tabindex="0"
          @keydown="handleTemplateKeydown"
          style="overflow-y: auto; max-height: 50vh; margin-bottom: 15px; display: flex; flex-direction: column; gap: 10px; outline: none;"
        >
          <div
            v-for="(template, index) in templates"
            :key="template.name"
            :ref="el => templateItems[index] = el"
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
                ref="remoteNameInput"
                v-model="remoteName"
                type="text"
                placeholder="Enter remote name"
                pattern="[a-zA-Z0-9_\-]+"
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
                @keydown.enter="handleFieldEnter('remoteName')"
              />
              <small style="color: #666;">Use only letters, numbers, underscores, and hyphens</small>
            </div>

            <!-- Template fields -->
            <div v-for="(field, index) in selectedTemplate.fields" :key="field.key">
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
              <div style="display: flex; gap: 8px; align-items: flex-start; position: relative;">
                <div style="flex: 1; position: relative;">
                  <input
                    :ref="el => fieldInputs[index] = el"
                    v-model="formValues[field.key]"
                    :type="isSecretField(field) && !fieldVisibility[field.key] ? 'password' : 'text'"
                    :placeholder="`Enter ${field.label}`"
                    style="width: 100%; padding: 8px; padding-right: 35px; border: 1px solid #ddd; border-radius: 4px;"
                    @keydown.enter="handleFieldEnter(field.key)"
                  />
                  <button
                    v-if="isSecretField(field)"
                    @click.prevent="toggleFieldVisibility(field.key)"
                    type="button"
                    style="position: absolute; right: 5px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; padding: 5px; color: #666;"
                    :title="fieldVisibility[field.key] ? 'Hide password' : 'Show password'"
                  >
                    <!-- Eye icon (show password) -->
                    <svg v-if="!fieldVisibility[field.key]" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                    </svg>
                    <!-- Eye with diagonal line (hide password) -->
                    <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                      <circle cx="12" cy="12" r="3"></circle>
                      <line x1="1" y1="23" x2="23" y2="1"></line>
                    </svg>
                  </button>
                </div>
                <button
                  v-if="isTokenField(field) && !formValues[field.key]?.trim()"
                  @click.prevent="showOAuthHelp"
                  style="padding: 8px 12px; background: #17a2b8; color: white; border: none; border-radius: 4px; cursor: pointer; white-space: nowrap; font-size: 13px;"
                  title="Get OAuth token"
                >
                  Get Token
                </button>
              </div>
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
          @click="startWizard"
          style="background: #28a745;"
        >+ Add Remote</button>
      </template>

      <!-- Step 2 Footer -->
      <template v-else-if="currentStep === 2">
        <button
          @click="showCustomRemoteForm"
          style="background: #6c757d; margin-right: auto;"
        >Custom Remote</button>
        <button @click="showRemotesList">Cancel</button>
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

  <!-- Custom Remote Method Selection Modal -->
  <CustomRemoteMethodModal
    v-model="showCustomMethodModal"
    @method-selected="handleCustomMethodSelected"
  />

  <!-- Custom Remote Wizard Modal -->
  <CustomRemoteWizardModal
    v-model="showCustomWizardModal"
    @remote-created="handleCustomRemoteCreated"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../../stores/app'
import { apiCall } from '../../services/api'
import BaseModal from './BaseModal.vue'
import OAuthInteractiveModal from './OAuthInteractiveModal.vue'
import CustomRemoteMethodModal from './CustomRemoteMethodModal.vue'
import CustomRemoteWizardModal from './CustomRemoteWizardModal.vue'

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
const fieldVisibility = ref({}) // Track password field visibility
const customConfig = ref('')

// Input refs for ENTER key navigation
const remoteNameInput = ref(null)
const fieldInputs = ref([])
const templateListContainer = ref(null)
const templateItems = ref([])

// Modals
const showCustomMethodModal = ref(false)
const showCustomWizardModal = ref(false)
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

// Sort remotes alphabetically for display (preserves config file order for saves)
const sortedRemotes = computed(() => {
  return [...remotes.value].sort((a, b) => {
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
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

  // Focus template list container for step 2 (for keyboard navigation)
  if (newStep === 2) {
    await nextTick()
    if (templateListContainer.value) {
      templateListContainer.value.focus()
    }
  } else {
    // Refocus main modal overlay after step change (but not for step 2)
    const mainOverlay = document.querySelector('.modal-overlay')
    if (mainOverlay) {
      mainOverlay.focus()
    }
  }
})

// Watch child modals closing to refocus parent modal
watch([showCustomMethodModal, showCustomWizardModal, showCustomConfigModal, showViewConfigModal, showEditConfigModal, showOAuthModal], async ([method, wizard, custom, view, edit, oauth], [prevMethod, prevWizard, prevCustom, prevView, prevEdit, prevOAuth]) => {
  // If any child modal just closed (was true, now false) and main modal is still open
  if (appStore.showManageRemotesModal) {
    if ((prevMethod && !method) || (prevWizard && !wizard) || (prevCustom && !custom) || (prevView && !view) || (prevEdit && !edit) || (prevOAuth && !oauth)) {
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

// Show custom remote method selection
function showCustomRemoteForm() {
  // Exit wizard and return to main view
  showRemotesList()
  // Open method selection modal
  showCustomMethodModal.value = true
}

// Handle custom method selection
function handleCustomMethodSelected(method) {
  if (method === 'manual') {
    // Open manual configuration modal
    customConfig.value = ''
    showCustomConfigModal.value = true
  } else if (method === 'wizard') {
    // Open wizard modal
    showCustomWizardModal.value = true
  }
}

// Handle custom remote creation completion
async function handleCustomRemoteCreated(remoteName) {
  // Reload remotes list
  await loadRemotesList()
  console.log(`Custom remote '${remoteName}' created successfully`)

  // Check if the created remote needs OAuth token
  const createdRemote = remotes.value.find(r => r.name === remoteName)
  if (createdRemote && createdRemote.is_oauth) {
    // Check if token is empty by fetching the raw config
    try {
      const configData = await apiCall(`/api/remotes/${encodeURIComponent(remoteName)}/raw`)
      const rawConfig = configData.raw_config || ''

      // Parse token from raw config (format: "token = value")
      // Use [^\r\n]* to explicitly stop at line boundaries (handles both \n and \r\n)
      const tokenMatch = rawConfig.match(/^\s*token\s*=\s*([^\r\n]*)$/m)
      const token = tokenMatch ? tokenMatch[1].trim() : ''

      // If token is empty, open OAuth modal
      if (!token || token.trim() === '') {
        oauthRemoteName.value = remoteName
        showOAuthModal.value = true
      }
    } catch (error) {
      console.error('Failed to check remote token:', error)
    }
  }
}

// Start the wizard (fresh start)
function startWizard() {
  // Clear all wizard state for a fresh start
  selectedTemplate.value = null
  formValues.value = {}
  fieldVisibility.value = {}
  remoteName.value = ''
  currentStep.value = 2
}

// Show template selection (wizard step 1) - used when going back from step 3
function showTemplateSelection() {
  // Just go to step 2, don't clear any state - preserve it for navigation
  currentStep.value = 2
}

// Show remotes list (exit wizard)
function showRemotesList() {
  // Going back to main view - clear wizard state
  currentStep.value = 1
  selectedTemplate.value = null
  formValues.value = {}
  remoteName.value = ''
}

// Show remote form (wizard step 2)
function showRemoteForm() {
  // Initialize form values for selected template if not already done
  if (selectedTemplate.value && Object.keys(formValues.value).length === 0) {
    const initialValues = {}
    for (const field of selectedTemplate.value.fields) {
      initialValues[field.key] = ''
    }
    formValues.value = initialValues
  }
  currentStep.value = 3
}

// Select template
function selectTemplate(templateName) {
  const newTemplate = templates.value.find(t => t.name === templateName)

  // If selecting a different template, clear the form values
  if (selectedTemplate.value?.name !== newTemplate?.name) {
    selectedTemplate.value = newTemplate

    // Initialize form values for new template
    const initialValues = {}
    if (newTemplate?.fields) {
      for (const field of newTemplate.fields) {
        initialValues[field.key] = ''
      }
    }
    formValues.value = initialValues
    fieldVisibility.value = {} // Reset password visibility
    remoteName.value = ''
  } else {
    // Same template selected, just ensure it's set
    selectedTemplate.value = newTemplate
  }
}

// Handle keyboard navigation in template selection
function handleTemplateKeydown(e) {
  if (e.key === 'Enter' && selectedTemplate.value) {
    // ENTER key with selection -> go to next step
    e.preventDefault()
    showRemoteForm()
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    // Arrow key navigation
    e.preventDefault()

    const currentIndex = selectedTemplate.value
      ? templates.value.findIndex(t => t.name === selectedTemplate.value.name)
      : -1

    let newIndex
    if (e.key === 'ArrowDown') {
      if (currentIndex === -1) {
        newIndex = 0 // Select first
      } else {
        newIndex = Math.min(currentIndex + 1, templates.value.length - 1)
      }
    } else { // ArrowUp
      if (currentIndex === -1) {
        newIndex = templates.value.length - 1 // Select last
      } else {
        newIndex = Math.max(currentIndex - 1, 0)
      }
    }

    if (newIndex !== currentIndex && templates.value[newIndex]) {
      selectTemplate(templates.value[newIndex].name)

      // Scroll selected item into view
      nextTick(() => {
        const item = templateItems.value[newIndex]
        if (item) {
          item.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        }
      })
    }
  }
}

// Handle ENTER key in fields - move to next empty field or create if all filled
function handleFieldEnter(currentFieldKey) {
  // Check remote name first
  if (currentFieldKey === 'remoteName') {
    if (!remoteName.value.trim()) return

    // Find first empty field
    if (selectedTemplate.value?.fields) {
      const firstEmptyIndex = selectedTemplate.value.fields.findIndex(f => !formValues.value[f.key]?.trim())
      if (firstEmptyIndex >= 0 && fieldInputs.value[firstEmptyIndex]) {
        fieldInputs.value[firstEmptyIndex].focus()
        return
      }
    }

    // All fields filled, create remote
    if (isFormValid.value) {
      createRemote()
    }
    return
  }

  // For template fields, find next empty field
  const fields = selectedTemplate.value?.fields || []
  const currentIndex = fields.findIndex(f => f.key === currentFieldKey)

  if (currentIndex >= 0) {
    // Look for next empty field
    for (let i = currentIndex + 1; i < fields.length; i++) {
      if (!formValues.value[fields[i].key]?.trim()) {
        if (fieldInputs.value[i]) {
          fieldInputs.value[i].focus()
        }
        return
      }
    }

    // No more empty fields, create remote if valid
    if (isFormValid.value) {
      createRemote()
    }
  }
}

// Is secret field
function isSecretField(field) {
  const label = field.label.toLowerCase()
  return label.includes('password') || label.includes('secret') || label.includes('key') || label.includes('token')
}

// Toggle password field visibility
function toggleFieldVisibility(fieldKey) {
  fieldVisibility.value[fieldKey] = !fieldVisibility.value[fieldKey]
}

// Is sensitive key
function isSensitiveKey(key) {
  const lowerKey = key.toLowerCase()
  return lowerKey.includes('password') || lowerKey.includes('secret') || lowerKey.includes('key') || lowerKey.includes('token')
}

// Is token field (for OAuth)
function isTokenField(field) {
  const lowerKey = field.key.toLowerCase()
  const lowerLabel = field.label.toLowerCase()
  return lowerKey.includes('token') || lowerLabel.includes('token')
}

// Create remote from template
async function createRemote() {
  try {
    // Track if any token field was empty
    let hasEmptyTokenField = false

    // Build values dictionary using field labels as keys
    const values = {}
    for (const field of selectedTemplate.value.fields) {
      const value = formValues.value[field.key].trim()
      values[field.label] = value

      // Check if this is a token field and it's empty
      if (isTokenField(field) && !value) {
        hasEmptyTokenField = true
      }
    }

    const newRemoteName = remoteName.value.trim()

    // Send template name and values (labels -> values)
    await apiCall('/api/remotes', 'POST', {
      name: newRemoteName,
      template: selectedTemplate.value.name,
      values: values
    })

    await loadRemotesList()

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))

    // Check if the created remote needs OAuth token BEFORE going back to list
    const createdRemote = remotes.value.find(r => r.name === newRemoteName)
    let needsOAuth = false

    console.log(`[ManageRemotesModal] Created remote: ${newRemoteName}, is_oauth=${createdRemote?.is_oauth}`)

    if (createdRemote && createdRemote.is_oauth) {
      // Check if token is empty by fetching the raw config
      try {
        const configData = await apiCall(`/api/remotes/${encodeURIComponent(newRemoteName)}/raw`)
        const rawConfig = configData.raw_config || ''

        // Parse token from raw config (format: "token = value")
        // Use [^\r\n]* to explicitly stop at line boundaries (handles both \n and \r\n)
        const tokenMatch = rawConfig.match(/^\s*token\s*=\s*([^\r\n]*)$/m)
        const token = tokenMatch ? tokenMatch[1].trim() : ''

        console.log(`[ManageRemotesModal] Token check for ${newRemoteName}: token="${token}", isEmpty=${!token || token.trim() === ''}`)

        // If token is empty, we'll need to open OAuth modal
        if (!token || token.trim() === '') {
          needsOAuth = true
          oauthRemoteName.value = newRemoteName
        }
      } catch (error) {
        console.error('Failed to check remote token:', error)
      }
    }

    // Return to list view
    showRemotesList()

    // Open OAuth modal if needed (after returning to list)
    if (needsOAuth) {
      console.log(`[ManageRemotesModal] Auto-opening OAuth modal for ${newRemoteName}`)
      // Use setTimeout to ensure modal state has settled
      await new Promise(resolve => setTimeout(resolve, 100))
      oauthRemoteName.value = newRemoteName
      showOAuthModal.value = true
      console.log(`[ManageRemotesModal] OAuth modal opened, showOAuthModal=${showOAuthModal.value}`)
    }
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

    // Don't show success alert, only show errors
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

// Show OAuth help for creating remote
function showOAuthHelp() {
  alert(
    'Leave the token field empty when creating the remote.\n\n' +
    'After the remote is created, you will be automatically prompted to refresh the OAuth token.'
  )
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

.help-tooltip a {
  color: #58C4FF;
  text-decoration: underline;
}

.help-tooltip a:hover {
  color: #8FD5FF;
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
