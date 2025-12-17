import { ref } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'

export function useFileOperations() {
  const appStore = useAppStore()

  // Modal states
  const showRenameModal = ref(false)
  const showCreateFolderModal = ref(false)
  const showDeleteModal = ref(false)
  const showDragDropModal = ref(false)

  // Modal data
  const renameData = ref({ pane: null, file: null })
  const createFolderPane = ref(null)
  const deleteData = ref({ pane: null, files: [] })
  const dragDropData = ref({
    sourcePane: null,
    targetPane: null,
    files: [],
    sourcePath: '',
    destPath: ''
  })

  /**
   * Build full path for a file
   */
  function buildPath(basePath, fileName) {
    if (basePath.endsWith('/')) {
      return basePath + fileName
    }
    return basePath + '/' + fileName
  }

  /**
   * Resolve pane location to actual remote and absolute path
   * Returns {remote: string, path: string} where path is absolute on that remote
   */
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

  /**
   * Build operation path for a file (resolves aliases in absolute paths mode)
   */
  function buildOperationPath(pane, fileName) {
    const resolved = getResolvedLocation(pane)
    const filePath = buildPath(resolved.path, fileName)

    if (resolved.remote) {
      return `${resolved.remote}:${filePath}`
    } else {
      return filePath
    }
  }

  /**
   * Get full path for a pane (with remote prefix if applicable)
   * This resolves aliases in absolute paths mode
   */
  function getPaneFullPath(pane) {
    const resolved = getResolvedLocation(pane)

    if (resolved.remote) {
      return `${resolved.remote}:${resolved.path}`
    } else {
      return resolved.path
    }
  }

  /**
   * Refresh a pane
   */
  async function refreshPane(pane, preserveSelection = false) {
    // This will be called from the FilePane component
    // The FilePane component manages its own refresh
    // We emit an event to trigger it
    window.dispatchEvent(new CustomEvent('refresh-pane', {
      detail: { pane, preserveSelection }
    }))
  }

  /**
   * Open rename modal
   */
  function openRenameModal(pane, file) {
    renameData.value = { pane, file }
    showRenameModal.value = true
  }

  /**
   * Confirm rename
   */
  async function confirmRename(newName) {
    const { pane, file } = renameData.value
    if (!pane || !file) return

    const trimmedName = newName.trim()
    if (!trimmedName) {
      alert('Please enter a name')
      return
    }

    // Skip if name hasn't changed
    if (trimmedName === file.Name) {
      showRenameModal.value = false
      return
    }

    try {
      const state = appStore[`${pane}Pane`]

      // Check if destination already exists
      const existingFile = state.files.find(f => f.Name === trimmedName)
      if (existingFile) {
        alert(`A file or folder named "${trimmedName}" already exists in this directory`)
        return
      }

      // Build paths using resolved location (handles absolute paths mode)
      const oldPath = buildOperationPath(pane, file.Name)
      const newPath = buildOperationPath(pane, trimmedName)

      // Use move API for rename operation
      await apiCall('/api/jobs/move', 'POST', {
        src_path: oldPath,
        dst_path: newPath
      })

      showRenameModal.value = false

      // Refresh pane
      await refreshPane(pane, true)

      // Trigger job update
      window.dispatchEvent(new CustomEvent('update-jobs'))
    } catch (error) {
      console.error('Rename failed:', error)
      alert(`Failed to rename: ${error.message}`)
    }
  }

  /**
   * Open create folder modal
   */
  function openCreateFolderModal(pane) {
    createFolderPane.value = pane
    showCreateFolderModal.value = true
  }

  /**
   * Resolve relative path against base path
   */
  function resolveRelativePath(basePath, relativePath) {
    // If relative path starts with /, it's absolute
    if (relativePath.startsWith('/') || relativePath.startsWith('~')) {
      return relativePath
    }
    // Otherwise, join with base path
    const base = basePath.endsWith('/') ? basePath : basePath + '/'
    return base + relativePath
  }

  /**
   * Confirm create folder
   */
  async function confirmCreateFolder(folderName) {
    const pane = createFolderPane.value
    if (!pane) return

    const trimmedName = folderName.trim()
    if (!trimmedName) {
      alert('Please enter a folder name')
      return
    }

    try {
      const state = appStore[`${pane}Pane`]

      // Support relative paths - resolve against current directory
      const resolvedPath = resolveRelativePath(state.path, trimmedName)

      // Build path using resolved location (handles absolute paths mode)
      const resolved = getResolvedLocation(pane)
      const absoluteFolderPath = resolveRelativePath(resolved.path, trimmedName)

      const path = resolved.remote
        ? `${resolved.remote}:${absoluteFolderPath}`
        : absoluteFolderPath

      await apiCall('/api/files/mkdir', 'POST', { path })

      showCreateFolderModal.value = false

      // Refresh pane
      await refreshPane(pane)
    } catch (error) {
      console.error('Create folder failed:', error)
      alert(`Failed to create folder: ${error.message}`)
    }
  }

  /**
   * Open delete modal
   */
  function openDeleteModal(pane) {
    const state = appStore[`${pane}Pane`]
    const selectedFiles = state.selectedIndexes.map(idx => state.files[idx])

    if (selectedFiles.length === 0) return

    deleteData.value = {
      pane,
      files: selectedFiles
    }
    showDeleteModal.value = true
  }

  /**
   * Confirm delete
   */
  async function confirmDelete() {
    const { pane, files } = deleteData.value
    if (!pane || files.length === 0) return

    // Close modal immediately for better UX
    showDeleteModal.value = false

    try {
      // Delete each file
      for (const file of files) {
        // Build path using resolved location (handles absolute paths mode)
        const path = buildOperationPath(pane, file.Name)

        await apiCall('/api/files/delete', 'POST', { path })
      }

      // Clear selection and refresh
      appStore.setPaneSelection(pane, [])
      await refreshPane(pane)
    } catch (error) {
      console.error('Delete failed:', error)
      alert(`Failed to delete: ${error.message}`)
    }
  }

  /**
   * Copy selected files to opposite pane
   */
  async function copyToPane(sourcePane, targetPane) {
    const sourceState = appStore[`${sourcePane}Pane`]
    const targetState = appStore[`${targetPane}Pane`]

    const selectedFiles = sourceState.selectedIndexes.map(idx => sourceState.files[idx])
    if (selectedFiles.length === 0) return

    const sourcePath = getPaneFullPath(sourcePane)
    const destPath = getPaneFullPath(targetPane)

    // Show confirmation modal
    dragDropData.value = {
      sourcePane,
      targetPane,
      files: selectedFiles.map(f => f.Name),
      sourcePath,
      destPath
    }
    showDragDropModal.value = true
  }

  /**
   * Confirm drag/drop or copy operation
   */
  async function confirmCopy() {
    const { sourcePane, targetPane, files } = dragDropData.value
    if (!sourcePane || !targetPane || files.length === 0) return

    // Close modal immediately for better UX
    showDragDropModal.value = false

    try {
      const sourceState = appStore[`${sourcePane}Pane`]
      const targetState = appStore[`${targetPane}Pane`]

      // Get selected file objects
      const selectedFiles = sourceState.selectedIndexes.map(idx => sourceState.files[idx])

      // Get resolved locations for both panes (handles absolute paths mode)
      const sourceResolved = getResolvedLocation(sourcePane)
      const targetResolved = getResolvedLocation(targetPane)

      // Copy each file
      for (const file of selectedFiles) {
        // Build source path using resolved location
        const srcPath = buildOperationPath(sourcePane, file.Name)

        // Build destination path with trailing slash for directory
        let dstPath
        if (targetResolved.remote) {
          const remotePath = `${targetResolved.remote}:${targetResolved.path}`
          dstPath = remotePath.endsWith('/') ? remotePath : remotePath + '/'
        } else {
          dstPath = targetResolved.path.endsWith('/') ? targetResolved.path : targetResolved.path + '/'
        }

        console.log('Copy operation:', {
          srcPath,
          dstPath,
          file: file.Name,
          sourceRemote: sourceResolved.remote,
          targetRemote: targetResolved.remote
        })

        const response = await apiCall('/api/jobs/copy', 'POST', {
          src_path: srcPath,
          dst_path: dstPath,
          copy_links: false
        })

        console.log('Copy response:', response)
      }

      // Clear source selection
      appStore.setPaneSelection(sourcePane, [])

      // Note: Refresh will happen automatically when job completes via handleJobCompleted event
      // Trigger job update
      window.dispatchEvent(new CustomEvent('update-jobs'))
    } catch (error) {
      console.error('Copy failed:', error)
      console.error('Error details:', {
        message: error.message,
        error: error
      })
      alert(`Failed to copy: ${error.message}`)
    }
  }

  /**
   * Handle drag/drop from FilePane
   */
  function handleDragDrop(sourcePane, targetPane, indexes) {
    const sourceState = appStore[`${sourcePane}Pane`]
    const targetState = appStore[`${targetPane}Pane`]

    const files = indexes.map(idx => sourceState.files[idx])
    const sourcePath = getPaneFullPath(sourcePane)
    const destPath = getPaneFullPath(targetPane)

    dragDropData.value = {
      sourcePane,
      targetPane,
      files: files.map(f => f.Name),
      sourcePath,
      destPath
    }
    showDragDropModal.value = true
  }

  return {
    // Modal states
    showRenameModal,
    showCreateFolderModal,
    showDeleteModal,
    showDragDropModal,

    // Modal data
    renameData,
    createFolderPane,
    deleteData,
    dragDropData,

    // Functions
    openRenameModal,
    confirmRename,
    openCreateFolderModal,
    confirmCreateFolder,
    openDeleteModal,
    confirmDelete,
    copyToPane,
    confirmCopy,
    handleDragDrop,
    refreshPane
  }
}
