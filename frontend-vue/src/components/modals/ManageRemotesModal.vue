<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    :canClose="true"
    maxWidth="700px"
  >
    <template #header>🔧 Manage Remotes</template>
    <template #body>
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
              @dblclick="viewRemote(remote.name)"
              style="border-bottom: 1px solid #eee; cursor: pointer; transition: background-color 0.2s;"
              :style="{ backgroundColor: hoveredRemote === remote.name ? '#f5f5f5' : 'transparent' }"
              @mouseenter="hoveredRemote = remote.name"
              @mouseleave="hoveredRemote = null"
              :title="`Double-click to view ${remote.name} configuration`"
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
    <template #footer>
      <!-- Add Remote button will be added later with wizard -->
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
import { ref, watch } from 'vue'
import BaseModal from './BaseModal.vue'
import { apiCall } from '../../services/api'

const props = defineProps({
  modelValue: Boolean,
  activeRemotes: {
    type: Object,
    default: () => ({ left: '', right: '' })
  }
})

const emit = defineEmits(['update:modelValue', 'remotesChanged'])

// State
const loading = ref(false)
const error = ref('')
const remotes = ref([])
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
 * Load remotes when modal opens
 */
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    await loadRemotes()
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
 * View remote configuration (double-click)
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
