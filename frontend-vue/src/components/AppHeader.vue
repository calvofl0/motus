<template>
  <div class="header">
    <div class="header-left">
      <h1>Motus</h1>
      <p class="subtitle"><em>Motus et bouche cousue</em> — A Web-based File Transfer Interface</p>
    </div>
    <div class="header-right">
      <button class="manage-remotes-button" @click="openManageRemotes">
        Manage Remotes
      </button>
      <div class="view-dropdown-container" v-if="appStore.isEasyMode">
        <button class="view-toggle-button" @click="toggleViewMenu">
          View ▾
        </button>
        <div class="view-dropdown-menu" :class="{ hidden: !showViewMenu }">
          <div class="view-menu-item" @click="switchViewMode">
            <span>{{ viewModeIcon }}</span> <span>{{ viewModeText }}</span>
          </div>
          <div class="view-menu-item" @click="toggleHiddenFiles">
            <span>{{ hiddenFilesText }}</span>
          </div>
        </div>
      </div>
      <button class="mode-toggle-button" @click="toggleMode">
        <span>{{ modeButtonText }}</span>
      </button>
      <button class="quit-button" @click="quitServer">Quit</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'

const appStore = useAppStore()
const router = useRouter()

const showViewMenu = ref(false)

const viewModeIcon = computed(() =>
  appStore.viewMode === 'grid' ? '⊞' : '☰'
)

const viewModeText = computed(() =>
  appStore.viewMode === 'grid' ? 'Grid layout' : 'List layout'
)

const hiddenFilesText = computed(() =>
  appStore.showHiddenFiles ? 'Hide hidden files' : 'Show hidden files'
)

const modeButtonText = computed(() =>
  appStore.isEasyMode ? 'Expert Mode' : 'Easy Mode'
)

function openManageRemotes() {
  // TODO: Implement manage remotes modal
  console.log('Open manage remotes')
}

function toggleViewMenu(e) {
  e.stopPropagation()
  showViewMenu.value = !showViewMenu.value
}

function switchViewMode() {
  appStore.toggleViewMode()
  showViewMenu.value = false
}

function toggleHiddenFiles() {
  appStore.toggleHiddenFiles()
  showViewMenu.value = false
}

function toggleMode() {
  const newMode = appStore.isEasyMode ? 'expert' : 'easy'
  appStore.setMode(newMode)
  router.push(newMode === 'expert' ? '/expert' : '/')
}

async function quitServer() {
  // TODO: Check running jobs
  if (confirm('Are you sure you want to quit the server?')) {
    try {
      await fetch('/api/shutdown', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `token ${appStore.authToken}`
        }
      })

      document.body.innerHTML = `
        <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
          <h1 style="color:#28a745; margin-bottom:20px;">✓ Server Stopped Successfully</h1>
          <p style="font-size:18px; color:#666; margin-bottom:30px;">
            The Motus server has been shut down gracefully.
          </p>
          <p style="color:#999; font-size:14px;">
            You can close this window now.
          </p>
        </div>
      `
    } catch (error) {
      alert(`Failed to shutdown server: ${error.message}`)
    }
  }
}

// Close view menu when clicking elsewhere
document.addEventListener('click', () => {
  showViewMenu.value = false
})
</script>
