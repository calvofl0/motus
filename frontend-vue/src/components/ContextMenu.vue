<template>
  <Teleport to="body">
    <div
      v-if="visible"
      ref="menuRef"
      class="context-menu"
      :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      @click="handleMenuClick"
    >
      <!-- Create Folder (only when no files selected or on empty space) -->
      <div
        v-if="canCreateFolder"
        class="context-menu-item"
        data-action="newfolder"
      >
        📁 Create Folder
      </div>

      <!-- Rename (only when single file selected) -->
      <div
        v-if="canRename"
        class="context-menu-item"
        data-action="rename"
      >
        ✏️ Rename
      </div>

      <!-- Delete (only when files selected) -->
      <div
        v-if="canDelete"
        class="context-menu-item danger"
        data-action="delete"
      >
        🗑️ Delete
      </div>

      <!-- Sort By -->
      <div class="context-menu-item has-submenu">
        📊 Sort by
        <div class="context-submenu">
          <div class="context-menu-item" data-sort="name" data-asc="true">
            Name (A-Z)
          </div>
          <div class="context-menu-item" data-sort="name" data-asc="false">
            Name (Z-A)
          </div>
          <div class="context-menu-item" data-sort="size" data-asc="true">
            Size (Smallest)
          </div>
          <div class="context-menu-item" data-sort="size" data-asc="false">
            Size (Largest)
          </div>
          <div class="context-menu-item" data-sort="date" data-asc="true">
            Date (Oldest)
          </div>
          <div class="context-menu-item" data-sort="date" data-asc="false">
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
  if (isVisible) {
    await nextTick()
    if (menuRef.value) {
      const rect = menuRef.value.getBoundingClientRect()
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

<style scoped>
.context-menu {
  position: fixed;
  background: white;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  z-index: 10000;
  min-width: 180px;
}

.context-menu-item {
  padding: 10px 16px;
  cursor: pointer;
  font-size: 14px;
  border-bottom: 1px solid #f0f0f0;
  user-select: none;
}

.context-menu-item:last-child {
  border-bottom: none;
}

.context-menu-item:hover {
  background: #f5f5f5;
}

.context-menu-item.danger:hover {
  background: #fee;
  color: #dc3545;
}

.context-menu-item.has-submenu {
  position: relative;
}

.context-menu-item.has-submenu::after {
  content: '▶';
  position: absolute;
  right: 10px;
  font-size: 10px;
}

.context-submenu {
  display: none;
  position: absolute;
  left: 100%;
  top: 0;
  background: white;
  border: 1px solid #ccc;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  min-width: 160px;
}

.context-menu-item.has-submenu:hover .context-submenu {
  display: block;
}

.context-submenu .context-menu-item {
  white-space: nowrap;
}
</style>
