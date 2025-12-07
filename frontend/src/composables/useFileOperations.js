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
   * Get full path for a pane (with remote prefix if applicable)
   */
  function getPaneFullPath(pane) {
    const state = appStore[`${pane}Pane`]
    return state.remote ? `${state.remote}:${state.path}` : state.path
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

      const oldPath = state.remote
        ? `${state.remote}:${buildPath(state.path, file.Name)}`
        : buildPath(state.path, file.Name)

      const newPath = state.remote
        ? `${state.remote}:${buildPath(state.path, trimmedName)}`
        : buildPath(state.path, trimmedName)

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

      const path = state.remote
        ? `${state.remote}:${resolvedPath}`
        : resolvedPath

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
      const state = appStore[`${pane}Pane`]

      // Delete each file
      for (const file of files) {
        const path = state.remote
          ? `${state.remote}:${buildPath(state.path, file.Name)}`
          : buildPath(state.path, file.Name)

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

      // Copy each file
      for (const file of selectedFiles) {
        const srcPath = sourceState.remote
          ? `${sourceState.remote}:${buildPath(sourceState.path, file.Name)}`
          : buildPath(sourceState.path, file.Name)

        // Build destination path with trailing slash for directory
        let dstPath
        if (targetState.remote) {
          const remotePath = `${targetState.remote}:${targetState.path}`
          dstPath = remotePath.endsWith('/') ? remotePath : remotePath + '/'
        } else {
          dstPath = targetState.path.endsWith('/') ? targetState.path : targetState.path + '/'
        }

        console.log('Copy operation:', {
          srcPath,
          dstPath,
          file: file.Name,
          sourceRemote: sourceState.remote,
          targetRemote: targetState.remote
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

      // Refresh target pane
      await refreshPane(targetPane)

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
