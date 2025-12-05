<template>
  <div class="header">
    <div class="header-left">
      <img src="/img/logo.png" alt="Motus Logo" class="logo" />
      <div class="header-text">
        <h1>Motus</h1>
        <p class="subtitle"><em>Motus et bouche cousue</em> — A Web-based File Transfer Interface</p>
      </div>
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
      <button v-if="allowExpertMode" class="mode-toggle-button" @click="toggleMode">
        <span>{{ modeButtonText }}</span>
      </button>
      <button class="quit-button" @click="quitServer">Quit</button>
      <div class="theme-dropdown-container">
        <button class="theme-icon-button" @click="toggleThemeMenu" :title="themeTooltip">
          {{ themeIcon }}
        </button>
        <div class="theme-dropdown-menu" :class="{ hidden: !showThemeMenu }">
          <div class="theme-menu-item" @click="setTheme('auto')" :class="{ active: appStore.theme === 'auto' }">
            <span>☀️/🌙 Auto</span>
          </div>
          <div class="theme-menu-item" @click="setTheme('light')" :class="{ active: appStore.theme === 'light' }">
            <span>☀️ Light</span>
          </div>
          <div class="theme-menu-item" @click="setTheme('dark')" :class="{ active: appStore.theme === 'dark' }">
            <span>🌙 Dark</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'
import { savePreferences } from '../services/preferences'

const appStore = useAppStore()
const router = useRouter()

const showViewMenu = ref(false)
const showThemeMenu = ref(false)
const allowExpertMode = ref(false)

const viewModeIcon = computed(() =>
  appStore.viewMode === 'grid' ? '⊞' : '☰'
)

const viewModeText = computed(() =>
  appStore.viewMode === 'grid' ? 'Grid layout' : 'List layout'
)

const hiddenFilesText = computed(() =>
  appStore.showHiddenFiles ? 'Hide hidden files' : 'Show hidden files'
)

const themeIcon = computed(() => {
  if (appStore.theme === 'auto') {
    return '☀️/🌙'
  } else if (appStore.theme === 'light') {
    return '☀️'
  } else {
    return '🌙'
  }
})

const themeTooltip = computed(() => {
  if (appStore.theme === 'auto') {
    return `Theme: Auto (${appStore.effectiveTheme === 'dark' ? 'Dark' : 'Light'})`
  } else if (appStore.theme === 'light') {
    return 'Theme: Light'
  } else {
    return 'Theme: Dark'
  }
})

const modeButtonText = computed(() =>
  appStore.isEasyMode ? 'Expert Mode' : 'Easy Mode'
)

function openManageRemotes() {
  appStore.openManageRemotes()
}

function toggleViewMenu(e) {
  e.stopPropagation()
  showViewMenu.value = !showViewMenu.value
  // Close theme menu if it's open
  if (showViewMenu.value) {
    showThemeMenu.value = false
  }
}

function switchViewMode() {
  appStore.toggleViewMode()
  showViewMenu.value = false
}

function toggleHiddenFiles() {
  appStore.toggleHiddenFiles()
  showViewMenu.value = false
}

function toggleThemeMenu(e) {
  e.stopPropagation()
  showThemeMenu.value = !showThemeMenu.value
  // Close view menu if it's open
  if (showThemeMenu.value) {
    showViewMenu.value = false
  }
}

function setTheme(themeName) {
  appStore.theme = themeName
  appStore.applyTheme()
  savePreferences(apiCall, {
    view_mode: appStore.viewMode,
    show_hidden_files: appStore.showHiddenFiles,
    theme: themeName
  })
  showThemeMenu.value = false
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

// Close menus when clicking elsewhere
document.addEventListener('click', () => {
  showViewMenu.value = false
  showThemeMenu.value = false
})

onMounted(async () => {
  document.addEventListener('keydown', handleGlobalKeydown)

  // Fetch config to check if expert mode is allowed
  try {
    const config = await apiCall('/api/config')
    allowExpertMode.value = config.allow_expert_mode || false
  } catch (error) {
    console.error('Failed to fetch config:', error)
    // Default to false if config fetch fails
    allowExpertMode.value = false
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
})
</script>
