<template>
  <!-- Main Manage Remotes Modal -->
  <BaseModal
    ref="modalRef"
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
      <div v-if="currentStep === 1" class="remotes-list-container">
        <ModalTable
          ref="modalTableRef"
          :items="sortedRemotes"
          :columns="remoteColumns"
          v-model:selected-index="selectedRemoteIndex"
          :grid-template-columns="'1fr 1fr 140px'"
          :row-key="remote => remote.name"
          :loading="loading"
          loading-message="Loading remotes..."
          empty-message="No remotes configured"
          :parentModal="modalRef"
          @row-click="handleRemoteRowClick"
          @keydown="handleCustomKeyDown"
        >
          <!-- Custom cell: Name -->
          <template #cell-name="{ item }">
            <span class="col-name">{{ item.name }}</span>
          </template>

          <!-- Custom cell: Type -->
          <template #cell-type="{ item }">
            <span class="col-type">{{ item.type }}</span>
          </template>

          <!-- Custom cell: Actions -->
          <template #cell-actions="{ item }">
            <div class="col-actions">
              <button
                v-if="item.is_oauth"
                class="remote-icon-btn oauth-refresh-btn"
                @click.stop="refreshOAuth(item.name)"
                :disabled="isActiveRemote(item.name) || item.is_readonly"
                :class="{ 'disabled': isActiveRemote(item.name) || item.is_readonly }"
                :title="item.is_readonly ? 'Cannot refresh OAuth for read-only remote' : (isActiveRemote(item.name) ? 'Cannot refresh OAuth while remote is in use' : 'Refresh OAuth token')"
              >↻</button>
              <span v-else class="oauth-spacer"></span>

              <button
                class="remote-icon-btn"
                @click.stop="editRemoteConfig(item.name)"
                :disabled="isActiveRemote(item.name) || item.is_readonly"
                :class="{ 'disabled': isActiveRemote(item.name) || item.is_readonly }"
                :title="item.is_readonly ? 'Cannot edit read-only remote' : (isActiveRemote(item.name) ? 'Cannot edit remote while in use' : 'Edit remote')"
              >✏️</button>

              <button
                class="remote-icon-btn"
                @click.stop="deleteRemote(item.name)"
                :disabled="isActiveRemote(item.name) || item.is_readonly"
                :class="{ 'disabled': isActiveRemote(item.name) || item.is_readonly }"
                :title="item.is_readonly ? 'Cannot delete read-only remote' : (isActiveRemote(item.name) ? 'Cannot delete remote while in use' : 'Delete remote')"
              >🗑️</button>
            </div>
          </template>
        </ModalTable>
      </div>

      <!-- Step 2: Select Template -->
      <div v-else-if="currentStep === 2">
        <p class="template-intro">Choose a template for the new remote:</p>
        <div
          ref="templateListContainer"
          tabindex="0"
          @keydown="handleTemplateKeydown"
          class="template-list-container"
        >
          <div
            v-for="(template, index) in templates"
            :key="template.name"
            :ref="el => templateItems[index] = el"
            @click="selectTemplate(template.name)"
            class="template-item"
            :class="{ 'template-selected': selectedTemplate?.name === template.name }"
          >
            <strong class="template-name">{{ template.name }}</strong>
            <small v-if="template.fields && template.fields.length > 0" class="template-fields">
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
                style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
                :style="{ borderColor: remoteNameError ? '#dc3545' : '#ddd' }"
                @input="validateRemoteNameInput"
                @keydown.enter="handleFieldEnter('remoteName')"
              />
              <small v-if="remoteNameError" style="color: #dc3545;">{{ remoteNameError }}</small>
              <small v-else style="color: #666;">May contain letters, numbers, _, -, ., +, @, and space. Cannot start with '-' or space, or end with space.</small>
            </div>

            <!-- Template fields -->
            <div v-for="(field, index) in selectedTemplate.fields" :key="field.key">
              <label style="display: block; margin-bottom: 4px; font-weight: 500;">
                {{ field.label }}
                <span v-if="field.help" class="help-icon" style="display: inline-block; cursor: help; position: relative; margin-left: 4px;">
                  <svg width="16" height="16" viewBox="0 0 16 16" style="vertical-align: middle;">
                    <text x="8" y="12" text-anchor="middle" fill="#007bff" font-size="14" font-weight="bold" font-style="italic" font-family="serif">i</text>
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
          class="btn btn-success"
        >+ Add Remote</button>
      </template>

      <!-- Step 2 Footer -->
      <template v-else-if="currentStep === 2">
        <button
          @click="showCustomRemoteForm"
          class="btn btn-success"
          style="margin-right: auto;"
        >Custom Remote</button>
        <button @click="showRemotesList" class="btn btn-secondary">Cancel</button>
        <button
          @click="showRemoteForm"
          :disabled="!selectedTemplate"
          class="btn btn-primary"
        >Next</button>
      </template>

      <!-- Step 3 Footer -->
      <template v-else-if="currentStep === 3">
        <button @click="showTemplateSelection" class="btn btn-secondary">Back</button>
        <button
          @click="createRemote"
          :disabled="!isFormValid"
          class="btn btn-success"
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
      <p class="config-title"><strong>Custom Remote Configuration</strong></p>
      <p class="config-help">Enter the rclone configuration for your custom remote. Must include the [remote_name] section header.</p>
      <textarea
        v-model="customConfig"
        class="config-textarea"
        placeholder="[myremote]&#10;type = s3&#10;access_key_id = YOUR_ACCESS_KEY&#10;secret_access_key = YOUR_SECRET_KEY&#10;region = us-east-1&#10;..."
      ></textarea>
    </template>
    <template #footer>
      <button @click="showCustomConfigModal = false" class="btn btn-secondary">Cancel</button>
      <button
        @click="createCustomRemote"
        :disabled="!isCustomConfigValid"
        class="btn btn-success"
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
      <button @click="copyConfigToClipboard" class="btn btn-success copy-config-btn">
        📋 Copy to Clipboard
        <span v-if="showCopyTooltip" class="copy-tooltip">Copied!</span>
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
      <p class="config-help">Edit the rclone configuration for this remote. You can rename the remote by changing the value between [brackets].</p>
      <textarea
        v-model="editConfigText"
        class="config-textarea"
        placeholder="[remote_name]&#10;type = s3&#10;..."
      ></textarea>
    </template>
    <template #footer>
      <button @click="showEditConfigModal = false" class="btn btn-secondary">Cancel</button>
      <button @click="saveRemoteConfig" class="btn btn-success">Save</button>
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

  <!-- Keyboard Shortcuts Modal -->
  <ManageRemotesShortcutsModal
    v-model="showShortcutsModal"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { useAppStore } from '../../stores/app'
import { apiCall } from '../../services/api'
import { validateRemoteName } from '../../utils/remoteNameValidation'
import { sortRemotes } from '../../utils/remoteSorting'
import BaseModal from './BaseModal.vue'
import ModalTable from './ModalTable.vue'
import OAuthInteractiveModal from './OAuthInteractiveModal.vue'
import CustomRemoteMethodModal from './CustomRemoteMethodModal.vue'
import CustomRemoteWizardModal from './CustomRemoteWizardModal.vue'
import ManageRemotesShortcutsModal from './ManageRemotesShortcutsModal.vue'

const appStore = useAppStore()

// Column definitions for remotes table
const remoteColumns = [
  { key: 'name', header: 'Name' },
  { key: 'type', header: 'Type' },
  { key: 'actions', header: 'Actions' }
]

// State
const currentStep = ref(1)
const loading = ref(false)
const remotes = ref([])
const selectedRemoteIndex = ref(-1) // For keyboard navigation
const modalRef = ref(null)
const modalTableRef = ref(null)
const templates = ref([])
const templatesAvailable = ref(false)
const selectedTemplate = ref(null)
const remoteName = ref('')
const remoteNameError = ref('')
const formValues = ref({})
const fieldVisibility = ref({}) // Track password field visibility
const customConfig = ref('')

// Cache for alias target remotes (remoteName -> targetRemoteName)
const aliasTargetCache = ref(new Map())
// Set of remotes that are currently in use (including via aliases)
const activeRemoteNames = ref(new Set())

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
const showShortcutsModal = ref(false)

// Validate remote name input
function validateRemoteNameInput() {
  const validation = validateRemoteName(remoteName.value)
  remoteNameError.value = validation.error || ''
}

// Computed
const isFormValid = computed(() => {
  if (!selectedTemplate.value) return false
  if (!remoteName.value.trim()) return false
  if (remoteNameError.value) return false

  for (const field of selectedTemplate.value.fields || []) {
    if (!formValues.value[field.key]?.trim()) return false
  }

  return true
})

const isCustomConfigValid = computed(() => {
  return customConfig.value.trim() && /^\[.+?\]/m.test(customConfig.value)
})

// Sort remotes: readonly/extra remotes first, then user remotes, alphabetically within each group
const sortedRemotes = computed(() => {
  return sortRemotes(remotes.value)
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

    // Auto-focus the remote name input field
    await nextTick()
    if (remoteNameInput.value) {
      remoteNameInput.value.focus()
    }
  }

  // Focus template list container for step 2 (for keyboard navigation)
  else if (newStep === 2) {
    await nextTick()
    if (templateListContainer.value) {
      templateListContainer.value.focus()
    }
  }
  // Refocus main modal overlay for other steps
  else {
    const mainOverlay = document.querySelector('.modal-overlay')
    if (mainOverlay) {
      mainOverlay.focus()
    }
  }
})

// Watch child modals closing to refocus parent modal
watch([showCustomMethodModal, showCustomWizardModal, showCustomConfigModal, showViewConfigModal, showEditConfigModal, showOAuthModal, showShortcutsModal], async ([method, wizard, custom, view, edit, oauth, shortcuts], [prevMethod, prevWizard, prevCustom, prevView, prevEdit, prevOAuth, prevShortcuts]) => {
  // If any child modal just closed (was true, now false) and main modal is still open
  if (appStore.showManageRemotesModal) {
    if ((prevMethod && !method) || (prevWizard && !wizard) || (prevCustom && !custom) || (prevView && !view) || (prevEdit && !edit) || (prevOAuth && !oauth) || (prevShortcuts && !shortcuts)) {
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

      const showTooltip = () => {
        clearTimeout(hideTimeout)
        tooltip.style.display = 'block'
      }

      const hideTooltip = () => {
        hideTimeout = setTimeout(() => {
          tooltip.style.display = 'none'
        }, 200) // Increased delay for easier tooltip hovering
      }

      // Show on icon hover
      icon.addEventListener('mouseenter', showTooltip)

      // Hide when leaving icon (with delay)
      icon.addEventListener('mouseleave', hideTooltip)

      // Keep visible when hovering tooltip
      tooltip.addEventListener('mouseenter', showTooltip)

      // Hide when leaving tooltip
      tooltip.addEventListener('mouseleave', hideTooltip)
    }
  })
}

// Load remotes list
async function loadRemotesList() {
  loading.value = true
  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes || []
    // Clear alias cache when remotes are reloaded
    aliasTargetCache.value.clear()
    // Update active remotes to handle alias chains
    await updateActiveRemotes()
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

/**
 * Get the target remote name from an alias remote's config
 * Returns null if not an alias or if target can't be determined
 */
async function getAliasTarget(remoteName) {
  // Check cache first
  if (aliasTargetCache.value.has(remoteName)) {
    return aliasTargetCache.value.get(remoteName)
  }

  // Find the remote in our list
  const remote = remotes.value.find(r => r.name === remoteName)
  if (!remote || remote.type !== 'alias') {
    // Not an alias, cache null
    aliasTargetCache.value.set(remoteName, null)
    return null
  }

  try {
    // Get raw config
    const data = await apiCall(`/api/remotes/${remoteName}/raw`)
    const rawConfig = data.raw_config || ''

    // Parse the "remote = " field
    const lines = rawConfig.split(/\r?\n/)
    for (const line of lines) {
      const trimmedLine = line.trim()
      if (trimmedLine.startsWith('remote =') || trimmedLine.startsWith('remote=')) {
        const equalsIndex = trimmedLine.indexOf('=')
        const targetValue = trimmedLine.substring(equalsIndex + 1).trim()

        // Extract remote name (before the colon)
        // e.g., "onedrive:/path" -> "onedrive"
        // or just "onedrive" -> "onedrive"
        let targetRemote = targetValue
        if (targetValue.includes(':')) {
          targetRemote = targetValue.split(':', 2)[0]
        }

        // Cache and return
        aliasTargetCache.value.set(remoteName, targetRemote)
        return targetRemote
      }
    }

    // No remote field found
    aliasTargetCache.value.set(remoteName, null)
    return null
  } catch (error) {
    console.error(`Failed to get alias target for ${remoteName}:`, error)
    return null
  }
}

/**
 * Recursively add all remotes in an alias chain to the active set
 */
async function addAliasChain(remoteName, activeSet, visitedRemotes = new Set()) {
  // Prevent infinite loops
  if (visitedRemotes.has(remoteName)) {
    return
  }
  visitedRemotes.add(remoteName)

  // Get the target of this remote (if it's an alias)
  const target = await getAliasTarget(remoteName)
  if (target) {
    // Add the target to active set
    activeSet.add(target)

    // Recursively trace the target
    await addAliasChain(target, activeSet, visitedRemotes)
  }
}

/**
 * Update the set of active remote names (including alias targets)
 */
async function updateActiveRemotes() {
  const active = new Set()

  // Start with directly active remotes
  const directlyActive = [appStore.leftPane.remote, appStore.rightPane.remote].filter(Boolean)
  directlyActive.forEach(name => active.add(name))

  // For each directly active remote, trace alias chain
  for (const remoteName of directlyActive) {
    await addAliasChain(remoteName, active)
  }

  activeRemoteNames.value = active
}

// Check if remote is active (includes remotes used via alias chains)
function isActiveRemote(remoteName) {
  return activeRemoteNames.value.has(remoteName)
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

  // Notify other components that remotes have changed
  window.dispatchEvent(new CustomEvent('remotes-changed'))

  // Check if the created remote needs OAuth token
  const createdRemote = remotes.value.find(r => r.name === remoteName)
  if (createdRemote && createdRemote.is_oauth) {
    // Check if token is empty by fetching the raw config
    try {
      const configData = await apiCall(`/api/remotes/${encodeURIComponent(remoteName)}/raw`)
      const rawConfig = configData.raw_config || ''

      // Parse token from raw config by splitting lines
      let token = ''
      const lines = rawConfig.split(/\r?\n/)
      for (const line of lines) {
        const trimmedLine = line.trim()
        if (trimmedLine.startsWith('token =') || trimmedLine.startsWith('token=')) {
          // Extract value after 'token ='
          const equalsIndex = trimmedLine.indexOf('=')
          token = trimmedLine.substring(equalsIndex + 1).trim()
          break
        }
      }

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
  remoteNameError.value = ''
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
    remoteNameError.value = ''
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

    if (createdRemote && createdRemote.is_oauth) {
      // Check if token is empty by fetching the raw config
      try {
        const configData = await apiCall(`/api/remotes/${encodeURIComponent(newRemoteName)}/raw`)
        const rawConfig = configData.raw_config || ''

        // Parse token from raw config by splitting lines
        let token = ''
        const lines = rawConfig.split(/\r?\n/)
        for (const line of lines) {
          const trimmedLine = line.trim()
          if (trimmedLine.startsWith('token =') || trimmedLine.startsWith('token=')) {
            // Extract value after 'token ='
            const equalsIndex = trimmedLine.indexOf('=')
            token = trimmedLine.substring(equalsIndex + 1).trim()
            break
          }
        }

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
function handleRemoteRowClick(remote, index) {
  // Note: selectedRemoteIndex is already updated by v-model
  viewRemoteConfig(remote.name)
}

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

// Keyboard navigation for Step 1 (remotes list)
// Custom keyboard shortcuts (beyond basic navigation handled by ModalTable)
// Note: Modal stack automatically prevents handling when child modals are open
function handleCustomKeyDown(event) {
  // Only handle on Step 1
  if (currentStep.value !== 1) return

  // F1 - Show keyboard shortcuts
  if (event.key === 'F1') {
    event.preventDefault()
    event.stopPropagation()
    showShortcutsModal.value = true
    return
  }

  const sortedRemotesList = sortedRemotes.value
  if (sortedRemotesList.length === 0) return

  // Enter - View config
  if (event.key === 'Enter' && selectedRemoteIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    const remote = sortedRemotesList[selectedRemoteIndex.value]
    viewRemoteConfig(remote.name)
  }
  // E - Edit config
  else if ((event.key === 'e' || event.key === 'E') && selectedRemoteIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    const remote = sortedRemotesList[selectedRemoteIndex.value]
    if (!isActiveRemote(remote.name) && !remote.is_readonly) {
      editRemoteConfig(remote.name)
    }
  }
  // R - Refresh OAuth
  else if ((event.key === 'r' || event.key === 'R') && selectedRemoteIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    const remote = sortedRemotesList[selectedRemoteIndex.value]
    if (remote.is_oauth && !isActiveRemote(remote.name) && !remote.is_readonly) {
      refreshOAuth(remote.name)
    }
  }
  // D/Delete - Delete remote
  else if ((event.key === 'd' || event.key === 'D' || event.key === 'Delete') && selectedRemoteIndex.value >= 0) {
    event.preventDefault()
    event.stopPropagation()
    const remote = sortedRemotesList[selectedRemoteIndex.value]
    if (!isActiveRemote(remote.name) && !remote.is_readonly) {
      deleteRemote(remote.name)
    }
  }
}

// Watch for modal open/close to manage keyboard listener
watch(() => appStore.showManageRemotesModal, (isOpen) => {
  if (isOpen) {
    // Start keyboard listener in ModalTable when on step 1
    nextTick(() => {
      if (modalTableRef.value && currentStep.value === 1) {
        modalTableRef.value.startKeyboardListener()
      }
    })
  } else {
    // Stop keyboard listener in ModalTable
    if (modalTableRef.value) {
      modalTableRef.value.stopKeyboardListener()
    }
    selectedRemoteIndex.value = -1 // Reset selection
  }
})

// Watch for step changes to manage keyboard listener
watch(currentStep, (newStep, oldStep) => {
  if (newStep === 1 && oldStep !== 1 && appStore.showManageRemotesModal) {
    // Entering step 1, start keyboard listener
    nextTick(() => {
      if (modalTableRef.value) {
        modalTableRef.value.startKeyboardListener()
      }
    })
  } else if (newStep !== 1 && oldStep === 1) {
    // Leaving step 1, stop keyboard listener
    if (modalTableRef.value) {
      modalTableRef.value.stopKeyboardListener()
    }
  }
})

// Watch step changes to reset selection
watch(currentStep, () => {
  selectedRemoteIndex.value = -1
})

// Watch view config modal to add/remove keyboard listener
watch(showViewConfigModal, (isOpen) => {
  if (isOpen) {
    document.addEventListener('keydown', handleViewConfigKeyDown)
  } else {
    document.removeEventListener('keydown', handleViewConfigKeyDown)
  }
})

// Watch pane remotes to update active remotes (for alias chain handling)
watch([() => appStore.leftPane.remote, () => appStore.rightPane.remote], async () => {
  // Only update if modal is open and remotes are loaded
  if (appStore.showManageRemotesModal && remotes.value.length > 0) {
    await updateActiveRemotes()
  }
})

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('keydown', handleViewConfigKeyDown)
})

// Edit remote config
async function editRemoteConfig(name) {
  // Check if readonly
  const remote = remotes.value.find(r => r.name === name)
  if (remote?.is_readonly) {
    alert(`Cannot edit read-only remote "${name}". This remote is from a read-only configuration file.`)
    return
  }

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
  // Check if readonly
  const remote = remotes.value.find(r => r.name === name)
  if (remote?.is_readonly) {
    alert(`Cannot delete read-only remote "${name}". This remote is from a read-only configuration file.`)
    return
  }

  if (isActiveRemote(name)) {
    alert(`Cannot delete remote "${name}" while it is in use. Please select a different remote first.`)
    return
  }

  if (!confirm(`Are you sure you want to delete the remote "${name}"?`)) {
    // Restore focus to modal after cancel
    setTimeout(() => {
      const modalOverlay = document.querySelector('.modal-overlay')
      if (modalOverlay) {
        modalOverlay.focus()
      }
    }, 100)
    return
  }

  try {
    await apiCall(`/api/remotes/${name}`, 'DELETE')
    await loadRemotesList()

    // Trigger remotes changed event
    window.dispatchEvent(new CustomEvent('remotes-changed'))

    // Restore focus to modal after delete
    setTimeout(() => {
      const modalOverlay = document.querySelector('.modal-overlay')
      if (modalOverlay) {
        modalOverlay.focus()
      }
    }, 100)
  } catch (error) {
    alert(`Failed to delete remote: ${error.message}`)
    // Restore focus to modal after error
    setTimeout(() => {
      const modalOverlay = document.querySelector('.modal-overlay')
      if (modalOverlay) {
        modalOverlay.focus()
      }
    }, 100)
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
  // Check if readonly
  const remote = remotes.value.find(r => r.name === name)
  if (remote?.is_readonly) {
    alert(`Cannot refresh OAuth for read-only remote "${name}". This remote is from a read-only configuration file.`)
    return
  }

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

/* Use :deep() to style links inside v-html content */
.help-tooltip :deep(a) {
  color: #58C4FF !important;
  text-decoration: underline;
}

.help-tooltip :deep(a:hover) {
  color: #8FD5FF !important;
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

.config-title {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-primary);
}

.config-help {
  color: var(--color-text-secondary);
  margin-bottom: var(--spacing-sm);
}

.config-textarea {
  width: 100%;
  min-height: 300px;
  max-height: 50vh;
  font-family: 'Courier New', Courier, monospace;
  font-size: var(--font-size-xs);
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  resize: vertical;
}

.config-textarea:focus {
  outline: none;
  border-color: var(--color-primary);
}

.copy-config-btn {
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

.remotes-list-container {
  margin-bottom: var(--spacing-lg);
}

/* Increase base font size for remotes table */
.remotes-list-container :deep(.table-row) {
  font-size: var(--font-size-base);
}

/* Custom column styling */
.col-name,
.col-type {
  color: var(--color-text-primary);
}

.col-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-xs);
}

.oauth-spacer {
  display: inline-block;
  width: 32px;
}

.template-intro {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-secondary);
}

.template-list-container {
  overflow-y: auto;
  max-height: 50vh;
  margin-bottom: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  outline: none;
}

.template-item {
  padding: var(--spacing-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-white);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: var(--transition-fast);
}

.template-item:hover {
  background: var(--color-bg-hover);
}

.template-selected {
  border: 2px solid var(--color-primary) !important;
  background: var(--color-bg-primary-light) !important;
}

.template-name {
  display: block;
  margin-bottom: 4px;
  color: var(--color-text-primary);
}

.template-fields {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
}

/* Remote action icon buttons with hover effect */
.remote-icon-btn {
  background: none;
  border: none;
  font-size: 14px;
  cursor: pointer;
  padding: 4px 8px;
  margin-right: 4px;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.remote-icon-btn:not(.disabled):hover {
  transform: scale(1.2);
  opacity: 0.7;
}

.remote-icon-btn.disabled {
  cursor: not-allowed;
  filter: grayscale(100%) opacity(0.4);
}

.oauth-refresh-btn {
  font-size: 18px;
  color: var(--color-success);
}

.oauth-refresh-btn.disabled {
  color: #ccc;
}
</style>
