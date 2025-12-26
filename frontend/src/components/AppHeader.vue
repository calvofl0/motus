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
      <button class="completed-jobs-button" @click="openCompletedJobs">
        Completed Jobs
      </button>
      <button class="manage-remotes-button" @click="openManageRemotes">
        Manage Remotes
      </button>
      <div class="view-dropdown-container" v-if="appStore.isEasyMode">
        <button class="view-toggle-button" @click="toggleViewMenu">
          View ▾
        </button>
        <div class="view-dropdown-menu" :class="{ hidden: !showViewMenu }">
          <div class="view-menu-item" :class="{ selected: viewMenuSelectedIndex === 0 }" @click="switchViewMode">
            <span>{{ viewModeIcon }}</span> <span>{{ viewModeText }}</span>
          </div>
          <div class="view-menu-item" :class="{ selected: viewMenuSelectedIndex === 1 }" @click="toggleHiddenFiles">
            <span>{{ hiddenFilesText }}</span>
          </div>
          <div class="view-menu-item" :class="{ selected: viewMenuSelectedIndex === 2 }" @click="toggleAbsolutePaths">
            <span>{{ absolutePathsText }}</span>
          </div>
        </div>
      </div>
      <div class="help-dropdown-container" v-if="appStore.isEasyMode">
        <button class="help-toggle-button" @click="toggleHelpMenu">
          Help ▾
        </button>
        <div class="help-dropdown-menu" :class="{ hidden: !showHelpMenu }">
          <div class="help-menu-item" :class="{ selected: helpMenuSelectedIndex === 0 }" @click="showKeyboardShortcuts">
            <span>⌨️ Keyboard Shortcuts</span>
          </div>
          <div class="help-menu-item" :class="{ selected: helpMenuSelectedIndex === 1 }" @click="showGuidedTour">
            <span>📖 Show Guided Tour</span>
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
          <div class="theme-menu-item" @click="setTheme('auto')" :class="{ active: appStore.theme === 'auto', selected: themeMenuSelectedIndex === 0 }">
            <span>☀️/🌙 Auto</span>
          </div>
          <div class="theme-menu-item" @click="setTheme('light')" :class="{ active: appStore.theme === 'light', selected: themeMenuSelectedIndex === 1 }">
            <span>☀️ Light</span>
          </div>
          <div class="theme-menu-item" @click="setTheme('dark')" :class="{ active: appStore.theme === 'dark', selected: themeMenuSelectedIndex === 2 }">
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
import { startGuidedTour } from '../services/guidedTour'

const appStore = useAppStore()
const router = useRouter()

const showViewMenu = ref(false)
const showHelpMenu = ref(false)
const showThemeMenu = ref(false)
const allowExpertMode = ref(false)
const noTourConfig = ref(false)
const isQuitting = ref(false) // Prevent multiple quit confirmations

// Menu navigation state (-1 means no selection)
const viewMenuSelectedIndex = ref(-1)
const helpMenuSelectedIndex = ref(-1)
const themeMenuSelectedIndex = ref(-1)

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

function openCompletedJobs() {
  appStore.openCompletedJobs()
}

function toggleViewMenu(e) {
  e.stopPropagation()
  showViewMenu.value = !showViewMenu.value
  // Reset selected index when opening
  if (showViewMenu.value) {
    viewMenuSelectedIndex.value = -1
    showHelpMenu.value = false
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

function toggleHelpMenu(e) {
  e.stopPropagation()
  showHelpMenu.value = !showHelpMenu.value
  // Reset selected index when opening
  if (showHelpMenu.value) {
    helpMenuSelectedIndex.value = -1
    showViewMenu.value = false
    showThemeMenu.value = false
  }
}

function showKeyboardShortcuts() {
  showHelpMenu.value = false
  window.dispatchEvent(new CustomEvent('show-keyboard-shortcuts'))
}

function showGuidedTour() {
  showHelpMenu.value = false
  startGuidedTour(appStore, noTourConfig.value)
}

function toggleThemeMenu(e) {
  e.stopPropagation()
  showThemeMenu.value = !showThemeMenu.value
  // Reset selected index when opening
  if (showThemeMenu.value) {
    themeMenuSelectedIndex.value = -1
    showViewMenu.value = false
    showHelpMenu.value = false
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
  // Prevent multiple simultaneous quit attempts
  if (isQuitting.value) {
    return
  }

  try {
    isQuitting.value = true

    // Check how many frontends are registered
    const frontendData = await apiCall('/api/frontend/count')
    const frontendCount = frontendData.count || 0

    // Check for running jobs
    const jobsData = await apiCall('/api/jobs?status=running')
    const runningCount = jobsData.jobs ? jobsData.jobs.length : 0

    // Build confirmation message
    let confirmMessage = ''

    // Warn about other tabs if they exist
    if (frontendCount > 1) {
      const otherTabs = frontendCount - 1
      confirmMessage += `⚠️ Warning: ${otherTabs} other tab(s) are currently open.\n\n` +
        `Shutting down will close the server for all tabs.\n\n`
    }

    // Warn about running jobs
    if (runningCount > 0) {
      confirmMessage += `⚠️ Warning: ${runningCount} job(s) are currently running.\n\n` +
        `These jobs will be stopped and marked as interrupted.\n\n`
    }

    confirmMessage += `Are you sure you want to quit?`

    if (!confirm(confirmMessage)) {
      isQuitting.value = false
      return
    }

    // Notify components to stop polling before shutdown
    window.dispatchEvent(new CustomEvent('server-shutting-down'))

    // Delay to let components clean up
    await new Promise(resolve => setTimeout(resolve, 500))

    // Shutdown server - backend will set shutting_down flag
    // Other frontends will detect it via heartbeat and show shutdown page
    await apiCall('/api/shutdown', 'POST')

    // Show shutdown confirmation immediately (don't wait for heartbeat)
    showShutdownConfirmation()
  } catch (error) {
    console.error('[Quit] Shutdown failed:', error)
    isQuitting.value = false
    // Show error and reload
    alert(`Failed to shutdown server: ${error.message}`)
    location.reload()
  }
}

function showShutdownConfirmation() {
  // Show final shutdown message
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
}

// Handle ESC key to quit when no modals or context menu are open
function handleGlobalKeydown(e) {
  // Handle menu navigation
  if (showViewMenu.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      showViewMenu.value = false
      viewMenuSelectedIndex.value = -1
      return
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (viewMenuSelectedIndex.value === -1) {
        viewMenuSelectedIndex.value = 0
      } else {
        viewMenuSelectedIndex.value = (viewMenuSelectedIndex.value + 1) % 3 // 3 items in View menu
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (viewMenuSelectedIndex.value === -1) {
        viewMenuSelectedIndex.value = 2 // Last item
      } else {
        viewMenuSelectedIndex.value = (viewMenuSelectedIndex.value - 1 + 3) % 3
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Only activate if something is selected
      if (viewMenuSelectedIndex.value === 0) {
        switchViewMode()
      } else if (viewMenuSelectedIndex.value === 1) {
        toggleHiddenFiles()
      } else if (viewMenuSelectedIndex.value === 2) {
        toggleAbsolutePaths()
      }
    }
    return
  }

  if (showHelpMenu.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      showHelpMenu.value = false
      helpMenuSelectedIndex.value = -1
      return
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (helpMenuSelectedIndex.value === -1) {
        helpMenuSelectedIndex.value = 0
      } else {
        helpMenuSelectedIndex.value = (helpMenuSelectedIndex.value + 1) % 2 // 2 items in Help menu
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (helpMenuSelectedIndex.value === -1) {
        helpMenuSelectedIndex.value = 1 // Last item
      } else {
        helpMenuSelectedIndex.value = (helpMenuSelectedIndex.value - 1 + 2) % 2
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Only activate if something is selected
      if (helpMenuSelectedIndex.value === 0) {
        showKeyboardShortcuts()
      } else if (helpMenuSelectedIndex.value === 1) {
        showGuidedTour()
      }
    }
    return
  }

  if (showThemeMenu.value) {
    if (e.key === 'Escape') {
      e.preventDefault()
      e.stopPropagation()
      showThemeMenu.value = false
      themeMenuSelectedIndex.value = -1
      return
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (themeMenuSelectedIndex.value === -1) {
        themeMenuSelectedIndex.value = 0
      } else {
        themeMenuSelectedIndex.value = (themeMenuSelectedIndex.value + 1) % 3 // 3 items in Theme menu
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (themeMenuSelectedIndex.value === -1) {
        themeMenuSelectedIndex.value = 2 // Last item
      } else {
        themeMenuSelectedIndex.value = (themeMenuSelectedIndex.value - 1 + 3) % 3
      }
    } else if (e.key === 'Enter') {
      e.preventDefault()
      // Only activate if something is selected
      if (themeMenuSelectedIndex.value >= 0) {
        const themes = ['auto', 'light', 'dark']
        setTheme(themes[themeMenuSelectedIndex.value])
      }
    }
    return
  }

  if (e.key === 'Escape') {
    // Close View/Help/Theme dropdown menu if open
    if (showViewMenu.value || showHelpMenu.value || showThemeMenu.value) {
      e.preventDefault()
      e.stopPropagation()
      showViewMenu.value = false
      showHelpMenu.value = false
      showThemeMenu.value = false
      return
    }

    // Don't quit if files are selected (FilePane will handle unselect)
    const hasSelection = appStore.leftPane.selectedIndexes.length > 0 ||
                        appStore.rightPane.selectedIndexes.length > 0
    if (hasSelection) {
      return
    }

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
  showHelpMenu.value = false
  showThemeMenu.value = false
  viewMenuSelectedIndex.value = -1
  helpMenuSelectedIndex.value = -1
  themeMenuSelectedIndex.value = -1
})

// Event handlers for keyboard shortcuts
function handleOpenViewMenu() {
  // Close other menus and toggle View menu
  showHelpMenu.value = false
  showThemeMenu.value = false
  showViewMenu.value = !showViewMenu.value
  // Reset selection when opening
  if (showViewMenu.value) {
    viewMenuSelectedIndex.value = -1
  }
}

function handleOpenHelpMenu() {
  // Close other menus and toggle Help menu
  showViewMenu.value = false
  showThemeMenu.value = false
  showHelpMenu.value = !showHelpMenu.value
  // Reset selection when opening
  if (showHelpMenu.value) {
    helpMenuSelectedIndex.value = -1
  }
}

function handleToggleMode() {
  toggleMode()
}

function handleQuitServer() {
  quitServer()
}

onMounted(async () => {
  document.addEventListener('keydown', handleGlobalKeydown)

  // Listen for keyboard shortcut events
  window.addEventListener('open-view-menu', handleOpenViewMenu)
  window.addEventListener('open-help-menu', handleOpenHelpMenu)
  window.addEventListener('toggle-mode', handleToggleMode)
  window.addEventListener('quit-server', handleQuitServer)

  // Fetch config to check if expert mode is allowed and if tour is disabled
  try {
    const config = await apiCall('/api/config')
    allowExpertMode.value = config.allow_expert_mode || false
    noTourConfig.value = config.no_tour || false
  } catch (error) {
    console.error('Failed to fetch config:', error)
    // Default to false if config fetch fails
    allowExpertMode.value = false
    noTourConfig.value = false
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', handleGlobalKeydown)
  window.removeEventListener('open-view-menu', handleOpenViewMenu)
  window.removeEventListener('open-help-menu', handleOpenHelpMenu)
  window.removeEventListener('toggle-mode', handleToggleMode)
  window.removeEventListener('quit-server', handleQuitServer)
})
</script>
