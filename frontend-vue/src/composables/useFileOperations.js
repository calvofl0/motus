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

    try {
      const state = appStore[`${pane}Pane`]
      const oldPath = state.remote
        ? `${state.remote}:${buildPath(state.path, file.Name)}`
        : buildPath(state.path, file.Name)

      const newPath = state.remote
        ? `${state.remote}:${buildPath(state.path, newName)}`
        : buildPath(state.path, newName)

      await apiCall('/api/files/rename', 'POST', {
        old_path: oldPath,
        new_path: newPath
      })

      // Refresh pane
      await refreshPane(pane, true)
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
   * Confirm create folder
   */
  async function confirmCreateFolder(folderName) {
    const pane = createFolderPane.value
    if (!pane) return

    try {
      const state = appStore[`${pane}Pane`]
      const path = state.remote
        ? `${state.remote}:${buildPath(state.path, folderName)}`
        : buildPath(state.path, folderName)

      await apiCall('/api/files/mkdir', 'POST', { path })

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

        const dstPath = targetState.remote
          ? `${targetState.remote}:${targetState.path}/`
          : `${targetState.path}/`

        await apiCall('/api/jobs/copy', 'POST', {
          src_path: srcPath,
          dst_path: dstPath,
          copy_links: false
        })
      }

      // Refresh target pane
      await refreshPane(targetPane)

      // Trigger job update
      window.dispatchEvent(new CustomEvent('update-jobs'))
    } catch (error) {
      console.error('Copy failed:', error)
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
