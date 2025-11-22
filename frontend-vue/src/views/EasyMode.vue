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

    <!-- Context Menu -->
    <ContextMenu
      :visible="contextMenu.visible"
      :position="contextMenu.position"
      :selected-count="contextMenu.selectedCount"
      @close="closeContextMenu"
      @action="handleContextMenuAction"
      @sort="handleContextMenuSort"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, provide } from 'vue'
import { useAppStore } from '../stores/app'
import { useFileOperations } from '../composables/useFileOperations'
import FilePane from '../components/FilePane.vue'
import JobPanel from '../components/JobPanel.vue'
import RenameModal from '../components/modals/RenameModal.vue'
import CreateFolderModal from '../components/modals/CreateFolderModal.vue'
import DeleteConfirmModal from '../components/modals/DeleteConfirmModal.vue'
import DragDropConfirmModal from '../components/modals/DragDropConfirmModal.vue'
import ContextMenu from '../components/ContextMenu.vue'

const appStore = useAppStore()
const fileOps = useFileOperations()

// Refs to FilePane components
const leftPaneRef = ref(null)
const rightPaneRef = ref(null)

// Context menu state
const contextMenu = ref({
  visible: false,
  position: { x: 0, y: 0 },
  pane: null,
  selectedCount: 0
})

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
  console.log('[EasyMode] showContextMenu called', pane, event.clientX, event.clientY)
  const paneState = appStore[`${pane}Pane`]
  contextMenu.value = {
    visible: true,
    position: { x: event.clientX, y: event.clientY },
    pane,
    selectedCount: paneState.selectedIndexes.length
  }
  console.log('[EasyMode] contextMenu.value:', contextMenu.value)
}

function closeContextMenu() {
  contextMenu.value.visible = false
}

function handleContextMenuAction(action) {
  const pane = contextMenu.value.pane
  if (!pane) return

  const paneState = appStore[`${pane}Pane`]

  switch (action) {
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
  }
}

function handleContextMenuSort({ field, asc }) {
  const pane = contextMenu.value.pane
  if (!pane) return

  // Trigger sort on the pane
  const paneRef = pane === 'left' ? leftPaneRef.value : rightPaneRef.value
  if (paneRef && paneRef.setSortBy) {
    paneRef.setSortBy(field, asc)
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
