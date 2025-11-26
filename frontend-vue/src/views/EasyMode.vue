<template>
  <div id="easy-mode">
    <div class="panes-container">
      <!-- Left Pane -->
      <FilePane pane="left" ref="leftPaneRef" />

      <!-- Arrow Buttons -->
      <div class="arrow-buttons">
        <div class="arrow-button" :class="{ disabled: !canCopyRight }" @click="copyToRight">▶</div>
        <div class="arrow-button" :class="{ disabled: !canCopyLeft }" @click="copyToLeft">◀</div>
      </div>

      <!-- Right Pane -->
      <FilePane pane="right" ref="rightPaneRef" />
    </div>

    <!-- Job Panel -->
    <JobPanel />

    <!-- Modals -->
    <RenameModal
      v-model="fileOps.showRenameModal.value"
      :current-name="fileOps.renameData.value.file?.Name || ''"
      @confirm="fileOps.confirmRename"
    />

    <CreateFolderModal
      v-model="fileOps.showCreateFolderModal.value"
      @confirm="fileOps.confirmCreateFolder"
    />

    <DeleteConfirmModal
      v-model="fileOps.showDeleteModal.value"
      :items="fileOps.deleteData.value.files.map(f => f.Name)"
      @confirm="fileOps.confirmDelete"
    />

    <DragDropConfirmModal
      v-model="fileOps.showDragDropModal.value"
      :files="fileOps.dragDropData.value.files"
      :source-path="fileOps.dragDropData.value.sourcePath"
      :dest-path="fileOps.dragDropData.value.destPath"
      @confirm="fileOps.confirmCopy"
    />

    <UploadProgressModal
      v-model="upload.showUploadModal.value"
      :message="upload.uploadMessage.value"
      :progress="upload.uploadProgress.value"
      :details="upload.uploadDetails.value"
      :can-cancel="upload.canCancelUpload.value"
      @cancel="upload.cancelUpload"
    />

    <CreateAliasModal
      v-model="showCreateAliasModal"
      :target-path="aliasTargetPath"
      :resolved-path="aliasResolvedPath"
      @create="handleCreateAlias"
    />

    <!-- Context Menu -->
    <ContextMenu
      :visible="contextMenuVisible"
      :position="contextMenuPosition"
      :selected-count="contextMenuSelectedCount"
      :has-target-folder="contextMenuTargetFolder !== null"
      @close="closeContextMenu"
      @action="handleContextMenuAction"
      @sort="handleContextMenuSort"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide, nextTick } from 'vue'
import { useAppStore } from '../stores/app'
import { useFileOperations } from '../composables/useFileOperations'
import { useUpload } from '../composables/useUpload'
import FilePane from '../components/FilePane.vue'
import JobPanel from '../components/JobPanel.vue'
import RenameModal from '../components/modals/RenameModal.vue'
import CreateFolderModal from '../components/modals/CreateFolderModal.vue'
import DeleteConfirmModal from '../components/modals/DeleteConfirmModal.vue'
import DragDropConfirmModal from '../components/modals/DragDropConfirmModal.vue'
import UploadProgressModal from '../components/modals/UploadProgressModal.vue'
import CreateAliasModal from '../components/modals/CreateAliasModal.vue'
import ContextMenu from '../components/ContextMenu.vue'
import { apiCall } from '../services/api'

const appStore = useAppStore()
const fileOps = useFileOperations()
const upload = useUpload()

// Refs to FilePane components
const leftPaneRef = ref(null)
const rightPaneRef = ref(null)

// Context menu state - using separate refs for reliable reactivity
const contextMenuVisible = ref(false)
const contextMenuPosition = ref({ x: 0, y: 0 })
const contextMenuPane = ref(null)
const contextMenuSelectedCount = ref(0)
const contextMenuTargetFolder = ref(null) // The folder being right-clicked (for Create Alias)

// Create alias modal state
const showCreateAliasModal = ref(false)
const aliasTargetPath = ref('')
const aliasResolvedPath = ref('')
const aliasPane = ref(null)

// Computed
const canCopyRight = computed(() =>
  appStore.leftPane.selectedIndexes.length > 0
)

const canCopyLeft = computed(() =>
  appStore.rightPane.selectedIndexes.length > 0
)

// Copy functions
function copyToRight() {
  if (!canCopyRight.value) return
  fileOps.copyToPane('left', 'right')
}

function copyToLeft() {
  if (!canCopyLeft.value) return
  fileOps.copyToPane('right', 'left')
}

// Context menu functions
function showContextMenu(pane, event) {
  const paneState = appStore[`${pane}Pane`]

  // Determine if a single folder is selected (for Create Alias)
  let targetFolder = null
  if (paneState.selectedIndexes.length === 1) {
    const file = paneState.files[paneState.selectedIndexes[0]]
    if (file && file.IsDir) {
      targetFolder = file
    }
  }

  // Update refs directly
  contextMenuVisible.value = true
  contextMenuPosition.value = { x: event.clientX, y: event.clientY }
  contextMenuPane.value = pane
  contextMenuSelectedCount.value = paneState.selectedIndexes.length
  contextMenuTargetFolder.value = targetFolder
}

function closeContextMenu() {
  contextMenuVisible.value = false
}

function handleContextMenuAction(action) {
  const pane = contextMenuPane.value
  if (!pane) return

  const paneState = appStore[`${pane}Pane`]

  switch (action) {
    case 'createalias':
      if (contextMenuTargetFolder.value) {
        openCreateAliasModal(pane, contextMenuTargetFolder.value)
      }
      break
    case 'newfolder':
      fileOps.openCreateFolderModal(pane)
      break
    case 'rename':
      if (paneState.selectedIndexes.length === 1) {
        const file = paneState.files[paneState.selectedIndexes[0]]
        fileOps.openRenameModal(pane, file)
      }
      break
    case 'delete':
      if (paneState.selectedIndexes.length > 0) {
        fileOps.openDeleteModal(pane)
      }
      break
    case 'download':
      if (paneState.selectedIndexes.length > 0) {
        handleDownload(pane)
      }
      break
  }
}

function handleContextMenuSort({ field, asc }) {
  const pane = contextMenuPane.value
  if (!pane) return

  // Trigger sort on the pane
  const paneRef = pane === 'left' ? leftPaneRef.value : rightPaneRef.value
  if (paneRef && paneRef.setSortBy) {
    paneRef.setSortBy(field, asc)
  }
}

// Download function
async function handleDownload(pane) {
  try {
    const paneState = appStore[`${pane}Pane`]
    const remote = paneState.remote
    const currentPath = paneState.path

    // Get selected files
    const selectedFiles = paneState.selectedIndexes.map(idx => {
      const file = paneState.files[idx]
      // Construct full path
      let fullPath
      if (remote) {
        // Remote path
        const filePath = currentPath === '/' ? `/${file.Name}` : `${currentPath}/${file.Name}`
        fullPath = `${remote}:${filePath}`
      } else {
        // Local path
        fullPath = currentPath === '/' ? `/${file.Name}` : `${currentPath}/${file.Name}`
      }
      return fullPath
    })

    if (selectedFiles.length === 0) return

    // Call prepare endpoint
    const response = await apiCall('/api/files/download/prepare', 'POST', {
      paths: selectedFiles,
      remote_config: null // We use named remotes
    })

    if (response.type === 'direct') {
      // Direct download - trigger file download
      await downloadDirect(response.path)
    } else if (response.type === 'zip_job') {
      // ZIP job created - show notification
      alert(`Download preparation started. Job ID: ${response.job_id}\nYour download will start automatically when ready.`)

      // Monitor job completion
      watchJobForDownload(response.job_id)
    }
  } catch (error) {
    console.error('Download failed:', error)
    alert(`Download failed: ${error.message}`)
  }
}

async function downloadDirect(path) {
  try {
    const response = await fetch('/api/files/download/direct', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `token ${localStorage.getItem('token')}`
      },
      body: JSON.stringify({ path: path, remote_config: null })
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    // Get filename from response headers or path
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = 'download'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/)
      if (filenameMatch) filename = filenameMatch[1]
    } else {
      filename = path.split('/').pop() || 'download'
    }

    // Convert response to blob and trigger download
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (error) {
    console.error('Direct download failed:', error)
    throw error
  }
}

function watchJobForDownload(jobId) {
  // Listen for job completion event
  const handleJobComplete = (event) => {
    const job = event.detail
    if (job.job_id === jobId && job.status === 'completed') {
      // Job completed - trigger download
      const downloadToken = job.download_token
      if (downloadToken) {
        // Get current token for authentication
        const token = localStorage.getItem('token')
        const downloadUrl = `/api/files/download/zip/${downloadToken}?token=${token}`

        // Trigger download by navigating
        window.location.href = downloadUrl
      }

      // Remove listener
      window.removeEventListener('job-completed', handleJobComplete)
    } else if (job.job_id === jobId && job.status === 'failed') {
      alert(`Download preparation failed: ${job.error_text || 'Unknown error'}`)
      window.removeEventListener('job-completed', handleJobComplete)
    }
  }

  window.addEventListener('job-completed', handleJobComplete)
}

// Alias creation functions
async function openCreateAliasModal(pane, folder) {
  const paneState = appStore[`${pane}Pane`]
  const remote = paneState.remote
  const currentPath = paneState.path

  // Construct target path
  const folderPath = currentPath === '/' ? `/${folder.Name}` : `${currentPath}/${folder.Name}`
  const targetPath = remote ? `${remote}:${folderPath}` : folderPath

  // Resolve alias chain to get underlying path
  const resolvedPath = await resolveAliasPath(remote, folderPath)

  aliasTargetPath.value = targetPath
  aliasResolvedPath.value = resolvedPath
  aliasPane.value = pane
  showCreateAliasModal.value = true
}

async function resolveAliasPath(remote, path) {
  if (!remote) {
    // Local filesystem - no alias resolution needed
    return path
  }

  try {
    // Call backend API to resolve alias chain
    const response = await apiCall('/api/remotes/resolve-alias', 'POST', {
      remote: remote,
      path: path
    })
    return response.resolved_path || `${remote}:${path}`
  } catch (error) {
    console.error('Failed to resolve alias path:', error)
    // Fallback to original path if resolution fails
    return `${remote}:${path}`
  }
}

async function handleCreateAlias(aliasName) {
  try {
    // Create alias remote config
    const config = `[${aliasName}]\ntype = alias\nremote = ${aliasResolvedPath.value}\n`

    await apiCall('/api/remotes/raw', 'POST', {
      raw_config: config
    })

    showCreateAliasModal.value = false

    // Notify that remotes have changed (after modal closes)
    await nextTick()
    window.dispatchEvent(new CustomEvent('remotes-changed'))
  } catch (error) {
    console.error('Failed to create alias:', error)
    alert(`Failed to create alias: ${error.message}`)
  }
}

// Provide file operations and context menu to child components
provide('fileOperations', fileOps)
provide('contextMenu', { show: showContextMenu })

// Handle refresh pane events
function handleRefreshPane(event) {
  const { pane, preserveSelection } = event.detail
  const paneRef = pane === 'left' ? leftPaneRef.value : rightPaneRef.value
  if (paneRef && paneRef.refresh) {
    paneRef.refresh(preserveSelection)
  }
}

// Keyboard shortcuts
function handleKeyDown(event) {
  // Only handle shortcuts when not typing in an input
  if (event.target.tagName === 'INPUT' || event.target.tagName === 'TEXTAREA') {
    return
  }

  const lastPane = appStore.lastFocusedPane
  const paneState = appStore[`${lastPane}Pane`]

  // F2 - Rename selected file
  if (event.key === 'F2' && paneState.selectedIndexes.length === 1) {
    event.preventDefault()
    const file = paneState.files[paneState.selectedIndexes[0]]
    fileOps.openRenameModal(lastPane, file)
  }

  // Delete - Delete selected files
  if (event.key === 'Delete' && paneState.selectedIndexes.length > 0) {
    event.preventDefault()
    fileOps.openDeleteModal(lastPane)
  }
}

// Lifecycle
onMounted(() => {
  window.addEventListener('refresh-pane', handleRefreshPane)
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('refresh-pane', handleRefreshPane)
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
#easy-mode {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panes-container {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 0;
  padding: 15px;
  overflow: hidden;
}

.arrow-buttons {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 20px;
  padding: 0 15px;
}

.arrow-button {
  color: #28a745;
  font-size: 28px;
  cursor: pointer;
  transition: all 0.3s;
  opacity: 1;
  user-select: none;
}

.arrow-button.disabled {
  cursor: not-allowed;
  opacity: 0.3;
}

.arrow-button:not(.disabled):hover {
  transform: scale(1.2);
}
</style>
