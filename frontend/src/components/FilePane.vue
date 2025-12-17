<template>
  <div class="pane" :class="`${pane}-pane`">
    <!-- Pane Header -->
    <div class="pane-header">📂 {{ title }}</div>

    <!-- Pane Toolbar -->
    <div class="pane-toolbar">
      <div class="toolbar-row">
        <select v-model="selectedRemote" @change="onRemoteChange">
          <option v-if="localFsName" value="">{{ localFsName }}</option>
          <option v-for="remote in sortedRemotes" :key="remote.name" :value="remote.name">
            {{ remote.name }}
          </option>
        </select>
      </div>
      <div class="toolbar-row">
        <input
          type="text"
          v-model="inputPath"
          @keypress.enter="browsePath"
          placeholder="Path..."
        />
        <button
          class="parent-btn"
          @click="navigateUp"
          @mouseover="parentHover = true"
          @mouseout="parentHover = false"
          :disabled="isAtRoot"
          :title="isAtRoot ? 'Already at root directory' : 'Go to parent directory'"
          :style="{
            transform: (parentHover && !isAtRoot) ? 'scale(1.2)' : 'scale(1)',
            opacity: isAtRoot ? '0.3' : '1',
            cursor: isAtRoot ? 'not-allowed' : 'pointer'
          }"
        >
          ⬆
        </button>
        <button
          class="refresh-btn"
          @click="loading ? abortRefresh() : refresh()"
          @mouseover="refreshHover = true"
          @mouseout="refreshHover = false"
          :title="loading ? 'Abort loading' : 'Refresh'"
          :style="{ transform: refreshHover ? 'scale(1.2)' : 'scale(1)' }"
        >
          {{ loading ? '✕' : '⟳' }}
        </button>
      </div>
    </div>

    <!-- File Container -->
    <div
      :class="viewMode === 'grid' ? 'file-grid' : 'file-list'"
      :id="`${pane}-files`"
      @click="handleContainerClick"
      @contextmenu="handleContainerContextMenu"
      @dragover="handleDragOver"
      @drop="handleDrop"
      @dragleave="handleDragLeave"
    >
      <!-- Loading State -->
      <div v-if="loading" class="empty-state">Loading...</div>

      <!-- Grid View -->
      <template v-else-if="viewMode === 'grid'">
        <!-- Parent Directory -->
        <div
          v-if="!isAtRoot"
          class="file-item"
          @dblclick="navigateUp"
          @contextmenu.prevent="handleParentContextMenu"
        >
          <div class="file-icon">📁</div>
          <div class="file-name">..</div>
        </div>

        <!-- Files -->
        <div
          v-for="(file, visualIndex) in sortedFiles"
          :key="file._originalIndex"
          class="file-item"
          :class="{ selected: isSelected(file._originalIndex) }"
          draggable="true"
          @click="handleFileClick(file._originalIndex, $event)"
          @dblclick="handleFileDblClick(file)"
          @contextmenu.prevent="handleFileContextMenu(file._originalIndex, $event)"
          @mousedown="handleMouseDown(file._originalIndex, $event)"
          @dragstart="handleDragStart(file._originalIndex, $event)"
        >
          <div class="file-icon">{{ file.IsDir ? '📁' : '📄' }}</div>
          <div class="file-name">{{ file.Name }}</div>
        </div>

        <!-- Empty State for Grid -->
        <div v-if="sortedFiles.length === 0" class="empty-state">
          No files
        </div>
      </template>

      <!-- List View -->
      <table v-else>
        <thead>
          <tr>
            <th class="col-name" @click="setSortBy('name')">
              Name
              <span v-if="sortBy === 'name'" class="sort-indicator">
                {{ sortAsc ? '▲' : '▼' }}
              </span>
            </th>
            <th class="col-size" @click="setSortBy('size')">
              Size
              <span v-if="sortBy === 'size'" class="sort-indicator">
                {{ sortAsc ? '▲' : '▼' }}
              </span>
            </th>
            <th class="col-date" @click="setSortBy('date')">
              Date
              <span v-if="sortBy === 'date'" class="sort-indicator">
                {{ sortAsc ? '▲' : '▼' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <!-- Parent Directory -->
          <tr
            v-if="!isAtRoot"
            class="file-row"
            @dblclick="navigateUp"
            @contextmenu.prevent="handleParentContextMenu"
          >
            <td class="file-name-col">
              <span class="file-icon-small">📁</span>
              <span>..</span>
            </td>
            <td class="file-size-col"></td>
            <td class="file-date-col"></td>
          </tr>

          <!-- Files -->
          <tr
            v-for="(file, visualIndex) in sortedFiles"
            :key="file._originalIndex"
            class="file-row"
            :class="{ selected: isSelected(file._originalIndex) }"
            draggable="true"
            @click="handleFileClick(file._originalIndex, $event)"
            @dblclick="handleFileDblClick(file)"
            @contextmenu.prevent="handleFileContextMenu(file._originalIndex, $event)"
            @mousedown="handleMouseDown(file._originalIndex, $event)"
            @dragstart="handleDragStart(file._originalIndex, $event)"
          >
            <td class="file-name-col">
              <span class="file-icon-small">{{ file.IsDir ? '📁' : '📄' }}</span>
              <span>{{ file.Name }}</span>
            </td>
            <td class="file-size-col">{{ file.IsDir ? '' : formatSize(file.Size) }}</td>
            <td class="file-date-col">{{ formatDate(file.ModTime) }}</td>
          </tr>

          <!-- Empty State for List -->
          <tr v-if="sortedFiles.length === 0">
            <td colspan="3" class="empty-state">No files</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- Download Confirmation Modal -->
  <DownloadConfirmModal
    v-model="showDownloadConfirm"
    :fileName="downloadConfirmFile"
    :fileSize="downloadConfirmSize"
    @confirm="confirmDownload"
    @cancel="showDownloadConfirm = false"
  />
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, inject } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall, getAuthToken, getApiUrl } from '../services/api'
import { useUpload } from '../composables/useUpload'
import { formatFileSize } from '../services/helpers'
import DownloadConfirmModal from './modals/DownloadConfirmModal.vue'

const props = defineProps({
  pane: {
    type: String,
    required: true,
    validator: (value) => ['left', 'right'].includes(value)
  }
})

const appStore = useAppStore()
const fileOperations = inject('fileOperations', null)
const contextMenuHandler = inject('contextMenu', null)

// Upload functionality
const { handleExternalFileUpload } = useUpload()

// Reactive state
const refreshHover = ref(false)
const parentHover = ref(false)
const selectedRemote = ref('')
const previousRemote = ref('') // Track last working remote
const currentPath = ref('/')
const previousPath = ref('/') // Track path before refresh for abort
const inputPath = ref('/') // What user sees/types in input field
const files = ref([])
const remotes = ref([])
const loading = ref(false)
const sortBy = ref('name')
const sortAsc = ref(true)
const startupRemote = ref(null) // Default remote to show on startup
const localFsName = ref('Local Filesystem') // Name for local filesystem entry (empty string hides it)
const abortController = ref(null) // For aborting fetch requests

// Absolute paths mode state
const absolutePathsMode = ref(false) // Loaded from config
const localAliases = ref([]) // [{name: "mylocal", basePath: "/home/user/docs"}, ...]
const currentAliasBasePath = ref('') // Base path of current alias (if applicable)

// Download confirmation modal state
const showDownloadConfirm = ref(false)
const downloadConfirmFile = ref('')
const downloadConfirmSize = ref('')
const downloadConfirmPath = ref('')

// Computed
const title = computed(() => props.pane === 'left' ? 'Server A' : 'Server B')
const paneState = computed(() => props.pane === 'left' ? appStore.leftPane : appStore.rightPane)
const viewMode = computed(() => appStore.viewMode)
const showHiddenFiles = computed(() => appStore.showHiddenFiles)

// Sync input path with current path (called after successful navigation)
function syncInputPath() {
  if (absolutePathsMode.value && currentAliasBasePath.value) {
    // In absolute paths mode with an alias - show full path
    if (currentAliasBasePath.value === '/') {
      // Special case: alias to root - currentPath is already absolute
      inputPath.value = currentPath.value
    } else {
      // Normal case: concatenate base path and current path
      // Works for both local paths (/home/user/docs + /subfolder)
      // and remote paths (gdrive:MyFiles + /subfolder)
      inputPath.value = currentAliasBasePath.value + currentPath.value
    }
  } else {
    // Normal mode or no alias - show relative path
    inputPath.value = currentPath.value
  }
}

// Visual order mapping for range selection
const visualOrder = ref({})

// Sorted and filtered files
const sortedFiles = computed(() => {
  let filesToShow = files.value

  // Filter hidden files if needed
  if (!showHiddenFiles.value) {
    filesToShow = filesToShow.filter(f => !f.Name.startsWith('.'))
  }

  // Add original index
  const filesWithIndex = filesToShow.map((file, idx) => ({
    ...file,
    _originalIndex: files.value.indexOf(file)
  }))

  // Sort
  const sorted = sortFiles(filesWithIndex, sortBy.value, sortAsc.value)

  // Build visual order mapping: originalIndex -> visualPosition
  const orderMap = {}
  sorted.forEach((file, visualPos) => {
    orderMap[file._originalIndex] = visualPos
  })
  visualOrder.value = orderMap

  return sorted
})

// Sort remotes alphabetically (Local Filesystem is always first in the template)
const sortedRemotes = computed(() => {
  return [...remotes.value].sort((a, b) => {
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
})

// Check if at root directory
const isAtRoot = computed(() => {
  // In absolute paths mode, check if we're at filesystem root using inputPath
  if (absolutePathsMode.value) {
    const absPath = inputPath.value
    // At filesystem root
    if (absPath === '/' || absPath === '~/' || absPath === '~') {
      return true
    }
    return false
  }

  // Normal mode - check currentPath
  const path = currentPath.value
  // Root cases: /, ~/, or ~ (for local filesystem)
  if (path === '/' || path === '~/' || path === '~') {
    return true
  }
  return false
})

// Helper functions
function isSelected(index) {
  return paneState.value.selectedIndexes.includes(index)
}

function sortFiles(filesList, field, ascending) {
  const sorted = [...filesList].sort((a, b) => {
    let aVal, bVal

    switch (field) {
      case 'name':
        aVal = a.Name.toLowerCase()
        bVal = b.Name.toLowerCase()
        break
      case 'size':
        aVal = a.Size || 0
        bVal = b.Size || 0
        break
      case 'date':
        aVal = new Date(a.ModTime).getTime()
        bVal = new Date(b.ModTime).getTime()
        break
      default:
        return 0
    }

    // Directories always come first
    if (a.IsDir && !b.IsDir) return -1
    if (!a.IsDir && b.IsDir) return 1

    if (aVal < bVal) return ascending ? -1 : 1
    if (aVal > bVal) return ascending ? 1 : -1
    return 0
  })

  return sorted
}

function formatSize(bytes) {
  if (bytes === 0 || bytes === undefined) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleString()
}

// API functions
async function loadRemotes(retries = 3, delay = 100) {
  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes || []
  } catch (error) {
    console.error(`Failed to load remotes (${retries} retries left):`, error)

    // Retry with exponential backoff if retries remaining
    if (retries > 0) {
      await new Promise(resolve => setTimeout(resolve, delay))
      return loadRemotes(retries - 1, delay * 2)
    } else {
      console.error('Failed to load remotes after all retries')
    }
  }
}

async function refresh(preserveSelection = false) {
  loading.value = true

  // Create abort controller for this refresh
  abortController.value = new AbortController()

  // Save selection if preserving
  const selectedFileNames = preserveSelection
    ? paneState.value.selectedIndexes.map(idx => files.value[idx]?.Name).filter(n => n)
    : []

  try {
    // Construct path for API call
    let fullPath
    if (absolutePathsMode.value && currentAliasBasePath.value) {
      // In absolute paths mode with a local alias - use absolute path
      fullPath = currentAliasBasePath.value + currentPath.value
    } else if (selectedRemote.value) {
      // Normal remote - use remote:path format
      fullPath = `${selectedRemote.value}:${currentPath.value}`
    } else {
      // Local filesystem - use path as-is
      fullPath = currentPath.value
    }

    const data = await apiCall('/api/files/ls', 'POST', { path: fullPath }, abortController.value.signal)
    files.value = data.files || []

    // Update store
    appStore.setPaneFiles(props.pane, files.value)
    appStore.setPanePath(props.pane, currentPath.value)
    appStore.setPaneRemote(props.pane, selectedRemote.value)

    // Update previous remote and path on success
    previousRemote.value = selectedRemote.value
    previousPath.value = currentPath.value

    // Restore selection if preserving
    if (preserveSelection && selectedFileNames.length > 0) {
      const newSelection = []
      selectedFileNames.forEach(name => {
        const idx = files.value.findIndex(f => f.Name === name)
        if (idx !== -1) newSelection.push(idx)
      })
      appStore.setPaneSelection(props.pane, newSelection)
    } else {
      appStore.setPaneSelection(props.pane, [])
    }
  } catch (error) {
    // Check if error is due to abort
    if (error.name === 'AbortError') {
      console.log('Refresh aborted by user')
      // Don't show alert for user-initiated abort
      return
    }

    console.error('Failed to refresh pane:', error)
    alert(`Failed to list files: ${error.message}`)

    // Revert to previous working remote on error
    selectedRemote.value = previousRemote.value

    // Don't restore path here - let calling function handle it
    // Re-throw error so calling code (navigateInto/browsePath) can handle path rollback
    throw error
  } finally {
    loading.value = false
    abortController.value = null
  }
}

function abortRefresh() {
  if (abortController.value) {
    // Abort the ongoing request
    abortController.value.abort()

    // Restore previous path
    currentPath.value = previousPath.value

    // Reset loading state (will be done in finally block of refresh, but set here for immediate feedback)
    loading.value = false

    console.log('Refresh aborted, restored to previous path:', previousPath.value)
  }
}

function onRemoteChange() {
  // Update previousPath before changing path (for abort functionality)
  previousPath.value = currentPath.value

  // Update current alias base path if in absolute paths mode
  if (absolutePathsMode.value && selectedRemote.value) {
    const alias = localAliases.value.find(a => a.name === selectedRemote.value)

    // Special case: if alias points to filesystem root, use local filesystem instead
    if (alias && alias.isLocal && alias.basePath === '/') {
      selectedRemote.value = ''
      currentAliasBasePath.value = ''
    } else {
      currentAliasBasePath.value = alias ? alias.basePath : ''
    }
  } else {
    currentAliasBasePath.value = ''
  }

  currentPath.value = '/'
  syncInputPath()
  refresh()
}

async function browsePath() {
  // Save the last successful path to restore on error
  const lastSuccessfulPath = previousPath.value
  const lastSuccessfulInputPath = inputPath.value

  // Parse the input path
  const typedPath = inputPath.value

  // Store in currentPath (will be processed by autoSwitchRemote)
  currentPath.value = typedPath

  // Auto-switch remote if in absolute paths mode (this updates currentPath and currentAliasBasePath)
  await autoSwitchRemote()

  // Expand ~ before refreshing (only for local filesystem, not aliases)
  // Check if remote is truly local (empty string means local)
  if (selectedRemote.value === '' && currentPath.value.includes('~')) {
    await expandHomePath()
  }

  try {
    await refresh()
    // Sync input path with the actual path after successful navigation
    syncInputPath()
  } catch (error) {
    // Restore to the last successful path on error
    currentPath.value = lastSuccessfulPath
    inputPath.value = lastSuccessfulInputPath
    console.log('Browse path failed, path restored to:', lastSuccessfulPath)
  }
}

async function expandHomePath() {
  try {
    const response = await apiCall('/api/files/expand-home', 'POST', {
      path: currentPath.value
    })
    if (response.expanded_path) {
      currentPath.value = response.expanded_path
    }
  } catch (error) {
    console.error('Failed to expand home path:', error)
    // Continue anyway - the path might still work
  }
}

function setSortBy(field, asc = null) {
  if (asc !== null) {
    // Explicit sort direction from context menu
    sortBy.value = field
    sortAsc.value = asc
  } else if (sortBy.value === field) {
    // Toggle if clicking same column
    sortAsc.value = !sortAsc.value
  } else {
    // New column, default to ascending
    sortBy.value = field
    sortAsc.value = true
  }
}

// Navigation
async function navigateUp() {
  let newPath

  // In absolute paths mode, calculate parent from the absolute path (local or remote)
  if (absolutePathsMode.value && (inputPath.value.startsWith('/') || inputPath.value.includes(':'))) {
    const isRemotePath = inputPath.value.includes(':') && !inputPath.value.startsWith('/')

    if (isRemotePath) {
      // Remote path like "gdrive:MyFiles/subfolder"
      const colonIndex = inputPath.value.indexOf(':')
      const remoteName = inputPath.value.substring(0, colonIndex)
      const remotePath = inputPath.value.substring(colonIndex + 1)

      const pathParts = remotePath.split('/').filter(p => p)
      if (pathParts.length === 0) {
        return // Already at remote root
      }
      pathParts.pop()
      newPath = remoteName + ':' + (pathParts.length === 0 ? '' : pathParts.join('/'))
    } else {
      // Local path like "/home/user/docs"
      const pathParts = inputPath.value.split('/').filter(p => p)
      if (pathParts.length === 0) {
        return // Already at root
      }
      pathParts.pop()
      newPath = '/' + pathParts.join('/')
    }

    // Update inputPath and currentPath
    const oldInputPath = inputPath.value
    const oldPath = currentPath.value

    inputPath.value = newPath
    currentPath.value = newPath

    // Auto-switch based on new path
    await autoSwitchRemote()

    try {
      await refresh()
      syncInputPath()
    } catch (error) {
      inputPath.value = oldInputPath
      currentPath.value = oldPath
      previousPath.value = oldPath
    }
  } else {
    // Normal mode
    if (currentPath.value.startsWith('~/')) {
      if (currentPath.value === '~/' || currentPath.value === '~') {
        return // Already at home
      }
      const pathWithoutTilde = currentPath.value.substring(2)
      const pathParts = pathWithoutTilde.split('/').filter(p => p)
      pathParts.pop()
      newPath = pathParts.length === 0 ? '~/' : '~/' + pathParts.join('/')
    } else {
      const pathParts = currentPath.value.split('/').filter(p => p)
      pathParts.pop()
      newPath = '/' + pathParts.join('/')
    }

    const oldPath = currentPath.value

    // Update previousPath before changing currentPath (for abort functionality)
    previousPath.value = oldPath

    currentPath.value = newPath

    try {
      await refresh()
      syncInputPath()
    } catch (error) {
      currentPath.value = oldPath
      previousPath.value = oldPath
    }
  }
}

async function navigateInto(dirname) {
  const oldPath = currentPath.value
  const oldInputPath = inputPath.value

  // Update previousPath before changing currentPath (for abort functionality)
  previousPath.value = oldPath

  // In absolute paths mode, build absolute path and auto-switch (works for both local and remote paths)
  if (absolutePathsMode.value && (inputPath.value.startsWith('/') || inputPath.value.includes(':'))) {
    const newAbsPath = inputPath.value.endsWith('/')
      ? inputPath.value + dirname
      : inputPath.value + '/' + dirname

    inputPath.value = newAbsPath
    currentPath.value = newAbsPath

    // Auto-switch based on new path
    await autoSwitchRemote()
  } else {
    // Normal mode
    currentPath.value = currentPath.value.endsWith('/')
      ? currentPath.value + dirname
      : currentPath.value + '/' + dirname
  }

  try {
    await refresh()
    syncInputPath()
  } catch (error) {
    currentPath.value = oldPath
    inputPath.value = oldInputPath
    previousPath.value = oldPath
  }
}

// File selection
function handleFileClick(index, event) {
  // Update last focused pane
  appStore.setLastFocusedPane(props.pane)

  // Clear opposite pane selection
  const oppositePane = props.pane === 'left' ? 'right' : 'left'
  appStore.setPaneSelection(oppositePane, [])

  let newSelection = [...paneState.value.selectedIndexes]

  if (event.ctrlKey || event.metaKey) {
    // Toggle selection
    const idx = newSelection.indexOf(index)
    if (idx >= 0) {
      newSelection.splice(idx, 1)
    } else {
      newSelection.push(index)
    }
  } else if (event.shiftKey && newSelection.length > 0) {
    // Range selection using visual order
    const lastIndex = newSelection[newSelection.length - 1]

    // Convert original indexes to visual positions
    const lastVisual = visualOrder.value[lastIndex] ?? lastIndex
    const currentVisual = visualOrder.value[index] ?? index

    // Calculate range in visual space
    const visualStart = Math.min(lastVisual, currentVisual)
    const visualEnd = Math.max(lastVisual, currentVisual)

    // Convert visual positions back to original indexes
    newSelection = []
    Object.keys(visualOrder.value).forEach(origIndex => {
      const visualPos = visualOrder.value[origIndex]
      if (visualPos >= visualStart && visualPos <= visualEnd) {
        newSelection.push(parseInt(origIndex))
      }
    })
  } else {
    // Single selection
    newSelection = [index]
  }

  appStore.setPaneSelection(props.pane, newSelection)
}

async function handleFileDblClick(file) {
  if (file.IsDir) {
    navigateInto(file.Name)
    return
  }

  // It's a file - check if we can preview it
  try {
    const filePath = currentPath.value === '/' ? `/${file.Name}` : `${currentPath.value}/${file.Name}`
    const fullPath = buildOperationPath(filePath)

    // Check if file can be previewed
    const response = await apiCall('/api/files/can-preview', 'POST', {
      path: fullPath
    })

    if (response.can_preview) {
      // Can preview - open in new tab
      openFilePreview(fullPath)
    } else {
      // Cannot preview - show download confirmation
      downloadConfirmFile.value = file.Name
      downloadConfirmSize.value = formatFileSize(file.Size)
      downloadConfirmPath.value = fullPath
      showDownloadConfirm.value = true
    }
  } catch (error) {
    console.error('Error checking file preview:', error)
    // On error, fall back to download confirmation
    downloadConfirmFile.value = file.Name
    downloadConfirmSize.value = formatFileSize(file.Size)
    const remote = selectedRemote.value
    const filePath = currentPath.value === '/' ? `/${file.Name}` : `${currentPath.value}/${file.Name}`
    downloadConfirmPath.value = remote ? `${remote}:${filePath}` : filePath
    showDownloadConfirm.value = true
  }
}

function openFilePreview(path) {
  // Open file preview in new tab
  // We need to make a POST request to /api/files/preview and open the response in a new window
  // Since we can't easily do this with fetch and window.open, we'll create a form and submit it

  const token = getAuthToken()
  const url = '/api/files/preview'

  // Create a form
  const form = document.createElement('form')
  form.method = 'POST'
  form.action = url
  form.target = '_blank'  // Open in new tab

  // Add path field
  const pathInput = document.createElement('input')
  pathInput.type = 'hidden'
  pathInput.name = 'path'
  pathInput.value = path
  form.appendChild(pathInput)

  // Add token field (for authentication)
  const tokenInput = document.createElement('input')
  tokenInput.type = 'hidden'
  tokenInput.name = 'token'
  tokenInput.value = token
  form.appendChild(tokenInput)

  // Submit form
  document.body.appendChild(form)
  form.submit()
  document.body.removeChild(form)
}

async function confirmDownload() {
  // User confirmed download - trigger the download
  showDownloadConfirm.value = false

  try {
    const response = await apiCall('/api/files/download/prepare', 'POST', {
      paths: [downloadConfirmPath.value],
      remote_config: null
    })

    if (response.type === 'direct') {
      // Direct download
      await downloadDirect(downloadConfirmPath.value)
    } else if (response.type === 'zip_job') {
      // ZIP job created - notify user and watch for completion
      alert(`Download preparation started. Job ID: ${response.job_id}\nYour download will start automatically when ready.`)
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
  // Watch for job completion via SSE or polling
  // This is handled by the JobPanel component
  // For now, just log it - the user will see it in the jobs panel
  console.log(`Watching job ${jobId} for download completion`)
}

function handleMouseDown(index, event) {
  // Auto-select on drag if not already selected
  if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
    if (!isSelected(index)) {
      appStore.setPaneSelection(props.pane, [index])

      // Clear opposite pane
      const oppositePane = props.pane === 'left' ? 'right' : 'left'
      appStore.setPaneSelection(oppositePane, [])
    }
  }
}

// Context menu
function handleFileContextMenu(index, event) {
  event.preventDefault()
  event.stopPropagation()

  if (!isSelected(index)) {
    appStore.setPaneSelection(props.pane, [index])
  }
  appStore.setLastFocusedPane(props.pane)

  if (contextMenuHandler) {
    contextMenuHandler.show(props.pane, event)
  }
}

function handleParentContextMenu(event) {
  event.preventDefault()
  event.stopPropagation()

  appStore.setPaneSelection(props.pane, [])
  appStore.setLastFocusedPane(props.pane)

  if (contextMenuHandler) {
    contextMenuHandler.show(props.pane, event)
  }
}

function handleContainerClick(event) {
  // Deselect if clicking on empty space
  if (event.target.classList.contains('file-grid') ||
      event.target.classList.contains('file-list') ||
      event.target.tagName === 'TABLE') {
    appStore.setPaneSelection(props.pane, [])
    appStore.setLastFocusedPane(props.pane)
  }
}

function handleContainerContextMenu(event) {
  if (event.target.classList.contains('file-grid') ||
      event.target.classList.contains('file-list') ||
      event.target.tagName === 'TABLE') {
    event.preventDefault()
    appStore.setPaneSelection(props.pane, [])
    appStore.setLastFocusedPane(props.pane)

    if (contextMenuHandler) {
      contextMenuHandler.show(props.pane, event)
    }
  }
}

// Drag and drop
function handleDragStart(index, event) {
  event.dataTransfer.effectAllowed = 'copy'
  event.dataTransfer.setData('text/plain', JSON.stringify({
    pane: props.pane,
    indexes: paneState.value.selectedIndexes
  }))
}

function handleDragOver(event) {
  event.preventDefault()
  event.dataTransfer.dropEffect = 'copy'
  event.currentTarget.classList.add('drag-over')
}

function handleDragLeave(event) {
  event.currentTarget.classList.remove('drag-over')
}

async function handleDrop(event) {
  event.preventDefault()
  event.currentTarget.classList.remove('drag-over')

  const dragDataText = event.dataTransfer.getData('text/plain')
  const items = event.dataTransfer.items
  const externalFiles = event.dataTransfer.files

  // Check if this is external file drop (from desktop)
  if ((items || externalFiles) && externalFiles.length > 0 && !dragDataText) {
    // External file drop from desktop - check for folders
    if (items && items.length > 0) {
      // Use DataTransferItem API to support folders (Chrome/Edge/Safari)
      await handleExternalDropWithFolders(items)
    } else {
      // Fallback to simple file drop (Firefox)
      await handleExternalFileDrop(externalFiles)
    }
    return
  }

  // Internal drag-drop
  const data = JSON.parse(dragDataText)
  if (data.pane === props.pane) {
    return // Can't drop on same pane
  }

  // Use file operations to handle drag-drop
  if (fileOperations) {
    fileOperations.handleDragDrop(data.pane, props.pane, data.indexes)
  }
}

/**
 * Traverse file tree recursively for folder uploads
 */
async function traverseFileTree(entry, path, filesWithPaths) {
  if (entry.isFile) {
    // Get the file
    const file = await new Promise((resolve, reject) => {
      entry.file(resolve, reject)
    })
    const fullPath = path + file.name
    filesWithPaths.push({ file, path: fullPath })
  } else if (entry.isDirectory) {
    // Read directory
    const dirReader = entry.createReader()
    const entries = await new Promise((resolve, reject) => {
      dirReader.readEntries(resolve, reject)
    })

    for (const childEntry of entries) {
      await traverseFileTree(childEntry, path + entry.name + '/', filesWithPaths)
    }
  }
}

/**
 * Handle external drop with folder support
 */
async function handleExternalDropWithFolders(items) {
  try {
    // Collect all files (including from folders recursively)
    const filesWithPaths = []

    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.kind === 'file') {
        const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : item.getAsEntry?.()
        if (entry) {
          await traverseFileTree(entry, '', filesWithPaths)
        } else {
          // Fallback for browsers without folder support
          const file = item.getAsFile()
          if (file) {
            filesWithPaths.push({ file, path: file.name })
          }
        }
      }
    }

    if (filesWithPaths.length === 0) {
      alert('No files found to upload')
      return
    }

    // Start upload
    await handleExternalFileUpload(
      filesWithPaths,
      selectedRemote.value,
      currentPath.value,
      true,
      refresh
    )
  } catch (error) {
    console.error('External drop with folders failed:', error)
    alert(`Failed to upload files: ${error.message}`)
  }
}

/**
 * Handle simple external file drop (no folders)
 */
async function handleExternalFileDrop(files) {
  if (files.length === 0) {
    return
  }

  const fileArray = Array.from(files)

  try {
    await handleExternalFileUpload(
      fileArray,
      selectedRemote.value,
      currentPath.value,
      false,
      refresh
    )
  } catch (error) {
    console.error('External file drop failed:', error)
    alert(`Failed to upload files: ${error.message}`)
  }
}

// Handle remotes changed event
async function handleRemotesChanged() {
  await loadRemotes()
  // Refresh aliases detection when remotes change
  if (absolutePathsMode.value) {
    await detectAliases()
  }
}

// Handle job completion event
function handleJobCompleted(event) {
  // Support both old format {jobId, dstPath} and new format (full job object)
  const detail = event.detail
  const jobId = detail.jobId || detail.job_id
  const dstPath = detail.dstPath || detail.dst_path

  if (!dstPath) return

  // Parse destination path (format: "remote:path" or just "path" for local)
  let dstRemote = ''
  let dstDir = ''

  if (dstPath.includes(':')) {
    const parts = dstPath.split(':', 2)
    dstRemote = parts[0]
    dstDir = parts[1] || '/'
  } else {
    dstRemote = ''
    dstDir = dstPath || '/'
  }

  // Get directory from destination path
  const lastSlashIndex = dstDir.lastIndexOf('/')
  if (lastSlashIndex > 0) {
    dstDir = dstDir.substring(0, lastSlashIndex)
  } else if (lastSlashIndex === 0) {
    dstDir = '/'
  }

  // Check if this pane is showing the destination
  if (selectedRemote.value === dstRemote && currentPath.value === dstDir) {
    refresh()
  }
}

// Build full path for operations (handles absolute paths mode)
function buildOperationPath(relativePath) {
  if (absolutePathsMode.value && currentAliasBasePath.value) {
    // In absolute paths mode with a local alias - use absolute path
    return currentAliasBasePath.value + relativePath
  } else if (selectedRemote.value) {
    // Normal remote - use remote:path format
    return `${selectedRemote.value}:${relativePath}`
  } else {
    // Local filesystem - use path as-is
    return relativePath
  }
}

// Find matching alias for a path (longest prefix match)
// Supports both local paths (e.g., "/home/user/docs") and remote paths (e.g., "gdrive:MyFiles/subfolder")
function findMatchingAlias(path) {
  if (!absolutePathsMode.value) {
    return null
  }

  // Determine if this is a local path or remote path
  const isLocalPath = path.startsWith('/')
  const isRemotePath = path.includes(':') && !path.startsWith('/')

  if (!isLocalPath && !isRemotePath) {
    return null // Not a valid absolute path
  }

  // Find all aliases that match
  const matches = localAliases.value.filter(a => {
    // Only match local aliases with local paths, and remote aliases with remote paths
    if (isLocalPath && !a.isLocal) return false
    if (isRemotePath && a.isLocal) return false

    // Special case: if basePath is '/' (root), it matches all local absolute paths
    if (a.basePath === '/' && isLocalPath) {
      return true
    }

    // Exact match
    if (path === a.basePath) {
      return true
    }

    // Prefix match
    if (isLocalPath) {
      // For local paths: must start with basePath + '/'
      return path.startsWith(a.basePath + '/')
    } else {
      // For remote paths: must start with basePath + '/'
      return path.startsWith(a.basePath + '/')
    }
  })

  if (matches.length === 0) {
    return null // No match
  }

  // Sort by base path length (longest first) for most specific match
  matches.sort((a, b) => b.basePath.length - a.basePath.length)

  // If multiple aliases have same base path length, sort alphabetically
  const longestLength = matches[0].basePath.length
  const longestMatches = matches.filter(a => a.basePath.length === longestLength)

  if (longestMatches.length > 1) {
    longestMatches.sort((a, b) => a.name.localeCompare(b.name))
  }

  return longestMatches[0]
}

// Auto-switch remote based on current path
async function autoSwitchRemote() {
  if (!absolutePathsMode.value) return

  const typedPath = currentPath.value

  // Check if this is a local path or remote path
  const isLocalPath = typedPath.startsWith('/')
  const isRemotePath = typedPath.includes(':') && !typedPath.startsWith('/')

  if (!isLocalPath && !isRemotePath) {
    return // Not an absolute path, don't auto-switch
  }

  // Try to find a matching alias
  const matchingAlias = findMatchingAlias(typedPath)

  if (matchingAlias) {
    // Special case: if alias points to filesystem root, use local filesystem instead
    // This avoids backend errors when aliases point to '/'
    if (matchingAlias.isLocal && matchingAlias.basePath === '/') {
      selectedRemote.value = ''
      currentAliasBasePath.value = ''
      currentPath.value = typedPath
    } else {
      // Found a matching alias - switch to it
      selectedRemote.value = matchingAlias.name
      currentAliasBasePath.value = matchingAlias.basePath

      // Calculate relative path from alias base
      if (typedPath === matchingAlias.basePath) {
        currentPath.value = '/'
      } else {
        // Remove base path to get relative path
        currentPath.value = typedPath.substring(matchingAlias.basePath.length)
      }
    }
  } else {
    // No matching alias found
    if (isLocalPath) {
      // For local paths: switch to local filesystem
      selectedRemote.value = ''
      currentAliasBasePath.value = ''
      currentPath.value = typedPath
    } else {
      // For remote paths: try to extract the remote name and switch to it
      const colonIndex = typedPath.indexOf(':')
      const remoteName = typedPath.substring(0, colonIndex)
      const remotePath = typedPath.substring(colonIndex + 1)

      // Check if this remote exists
      const remoteExists = remotes.value.some(r => r.name === remoteName)
      if (remoteExists) {
        selectedRemote.value = remoteName
        currentAliasBasePath.value = ''
        currentPath.value = remotePath || '/'
      }
      // If remote doesn't exist, don't switch (leave current selection)
    }
  }
}

// Detect all aliases and their base paths (local filesystem or remote)
async function detectAliases() {
  if (!absolutePathsMode.value) return

  const detectedAliases = []

  for (const remote of remotes.value) {
    try {
      // Resolve the alias to get its base location
      const response = await apiCall('/api/remotes/resolve-alias', 'POST', {
        remote: remote.name,
        path: ''
      })

      const resolvedPath = response.resolved_path || ''

      // Check if it resolves to something (local path or remote path)
      if (resolvedPath.includes(':')) {
        const colonIndex = resolvedPath.indexOf(':')
        const beforeColon = resolvedPath.substring(0, colonIndex)
        const afterColon = resolvedPath.substring(colonIndex + 1)

        if (beforeColon.startsWith('/')) {
          // Local filesystem path - concatenate
          detectedAliases.push({
            name: remote.name,
            basePath: beforeColon + afterColon,
            isLocal: true
          })
        } else {
          // Remote path (e.g., "gdrive:MyFiles")
          detectedAliases.push({
            name: remote.name,
            basePath: resolvedPath,
            isLocal: false
          })
        }
      } else if (resolvedPath.startsWith('/')) {
        // Direct local path (no colon)
        detectedAliases.push({
          name: remote.name,
          basePath: resolvedPath,
          isLocal: true
        })
      }
    } catch (error) {
      // Ignore errors for individual remotes
      console.debug(`Could not resolve alias ${remote.name}:`, error)
    }
  }

  // Sort by name for consistent ordering
  detectedAliases.sort((a, b) => a.name.localeCompare(b.name))
  localAliases.value = detectedAliases

  console.log('Detected aliases for absolute paths mode:', localAliases.value)
}

// Initialize
onMounted(async () => {
  try {
    // Load config to get startup remote, local fs name, and absolute paths mode
    try {
      const config = await apiCall('/api/config')
      startupRemote.value = config.startup_remote || null
      localFsName.value = config.local_fs || ''
      absolutePathsMode.value = config.absolute_paths || false
    } catch (error) {
      console.error('Failed to load config:', error)
    }

    await loadRemotes()

    // Detect aliases if in absolute paths mode
    if (absolutePathsMode.value) {
      await detectAliases()
    }

    // Initialize selected remote
    if (startupRemote.value) {
      // Use the configured startup remote as default
      selectedRemote.value = startupRemote.value
      previousRemote.value = startupRemote.value
      currentPath.value = '/'

      // Set alias base path if this is a local alias in absolute paths mode
      if (absolutePathsMode.value) {
        const alias = localAliases.value.find(a => a.name === startupRemote.value)
        currentAliasBasePath.value = alias ? alias.basePath : ''
      }
    } else {
      // Use local filesystem (empty string) as default
      selectedRemote.value = ''
      previousRemote.value = ''
      currentPath.value = '/'
    }

    await refresh()
    // Sync input path with current path after initial load
    syncInputPath()
  } catch (error) {
    console.warn('Backend not available:', error.message)
  }

  // Listen for remote changes
  window.addEventListener('remotes-changed', handleRemotesChanged)

  // Listen for job completion to auto-refresh
  window.addEventListener('job-completed', handleJobCompleted)
})

// Cleanup
onUnmounted(() => {
  window.removeEventListener('remotes-changed', handleRemotesChanged)
  window.removeEventListener('job-completed', handleJobCompleted)
})

// Expose methods to parent
defineExpose({
  refresh,
  setSortBy
})
</script>
