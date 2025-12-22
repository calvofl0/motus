<template>
  <div class="header">
    <div class="header-left">
      <img :src="logoSrc" alt="Motus Logo" class="logo" />
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
          <div class="view-menu-item" @click="toggleAbsolutePaths">
            <span>{{ absolutePathsText }}</span>
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
  appStore.viewMode === 'grid' ? '☰' : '⊞'
)

const viewModeText = computed(() =>
  appStore.viewMode === 'grid' ? 'List layout' : 'Grid layout'
)

const hiddenFilesText = computed(() =>
  appStore.showHiddenFiles ? 'Hide hidden files' : 'Show hidden files'
)

const absolutePathsText = computed(() =>
  appStore.absolutePathsMode ? 'Relative Paths' : 'Absolute Paths'
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

const logoSrc = computed(() => {
  return appStore.effectiveTheme === 'dark' ? './img/logo-dark.png' : './img/logo.png'
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

function toggleAbsolutePaths() {
  appStore.toggleAbsolutePaths()
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
    theme: themeName,
    absolute_paths: appStore.absolutePathsMode
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
    // Check how many frontends are registered
    const frontendData = await apiCall('/api/frontend/count')
    const frontendCount = frontendData.count || 0

    // Check for running jobs
    const jobsData = await apiCall('/api/jobs?status=running')
    const runningCount = jobsData.jobs ? jobsData.jobs.length : 0

    // Build confirmation message
    let confirmMessage = 'Are you sure you want to quit the server?'

    // Warn about other tabs if they exist
    if (frontendCount > 1) {
      const otherTabs = frontendCount - 1
      confirmMessage = `⚠️ Warning: ${otherTabs} other tab(s) are currently open.\n\n` +
        `Shutting down will close the server for all tabs.\n\n`
    }

    // Warn about running jobs
    if (runningCount > 0) {
      confirmMessage += `⚠️ Warning: ${runningCount} job(s) are currently running.\n\n` +
        `These jobs will be stopped and marked as interrupted.\n\n`
    }

    confirmMessage += `Are you sure you want to quit?`

    if (!confirm(confirmMessage)) {
      return
    }

    // Show "Shutting down..." overlay before making the call
    document.body.innerHTML = `
      <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <div style="display: inline-block; position: relative;">
          <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto 20px;"></div>
          <style>
            @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
          </style>
        </div>
        <h1 style="color:#3498db; margin-bottom:20px;">Shutting Down Server...</h1>
        <p style="font-size:18px; color:#666; margin-bottom:30px;">
          Please wait while the server shuts down gracefully.
        </p>
        <p style="color:#999; font-size:14px;">
          All tabs will show a confirmation message shortly.
        </p>
      </div>
    `

    // Notify components to stop polling before shutdown
    window.dispatchEvent(new CustomEvent('server-shutting-down'))

    // Delay to let components clean up
    await new Promise(resolve => setTimeout(resolve, 500))

    // Shutdown server - backend will set shutting_down flag
    // All frontends will detect it via heartbeat and show shutdown page
    await apiCall('/api/shutdown', 'POST')

    // Heartbeat will detect shutting_down=true and show the final shutdown page
    // for all tabs (including this one) within ~5 seconds
  } catch (error) {
    console.error('[Quit] Shutdown failed:', error)
    // Restore the page since shutdown failed
    alert(`Failed to shutdown server: ${error.message}`)
    location.reload()
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
