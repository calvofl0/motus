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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'

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
  appStore.openManageRemotes()
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
  try {
    // Check for running jobs
    const jobsData = await apiCall('/api/jobs?status=running')
    const runningCount = jobsData.jobs ? jobsData.jobs.length : 0

    // Show confirmation with appropriate message
    let confirmMessage = 'Are you sure you want to quit the server?'
    if (runningCount > 0) {
      confirmMessage = `⚠️ Warning: ${runningCount} job(s) are currently running.\n\n` +
        `If you quit now, these jobs will be stopped and marked as interrupted.\n\n` +
        `Are you sure you want to quit?`
    }

    if (!confirm(confirmMessage)) {
      return
    }

    // Notify components to stop polling before shutdown
    window.dispatchEvent(new CustomEvent('server-shutting-down'))

    // Delay to let components clean up (intervals are 2-5s, need time for them to clear)
    await new Promise(resolve => setTimeout(resolve, 500))

    // Shutdown server
    const shutdownData = await apiCall('/api/shutdown', 'POST')

    // Show success message
    const jobsStoppedMessage = shutdownData.running_jobs_stopped > 0
      ? `<p style="color:#666; margin-bottom:20px;">
          ${shutdownData.running_jobs_stopped} running job(s) were stopped and marked as interrupted.
          You can resume them next time you start the server.
        </p>`
      : ''

    document.body.innerHTML = `
      <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <h1 style="color:#28a745; margin-bottom:20px;">✓ Server Stopped Successfully</h1>
        <p style="font-size:18px; color:#666; margin-bottom:30px;">
          The Motus server has been shut down gracefully.
        </p>
        ${jobsStoppedMessage}
        <p style="color:#999; font-size:14px;">
          You can close this window now.
        </p>
      </div>
    `
  } catch (error) {
    console.error('[Quit] Shutdown failed:', error)
    alert(`Failed to shutdown server: ${error.message}`)
  }
}

// Handle ESC key to quit when no modals or context menu are open
function handleGlobalKeydown(e) {
  if (e.key === 'Escape') {
    // Check if any modal or context menu is open
    const hasOpenModal = document.querySelector('.modal-overlay')
    const hasOpenContextMenu = document.querySelector('.context-menu')
    if (!hasOpenModal && !hasOpenContextMenu) {
      quitServer()
    }
  }
}

// Close view menu when clicking elsewhere
document.addEventListener('click', () => {
  showViewMenu.value = false
})

onMounted(() => {
  document.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
