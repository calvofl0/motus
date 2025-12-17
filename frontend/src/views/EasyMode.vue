<template>
  <div id="easy-mode">
    <div class="panes-container">
      <!-- Left Pane -->
      <FilePane pane="left" ref="leftPaneRef" />

      <!-- Arrow Buttons -->
      <div class="arrow-buttons">
        <div class="arrow-button" :class="{ disabled: !canCopyRight }" @click="copyToRight">▶</div>
        <div
          class="check-button"
          :class="{ disabled: !canCheck }"
          @click="handleIntegrityCheck"
          title="Integrity check"
        >✓</div>
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

    <DownloadPreparingModal
      v-model="showDownloadPreparingModal"
      :message="downloadPreparingMessage"
    />

    <!-- Integrity Check Success Modal -->
    <div v-if="showCheckSuccessModal" class="modal-overlay" @click="showCheckSuccessModal = false">
      <div class="modal-content" @click.stop>
        <h3>✓ Integrity Check Successful</h3>
        <p><strong>Source:</strong> {{ checkSuccessSource }}</p>
        <p><strong>Destination:</strong> {{ checkSuccessDest }}</p>
        <button @click="showCheckSuccessModal = false">Close</button>
      </div>
    </div>

    <!-- Job Log Modal for Failed Checks -->
    <JobLogModal
      :show="showJobLogModal"
      :job="jobLogData"
      @close="showJobLogModal = false"
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
import DownloadPreparingModal from '../components/modals/DownloadPreparingModal.vue'
import CreateAliasModal from '../components/modals/CreateAliasModal.vue'
import ContextMenu from '../components/ContextMenu.vue'
import JobLogModal from '../components/modals/JobLogModal.vue'
import { apiCall, getAuthToken, getApiUrl } from '../services/api'

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

// Download preparing modal state
const showDownloadPreparingModal = ref(false)
const downloadPreparingMessage = ref('Downloading file from remote server...')

// Integrity check success modal state
const showCheckSuccessModal = ref(false)
const checkSuccessSource = ref('')
const checkSuccessDest = ref('')

// Job log modal state
const showJobLogModal = ref(false)
const jobLogData = ref(null)

// Computed
const canCopyRight = computed(() =>
  appStore.leftPane.selectedIndexes.length > 0
)

const canCopyLeft = computed(() =>
  appStore.rightPane.selectedIndexes.length > 0
)

const canCheck = computed(() =>
  appStore.leftPane.selectedIndexes.length > 0 || appStore.rightPane.selectedIndexes.length > 0
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

// Integrity check function
async function handleIntegrityCheck() {
  if (!canCheck.value) return

  // Determine source and destination
  let srcPane, dstPane
  if (appStore.leftPane.selectedIndexes.length > 0) {
    srcPane = 'left'
    dstPane = 'right'
  } else {
    srcPane = 'right'
    dstPane = 'left'
  }

  const srcPaneState = appStore[`${srcPane}Pane`]
  const dstPaneState = appStore[`${dstPane}Pane`]

  // Get selected files
  const selectedFiles = srcPaneState.selectedIndexes.map(idx => srcPaneState.files[idx])

  // Build helper function
  function buildPath(basePath, fileName) {
    if (basePath.endsWith('/')) {
      return basePath + fileName
    }
    return basePath + '/' + fileName
  }

  // Helper to get resolved location (for absolute paths mode)
  function getResolvedLocation(pane) {
    const state = appStore[`${pane}Pane`]

    if (!appStore.absolutePathsMode) {
      // Not in absolute paths mode - return as-is
      return {
        remote: state.remote,
        path: state.path
      }
    }

    // In absolute paths mode - resolve through alias
    if (state.aliasBasePath) {
      // We're in an alias
      if (state.aliasBasePath.includes(':')) {
        // Remote alias
        const colonIndex = state.aliasBasePath.indexOf(':')
        const remote = state.aliasBasePath.substring(0, colonIndex)
        const aliasPath = state.aliasBasePath.substring(colonIndex + 1)
        // Combine alias path with current path
        const fullPath = aliasPath + (state.path === '/' ? '' : state.path)
        return { remote, path: fullPath }
      } else {
        // Local alias
        const fullPath = state.aliasBasePath + (state.path === '/' ? '' : state.path)
        return { remote: '', path: fullPath }
      }
    } else if (state.remote) {
      // Direct remote (not an alias)
      return { remote: state.remote, path: state.path }
    } else {
      // Local filesystem
      return { remote: '', path: state.path }
    }
  }

  // Helper to build operation path
  function buildOperationPath(pane, fileName) {
    const resolved = getResolvedLocation(pane)
    const filePath = buildPath(resolved.path, fileName)

    if (resolved.remote) {
      return `${resolved.remote}:${filePath}`
    } else {
      return filePath
    }
  }

  try {
    // Check each file (same pattern as copy)
    for (const file of selectedFiles) {
      // Build paths using resolved location (handles absolute paths mode)
      const srcPath = buildOperationPath(srcPane, file.Name)
      const dstPath = buildOperationPath(dstPane, file.Name)

      const response = await apiCall('/api/jobs/check', 'POST', {
        src_path: srcPath,
        dst_path: dstPath
      })

      if (response.job_id) {
        // Watch for job completion
        watchJobForCheck(response.job_id, srcPath, dstPath)
      }
    }
  } catch (error) {
    console.error('Failed to start integrity check:', error)
    alert(`Failed to start integrity check: ${error.message}`)
  }
}

// Watch integrity check job completion
function watchJobForCheck(jobId, sourcePath, destPath) {
  let pollInterval = null
  let eventHandled = false

  // Function to handle success
  const handleSuccess = () => {
    if (eventHandled) return
    eventHandled = true

    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }

    // Show success popup
    checkSuccessSource.value = sourcePath
    checkSuccessDest.value = destPath
    showCheckSuccessModal.value = true

    window.removeEventListener('job-completed', handleJobComplete)
  }

  // Function to handle failure
  const handleFailure = async (job) => {
    if (eventHandled) return
    eventHandled = true

    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }

    // Refetch job details to ensure we have the complete log text
    // The job event might arrive before the database is fully updated
    try {
      const fullJobDetails = await apiCall(`/api/jobs/${job.job_id}`)
      jobLogData.value = fullJobDetails
    } catch (error) {
      console.error('Failed to fetch full job details:', error)
      // Fallback to the job object from the event
      jobLogData.value = job
    }

    // Auto-open job log modal
    showJobLogModal.value = true

    window.removeEventListener('job-completed', handleJobComplete)
  }

  // Listen for job completion event
  const handleJobComplete = async (event) => {
    const job = event.detail
    if (job.job_id === jobId) {
      if (job.status === 'completed') {
        handleSuccess()
      } else if (job.status === 'failed') {
        handleFailure(job)
      } else if (job.status === 'interrupted') {
        // Job was cancelled - stop polling and cleanup
        if (pollInterval) clearInterval(pollInterval)
        if (eventHandled) return
        eventHandled = true
        window.removeEventListener('job-completed', handleJobComplete)
      }
    }
  }

  window.addEventListener('job-completed', handleJobComplete)

  // Poll job status
  const pollJobStatus = async () => {
    try {
      const job = await apiCall(`/api/jobs/${jobId}`)
      if (job.status === 'completed') {
        handleSuccess()
      } else if (job.status === 'failed') {
        handleFailure(job)
      } else if (job.status === 'interrupted') {
        if (pollInterval) clearInterval(pollInterval)
        if (eventHandled) return
        eventHandled = true
        window.removeEventListener('job-completed', handleJobComplete)
      }
    } catch (error) {
      console.error(`Error polling job ${jobId}:`, error)
    }
  }

  // Start polling every 500ms
  pollInterval = setInterval(pollJobStatus, 500)

  // Also check immediately
  pollJobStatus()
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

    // Helper to get resolved location (for absolute paths mode)
    function getResolvedLocation(pane) {
      const state = appStore[`${pane}Pane`]

      if (!appStore.absolutePathsMode) {
        // Not in absolute paths mode - return as-is
        return {
          remote: state.remote,
          path: state.path
        }
      }

      // In absolute paths mode - resolve through alias
      if (state.aliasBasePath) {
        // We're in an alias
        if (state.aliasBasePath.includes(':')) {
          // Remote alias
          const colonIndex = state.aliasBasePath.indexOf(':')
          const remote = state.aliasBasePath.substring(0, colonIndex)
          const aliasPath = state.aliasBasePath.substring(colonIndex + 1)
          // Combine alias path with current path
          const fullPath = aliasPath + (state.path === '/' ? '' : state.path)
          return { remote, path: fullPath }
        } else {
          // Local alias
          const fullPath = state.aliasBasePath + (state.path === '/' ? '' : state.path)
          return { remote: '', path: fullPath }
        }
      } else if (state.remote) {
        // Direct remote (not an alias)
        return { remote: state.remote, path: state.path }
      } else {
        // Local filesystem
        return { remote: '', path: state.path }
      }
    }

    // Get resolved location
    const resolved = getResolvedLocation(pane)

    // Get selected files
    const selectedFiles = paneState.selectedIndexes.map(idx => {
      const file = paneState.files[idx]
      // Construct full path using resolved location
      let fullPath
      const filePath = resolved.path === '/' ? `/${file.Name}` : `${resolved.path}/${file.Name}`
      if (resolved.remote) {
        // Remote path
        fullPath = `${resolved.remote}:${filePath}`
      } else {
        // Local path
        fullPath = filePath
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
      // Direct download - show modal and trigger file download
      showDownloadPreparingModal.value = true
      try {
        await downloadDirect(response.path)
      } finally {
        showDownloadPreparingModal.value = false
      }
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
    const response = await fetch(getApiUrl('/api/files/download/direct'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `token ${getAuthToken()}`
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
  let pollInterval = null
  let eventHandled = false

  // Function to trigger the download
  const triggerDownload = (job) => {
    if (eventHandled) return // Prevent duplicate handling
    eventHandled = true

    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }

    const downloadToken = job.download_token
    if (downloadToken) {
      // Get current token for authentication
      const downloadUrl = getApiUrl(`/api/files/download/zip/${downloadToken}`) + `?token=${getAuthToken()}`

      // Trigger download by navigating
      window.location.href = downloadUrl
    } else {
      alert('Download preparation completed but download link is missing')
    }
  }

  // Function to handle failures
  const handleFailure = (errorText) => {
    if (eventHandled) return
    eventHandled = true

    if (pollInterval) {
      clearInterval(pollInterval)
      pollInterval = null
    }

    alert(`Download preparation failed: ${errorText || 'Unknown error'}`)
  }

  // Listen for job completion event (from JobPanel)
  const handleJobComplete = (event) => {
    const job = event.detail
    if (job.job_id === jobId) {
      if (job.status === 'completed') {
        triggerDownload(job)
        window.removeEventListener('job-completed', handleJobComplete)
      } else if (job.status === 'failed') {
        handleFailure(job.error_text)
        window.removeEventListener('job-completed', handleJobComplete)
      } else if (job.status === 'interrupted') {
        // Job was cancelled - stop polling and cleanup
        if (pollInterval) clearInterval(pollInterval)
        if (eventHandled) return
        eventHandled = true
        window.removeEventListener('job-completed', handleJobComplete)
      }
    }
  }

  window.addEventListener('job-completed', handleJobComplete)

  // Also poll the job status directly (for fast-completing jobs)
  // This ensures we catch jobs that complete before JobPanel sees them
  const pollJobStatus = async () => {
    try {
      const job = await apiCall(`/api/jobs/${jobId}`)
      if (job.status === 'completed') {
        triggerDownload(job)
        window.removeEventListener('job-completed', handleJobComplete)
      } else if (job.status === 'failed') {
        handleFailure(job.error_text)
        window.removeEventListener('job-completed', handleJobComplete)
      } else if (job.status === 'interrupted') {
        // Job was cancelled - stop polling and cleanup
        if (pollInterval) clearInterval(pollInterval)
        if (eventHandled) return
        eventHandled = true
        window.removeEventListener('job-completed', handleJobComplete)
      }
      // If still running or pending, keep polling
    } catch (error) {
      console.error(`Error polling job ${jobId}:`, error)
    }
  }

  // Start polling every 500ms
  pollInterval = setInterval(pollJobStatus, 500)

  // Also check immediately
  pollJobStatus()
}

// Alias creation functions
async function openCreateAliasModal(pane, folder) {
  const paneState = appStore[`${pane}Pane`]

  // Helper to get resolved location (for absolute paths mode)
  function getResolvedLocation(pane) {
    const state = appStore[`${pane}Pane`]

    if (!appStore.absolutePathsMode) {
      // Not in absolute paths mode - return as-is
      return {
        remote: state.remote,
        path: state.path
      }
    }

    // In absolute paths mode - resolve through alias
    if (state.aliasBasePath) {
      // We're in an alias
      if (state.aliasBasePath.includes(':')) {
        // Remote alias
        const colonIndex = state.aliasBasePath.indexOf(':')
        const remote = state.aliasBasePath.substring(0, colonIndex)
        const aliasPath = state.aliasBasePath.substring(colonIndex + 1)
        // Combine alias path with current path
        const fullPath = aliasPath + (state.path === '/' ? '' : state.path)
        return { remote, path: fullPath }
      } else {
        // Local alias
        const fullPath = state.aliasBasePath + (state.path === '/' ? '' : state.path)
        return { remote: '', path: fullPath }
      }
    } else if (state.remote) {
      // Direct remote (not an alias)
      return { remote: state.remote, path: state.path }
    } else {
      // Local filesystem
      return { remote: '', path: state.path }
    }
  }

  // Get resolved location (handles absolute paths mode)
  const resolved = getResolvedLocation(pane)

  // Construct target path using resolved location
  const folderPath = resolved.path === '/' ? `/${folder.Name}` : `${resolved.path}/${folder.Name}`
  const targetPath = resolved.remote ? `${resolved.remote}:${folderPath}` : folderPath

  // Resolve alias chain to get underlying path
  const resolvedPath = await resolveAliasPath(resolved.remote, folderPath)

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
    // Handle the resolved path format
    // If it resolves to a local filesystem path, concatenate without colon
    // If it resolves to a remote, keep the remote:path format
    let remotePath = aliasResolvedPath.value

    if (remotePath.includes(':')) {
      const colonIndex = remotePath.indexOf(':')
      const beforeColon = remotePath.substring(0, colonIndex)
      const afterColon = remotePath.substring(colonIndex + 1)

      // Check if beforeColon is a local filesystem path (starts with /)
      // or Windows path (like C:, but we need to check for double colon pattern)
      if (beforeColon.startsWith('/')) {
        // Local filesystem path - concatenate without colon
        remotePath = beforeColon + afterColon
      }
      // Otherwise keep the remote:path format as-is
    }

    // Create alias remote config
    const config = `[${aliasName}]\ntype = alias\nremote = ${remotePath}\n`

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

.arrow-button,
.check-button {
  color: #28a745;
  font-size: 28px;
  cursor: pointer;
  transition: all 0.3s;
  opacity: 1;
  user-select: none;
}

.arrow-button.disabled,
.check-button.disabled {
  cursor: not-allowed;
  opacity: 0.3;
}

.arrow-button:not(.disabled):hover,
.check-button:not(.disabled):hover {
  transform: scale(1.2);
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  max-width: 600px;
  width: 90%;
}

.modal-content h3 {
  margin-top: 0;
  color: #28a745;
  font-size: 20px;
}

.modal-content p {
  margin: 10px 0;
  word-break: break-all;
}

.modal-content button {
  margin-top: 20px;
  padding: 10px 20px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.modal-content button:hover {
  background: #218838;
}
</style>
