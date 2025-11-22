<template>
  <Teleport to="body">
    <div
      v-if="visible"
      ref="menuRef"
      class="context-menu"
      :style="{
        display: 'block',
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        background: 'white',
        border: '1px solid #ccc',
        borderRadius: '6px',
        boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        zIndex: 10000,
        minWidth: '180px'
      }"
      @click="handleMenuClick"
    >
      <!-- Create Folder (only when no files selected or on empty space) -->
      <div
        v-if="canCreateFolder"
        class="context-menu-item"
        data-action="newfolder"
        style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none;"
      >
        📁 Create Folder
      </div>

      <!-- Rename (only when single file selected) -->
      <div
        v-if="canRename"
        class="context-menu-item"
        data-action="rename"
        style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none;"
      >
        ✏️ Rename
      </div>

      <!-- Delete (only when files selected) -->
      <div
        v-if="canDelete"
        class="context-menu-item danger"
        data-action="delete"
        style="padding: 10px 16px; cursor: pointer; font-size: 14px; user-select: none; color: #dc3545;"
      >
        🗑️ Delete
      </div>

      <!-- Sort By -->
      <div class="context-menu-item has-submenu" style="padding: 10px 16px; cursor: pointer; font-size: 14px; user-select: none; position: relative;">
        📊 Sort by
        <span style="position: absolute; right: 10px; font-size: 10px;">▶</span>
        <div class="context-submenu" style="display: none; position: absolute; left: 100%; top: 0; background: white; border: 1px solid #ccc; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); min-width: 160px;">
          <div class="context-menu-item" data-sort="name" data-asc="true" style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none; white-space: nowrap;">
            Name (A-Z)
          </div>
          <div class="context-menu-item" data-sort="name" data-asc="false" style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none; white-space: nowrap;">
            Name (Z-A)
          </div>
          <div class="context-menu-item" data-sort="size" data-asc="true" style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none; white-space: nowrap;">
            Size (Smallest)
          </div>
          <div class="context-menu-item" data-sort="size" data-asc="false" style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none; white-space: nowrap;">
            Size (Largest)
          </div>
          <div class="context-menu-item" data-sort="date" data-asc="true" style="padding: 10px 16px; cursor: pointer; font-size: 14px; border-bottom: 1px solid #f0f0f0; user-select: none; white-space: nowrap;">
            Date (Oldest)
          </div>
          <div class="context-menu-item" data-sort="date" data-asc="false" style="padding: 10px 16px; cursor: pointer; font-size: 14px; user-select: none; white-space: nowrap;">
            Date (Newest)
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: {
    type: Boolean,
    default: false
  },
  position: {
    type: Object,
    default: () => ({ x: 0, y: 0 })
  },
  selectedCount: {
    type: Number,
    default: 0
  }
})

const emit = defineEmits(['close', 'action', 'sort'])

const menuRef = ref(null)
const justOpened = ref(false)

// Computed
const canCreateFolder = computed(() => true) // Always available
const canRename = computed(() => props.selectedCount === 1)
const canDelete = computed(() => props.selectedCount > 0)

function handleMenuClick(event) {
  const item = event.target.closest('.context-menu-item')
  if (!item) return

  // Check if this is a submenu item (has parent with has-submenu)
  const isSubmenuItem = item.parentElement.classList.contains('context-submenu')
  if (!isSubmenuItem && item.classList.contains('has-submenu')) {
    // Don't close menu when clicking on parent of submenu
    return
  }

  const action = item.getAttribute('data-action')
  const sortBy = item.getAttribute('data-sort')
  const sortAsc = item.getAttribute('data-asc')

  if (action) {
    emit('action', action)
    close()
  } else if (sortBy) {
    emit('sort', { field: sortBy, asc: sortAsc === 'true' })
    close()
  }
}

function close() {
  emit('close')
}

// Close on click outside
function handleClickOutside(event) {
  // Don't close immediately after opening
  if (justOpened.value) {
    return
  }

  if (props.visible && menuRef.value && !menuRef.value.contains(event.target)) {
    close()
  }
}

// Close on escape key
function handleKeyDown(event) {
  if (event.key === 'Escape' && props.visible) {
    close()
  }
}

// Adjust position if menu would go off-screen
watch(() => props.visible, async (isVisible) => {
  console.log('[ContextMenu] Visibility changed:', isVisible)
  console.log('[ContextMenu] Position:', props.position)
  console.log('[ContextMenu] Selected count:', props.selectedCount)

  if (isVisible) {
    // Prevent immediate closing on the same click that opened the menu
    justOpened.value = true
    setTimeout(() => {
      justOpened.value = false
    }, 100)

    await nextTick()
    console.log('[ContextMenu] menuRef:', menuRef.value)
    if (menuRef.value) {
      const rect = menuRef.value.getBoundingClientRect()
      console.log('[ContextMenu] Menu rect:', rect)
      const viewportWidth = window.innerWidth
      const viewportHeight = window.innerHeight

      // Adjust horizontal position if off-screen
      if (rect.right > viewportWidth) {
        const adjustedX = viewportWidth - rect.width - 10
        menuRef.value.style.left = `${Math.max(10, adjustedX)}px`
      }

      // Adjust vertical position if off-screen
      if (rect.bottom > viewportHeight) {
        const adjustedY = viewportHeight - rect.height - 10
        menuRef.value.style.top = `${Math.max(10, adjustedY)}px`
      }
    } else {
      console.error('[ContextMenu] menuRef is null!')
    }
  }
})

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style>
/* Note: Not using 'scoped' because Teleport moves element outside component scope */
.context-menu {}

.context-menu-item:hover {
  background: #f5f5f5;
}

.context-menu-item.danger:hover {
  background: #fee;
  color: #dc3545;
}

.context-menu-item.has-submenu:hover .context-submenu {
  display: block !important;
}
</style>
