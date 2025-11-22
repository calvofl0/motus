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
      <div v-else>
        <!-- File list will be implemented here -->
        <p style="padding: 20px; text-align: center; color: #666;">
          File browser component in progress...
        </p>
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
  await loadRemotes()
  await refresh()
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
