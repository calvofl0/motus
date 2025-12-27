<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    @confirm="$emit('update:modelValue', false)"
    title="Keyboard Shortcuts"
    size="large"
  >
    <div class="shortcuts-container">
      <!-- File Navigation -->
      <div class="shortcut-section">
        <h4>File Navigation</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>↑</kbd><kbd>↓</kbd><kbd>←</kbd><kbd>→</kbd>
            <span>Navigate files and switch between panes</span>
          </div>
          <div class="shortcut-item">
            <kbd>Enter</kbd>
            <span>Open folder or download file</span>
          </div>
          <div class="shortcut-item">
            <kbd>Backspace</kbd>
            <span>Navigate to parent directory</span>
          </div>
          <div class="shortcut-item">
            <kbd>Esc</kbd>
            <span>Unselect all files</span>
          </div>
          <div class="shortcut-item">
            <kbd>Shift</kbd> + <kbd>←</kbd>
            <span>Switch to left pane (or <kbd>←</kbd> in list mode)</span>
          </div>
          <div class="shortcut-item">
            <kbd>Shift</kbd> + <kbd>→</kbd>
            <span>Switch to right pane (or <kbd>→</kbd> in list mode)</span>
          </div>
          <div class="shortcut-item">
            <kbd>PgUp</kbd><kbd>PgDn</kbd>
            <span>Scroll file list</span>
          </div>
        </div>
      </div>

      <!-- File Operations -->
      <div class="shortcut-section">
        <h4>File Operations</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>←</kbd>
            <span>Transfer to left pane</span>
          </div>
          <div class="shortcut-item">
            <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>→</kbd>
            <span>Transfer to right pane</span>
          </div>
          <div class="shortcut-item">
            <kbd>F2</kbd>
            <span>Rename selected file</span>
          </div>
          <div class="shortcut-item">
            <kbd>Del</kbd>
            <span>Delete selected file(s)</span>
          </div>
        </div>
      </div>

      <!-- Global Shortcuts -->
      <div class="shortcut-section">
        <h4>Global Shortcuts</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>F1</kbd>
            <span>Show Keyboard Shortcuts</span>
          </div>
          <div class="shortcut-item">
            <kbd>J</kbd>
            <span>Show Completed Jobs</span>
          </div>
          <div class="shortcut-item">
            <kbd>R</kbd>
            <span>Open Remotes Manager</span>
          </div>
          <div class="shortcut-item">
            <kbd>V</kbd>
            <span>Open View menu</span>
          </div>
          <div class="shortcut-item">
            <kbd>H</kbd>
            <span>Open Help menu</span>
          </div>
          <div class="shortcut-item">
            <kbd>T</kbd>
            <span>Open Theme menu</span>
          </div>
          <div v-if="appStore.allowExpertMode" class="shortcut-item">
            <kbd>E</kbd>
            <span>Toggle Expert/Easy mode</span>
          </div>
          <div class="shortcut-item">
            <kbd>Q</kbd>
            <span>Shutdown server (when no modal is open)</span>
          </div>
        </div>
      </div>

      <!-- Menu Navigation -->
      <div class="shortcut-section">
        <h4>Menu Navigation</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>↑</kbd><kbd>↓</kbd>
            <span>Navigate menu items</span>
          </div>
          <div class="shortcut-item">
            <kbd>Enter</kbd>
            <span>Activate selected menu item</span>
          </div>
          <div class="shortcut-item">
            <kbd>Esc</kbd>
            <span>Close menu</span>
          </div>
        </div>
      </div>

      <!-- Modal Scrolling -->
      <div class="shortcut-section">
        <h4>Modal Scrolling</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>↑</kbd><kbd>↓</kbd>
            <span>Scroll modal content (40px)</span>
          </div>
          <div class="shortcut-item">
            <kbd>PgUp</kbd><kbd>PgDn</kbd>
            <span>Scroll modal content (full page)</span>
          </div>
          <div class="shortcut-item">
            <kbd>Home</kbd><kbd>End</kbd>
            <span>Jump to top/bottom of modal</span>
          </div>
        </div>
      </div>

      <!-- Completed Jobs Modal -->
      <div class="shortcut-section">
        <h4>Completed Jobs Modal</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>↑</kbd><kbd>↓</kbd>
            <span>Select job</span>
          </div>
          <div class="shortcut-item">
            <kbd>Enter</kbd>
            <span>View selected job log</span>
          </div>
          <div class="shortcut-item">
            <kbd>D</kbd> or <kbd>Del</kbd>
            <span>Delete selected job</span>
          </div>
          <div class="shortcut-item">
            <kbd>P</kbd>
            <span>Purge all jobs</span>
          </div>
          <div class="shortcut-item">
            <kbd>PgUp</kbd><kbd>PgDn</kbd>
            <span>Scroll job list</span>
          </div>
        </div>
      </div>

      <!-- Manage Remotes Modal -->
      <div class="shortcut-section">
        <h4>Manage Remotes Modal</h4>
        <div class="shortcut-list">
          <div class="shortcut-item">
            <kbd>↑</kbd><kbd>↓</kbd>
            <span>Select remote</span>
          </div>
          <div class="shortcut-item">
            <kbd>Enter</kbd>
            <span>View selected remote config</span>
          </div>
          <div class="shortcut-item">
            <kbd>E</kbd>
            <span>Edit selected remote</span>
          </div>
          <div class="shortcut-item">
            <kbd>R</kbd>
            <span>Refresh OAuth for selected remote</span>
          </div>
          <div class="shortcut-item">
            <kbd>D</kbd> or <kbd>Del</kbd>
            <span>Delete selected remote</span>
          </div>
        </div>
      </div>
    </div>

    <template #footer>
      <button class="btn-primary" @click="$emit('update:modelValue', false)">
        Close
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import BaseModal from './BaseModal.vue'
import { useAppStore } from '../../stores/app'

const appStore = useAppStore()

defineProps({
  modelValue: {
    type: Boolean,
    required: true
  }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.shortcuts-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-lg);
}

.shortcut-section h4 {
  margin: 0 0 var(--spacing-md) 0;
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  border-bottom: 2px solid var(--color-primary);
  padding-bottom: var(--spacing-xs);
}

.shortcut-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.shortcut-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm);
  background: var(--color-bg-light);
  border-radius: var(--radius-sm);
}

.shortcut-item kbd {
  display: inline-block;
  padding: 4px 8px;
  font-family: monospace;
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  background: var(--color-bg-white);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  box-shadow: 0 2px 0 var(--color-border);
  min-width: 32px;
  text-align: center;
}

.shortcut-item span {
  flex: 1;
  color: var(--color-text-primary);
  font-size: var(--font-size-base);
}

.btn-primary {
  padding: var(--spacing-sm) var(--spacing-xl);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  transition: var(--transition-normal);
}

.btn-primary:hover {
  background: var(--color-primary-hover);
}
</style>
