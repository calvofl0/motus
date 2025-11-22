<template>
  <div class="pane" :class="`${pane}-pane`">
    <div class="pane-header">📂 {{ title }}</div>
    <div class="pane-toolbar">
      <div class="toolbar-row">
        <select v-model="selectedRemote" @change="onRemoteChange">
          <option value="">Local Filesystem</option>
          <option v-for="remote in remotes" :key="remote.name" :value="remote.name">
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
          title="Refresh"
        >
          ⟳
        </button>
      </div>
    </div>
    <div class="file-grid" :id="`${pane}-files`">
      <div v-if="loading" style="text-align: center; padding: 40px; color: #666;">
        Loading...
      </div>
      <div v-else-if="files.length === 0" style="text-align: center; padding: 40px; color: #666;">
        No files
      </div>
      <div v-else style="padding: 20px;">
        <p style="margin-bottom: 15px; color: #666; font-weight: 500;">
          Files ({{ files.length }}) - Full grid/list view coming soon:
        </p>
        <div v-for="file in files" :key="file.Name" style="padding: 8px; border-bottom: 1px solid #eee;">
          <span v-if="file.IsDir" style="margin-right: 8px;">📁</span>
          <span v-else style="margin-right: 8px;">📄</span>
          <span style="font-weight: 500;">{{ file.Name }}</span>
          <span v-if="!file.IsDir" style="margin-left: 10px; color: #999; font-size: 12px;">
            {{ formatSize(file.Size) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'

const props = defineProps({
  pane: {
    type: String,
    required: true,
    validator: (value) => ['left', 'right'].includes(value)
  }
})

const appStore = useAppStore()

const title = computed(() => props.pane === 'left' ? 'Server A' : 'Server B')
const paneState = computed(() =>
  props.pane === 'left' ? appStore.leftPane : appStore.rightPane
)

const selectedRemote = ref(paneState.value.remote)
const currentPath = ref(paneState.value.path)
const files = ref([])
const remotes = ref([])
const loading = ref(false)

onMounted(async () => {
  // Try to load, but don't fail if backend is down
  try {
    await loadRemotes()
    await refresh()
  } catch (error) {
    console.warn('Backend not available:', error.message)
    // Show demo data for UI testing
    files.value = [
      { Name: 'Documents', IsDir: true, Size: 0, ModTime: new Date() },
      { Name: 'Pictures', IsDir: true, Size: 0, ModTime: new Date() },
      { Name: 'example.txt', IsDir: false, Size: 1234, ModTime: new Date() }
    ]
  }
})

async function loadRemotes() {
  try {
    const data = await apiCall('/api/remotes')
    remotes.value = data.remotes
  } catch (error) {
    console.error('Failed to load remotes:', error)
  }
}

async function refresh() {
  loading.value = true
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
  } catch (error) {
    console.error('Failed to refresh pane:', error)
    alert(`Error: ${error.message}`)
  } finally {
    loading.value = false
  }
}

function onRemoteChange() {
  currentPath.value = selectedRemote.value === '' ? '~/' : '/'
  refresh()
}

function browsePath() {
  refresh()
}

function formatSize(bytes) {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
}
</script>

<style scoped>
.refresh-btn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: #28a745;
  padding: 8px;
  transition: transform 0.2s;
}

.refresh-btn:hover {
  transform: scale(1.2);
}
</style>
