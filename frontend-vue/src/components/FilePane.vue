<template>
  <div class="pane" :class="`${pane}-pane`">
    <!-- Pane Header -->
    <div class="pane-header">📂 {{ title }}</div>

    <!-- Pane Toolbar -->
    <div class="pane-toolbar">
      <div class="toolbar-row">
        <select v-model="selectedRemote" @change="onRemoteChange">
          <option value="">Local Filesystem</option>
          <option v-for="remote in sortedRemotes" :key="remote.name" :value="remote.name">
            {{ remote.name }}
          </option>
        </select>
      </div>
      <div class="toolbar-row">
        <input
          type="text"
          v-model="currentPath"
          @keypress.enter="browsePath"
          placeholder="Path..."
        />
        <button
          class="refresh-btn"
          @click="refresh"
          @mouseover="refreshHover = true"
          @mouseout="refreshHover = false"
          title="Refresh"
          :style="{ transform: refreshHover ? 'scale(1.2)' : 'scale(1)' }"
        >
          ⟳
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

      <!-- Empty State -->
      <div v-else-if="sortedFiles.length === 0 && currentPath !== '/..' " class="empty-state">
        No files
      </div>

      <!-- Grid View -->
      <template v-else-if="viewMode === 'grid'">
        <!-- Parent Directory -->
        <div
          v-if="currentPath !== '/'"
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
            v-if="currentPath !== '/'"
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
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, inject } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'
import { useUpload } from '../composables/useUpload'

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
const selectedRemote = ref('')
const currentPath = ref('~/')
const files = ref([])
const remotes = ref([])
const loading = ref(false)
const sortBy = ref('name')
const sortAsc = ref(true)

// Computed
const title = computed(() => props.pane === 'left' ? 'Server A' : 'Server B')
const paneState = computed(() => props.pane === 'left' ? appStore.leftPane : appStore.rightPane)
const viewMode = computed(() => appStore.viewMode)
const showHiddenFiles = computed(() => appStore.showHiddenFiles)

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
async function loadRemotes() {
  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes || []
  } catch (error) {
    console.error('Failed to load remotes:', error)
  }
}

async function refresh(preserveSelection = false) {
  loading.value = true

  // Save selection if preserving
  const selectedFileNames = preserveSelection
    ? paneState.value.selectedIndexes.map(idx => files.value[idx]?.Name).filter(n => n)
    : []

  try {
    const fullPath = selectedRemote.value
      ? `${selectedRemote.value}:${currentPath.value}`
      : currentPath.value

    const data = await apiCall('/api/files/ls', 'POST', { path: fullPath })
    files.value = data.files || []

    // Update store
    appStore.setPaneFiles(props.pane, files.value)
    appStore.setPanePath(props.pane, currentPath.value)
    appStore.setPaneRemote(props.pane, selectedRemote.value)

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
    console.error('Failed to refresh pane:', error)
    alert(`Failed to list files: ${error.message}`)
  } finally {
    loading.value = false
  }
}

function onRemoteChange() {
  currentPath.value = selectedRemote.value === '' ? '~/' : '/'
  refresh()
}

async function browsePath() {
  // Expand ~ before refreshing (only for local filesystem)
  if (selectedRemote.value === '' && currentPath.value.includes('~')) {
    await expandHomePath()
  }
  refresh()
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
  currentPath.value = newPath

  try {
    await refresh()
  } catch (error) {
    currentPath.value = oldPath
  }
}

async function navigateInto(dirname) {
  const oldPath = currentPath.value
  currentPath.value = currentPath.value.endsWith('/')
    ? currentPath.value + dirname
    : currentPath.value + '/' + dirname

  try {
    await refresh()
  } catch (error) {
    currentPath.value = oldPath
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

function handleFileDblClick(file) {
  if (file.IsDir) {
    navigateInto(file.Name)
  }
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
function handleRemotesChanged() {
  loadRemotes()
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

// Initialize
onMounted(async () => {
  try {
    await loadRemotes()

    // Set initial path for local filesystem and expand home directory
    if (selectedRemote.value === '') {
      currentPath.value = '~/'
      await expandHomePath()
    }

    await refresh()
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

<style scoped>
/* Pane Structure */
.pane {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin: 0 7.5px;
}

.pane-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 15px;
  font-weight: 600;
  font-size: 16px;
}

.right-pane .pane-header {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

/* Toolbar */
.pane-toolbar {
  padding: 15px;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.toolbar-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.pane-toolbar select,
.pane-toolbar input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.refresh-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #28a745;
  padding: 8px;
  transition: transform 0.2s;
}

/* Grid View */
.file-grid {
  flex: 1;
  overflow-y: auto;
  padding: 15px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 15px;
  align-content: start;
}

.file-item {
  padding: 15px 10px;
  border: 2px solid transparent;
  border-radius: 8px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.file-item:hover {
  background: #f8f9fa;
  border-color: #007bff;
}

.file-item.selected {
  background: #e3f2fd;
  border-color: #007bff;
}

.file-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.file-name {
  font-size: 13px;
  word-break: break-word;
  color: #333;
}

/* List View */
.file-list {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.file-list table {
  width: 100%;
  border-collapse: collapse;
}

.file-list thead {
  position: sticky;
  top: 0;
  background: #f8f9fa;
  z-index: 10;
}

.file-list th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #555;
  border-bottom: 2px solid #dee2e6;
  cursor: pointer;
  user-select: none;
}

.file-list th:hover {
  background: #e9ecef;
}

.sort-indicator {
  margin-left: 5px;
  color: #007bff;
}

.file-row {
  cursor: pointer;
  transition: background 0.2s;
}

.file-row:hover {
  background: #f8f9fa;
}

.file-row.selected {
  background: #e3f2fd;
}

.file-list td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
}

.file-name-col {
  display: flex;
  align-items: center;
  gap: 8px;
}

.file-icon-small {
  font-size: 18px;
}

.file-size-col {
  width: 100px;
  text-align: right;
  color: #666;
  font-size: 13px;
}

.file-date-col {
  width: 180px;
  color: #666;
  font-size: 13px;
}

/* Column widths */
.col-name {
  min-width: 200px;
}

.col-size {
  width: 100px;
  text-align: right;
}

.col-date {
  width: 180px;
}

/* Empty State */
.empty-state {
  text-align: center;
  padding: 40px;
  color: #666;
}

/* Drag Over Effect */
.drag-over {
  background: #d4edda !important;
  border-color: #28a745 !important;
}
</style>
