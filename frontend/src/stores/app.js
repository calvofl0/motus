import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { apiCall, setAuthToken, getAuthToken } from '../services/api'
import { loadPreferences, savePreferences } from '../services/preferences'

export const useAppStore = defineStore('app', () => {
  // State
  const currentMode = ref('easy')
  const authToken = ref('')
  const viewMode = ref('grid')
  const showHiddenFiles = ref(false)
  const theme = ref('auto') // 'light', 'dark', or 'auto'
  const lastFocusedPane = ref('left')
  const maxUploadSize = ref(0)
  const showManageRemotesModal = ref(false)
  const absolutePathsMode = ref(false) // Loaded from config

  // Left pane state
  const leftPane = ref({
    remote: '',
    path: '~/',
    files: [],
    selectedIndexes: [],
    sortBy: 'name',
    sortAsc: true,
    aliasBasePath: '' // Base path of current alias (if applicable, for absolute paths mode)
  })

  // Right pane state
  const rightPane = ref({
    remote: '',
    path: '~/',
    files: [],
    selectedIndexes: [],
    sortBy: 'name',
    sortAsc: true,
    aliasBasePath: '' // Base path of current alias (if applicable, for absolute paths mode)
  })

  // Context menu state
  const contextMenu = ref({
    pane: null,
    items: []
  })

  // Computed
  const isEasyMode = computed(() => currentMode.value === 'easy')
  const isExpertMode = computed(() => currentMode.value === 'expert')

  // Effective theme resolves 'auto' to OS preference
  const effectiveTheme = computed(() => {
    if (theme.value === 'auto') {
      // Detect OS/browser theme preference
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        return 'dark'
      }
      return 'light'
    }
    return theme.value
  })

  // Actions
  async function initialize() {
    // Try to load token from URL, localStorage, or cookie
    const urlParams = new URLSearchParams(window.location.search)
    const tokenFromUrl = urlParams.get('token')

    if (tokenFromUrl) {
      // Token from URL - save to localStorage and cookie for persistence
      authToken.value = tokenFromUrl
      setAuthToken(tokenFromUrl)
      localStorage.setItem('motus_token', tokenFromUrl)
      document.cookie = `motus_token=${tokenFromUrl}; path=/; max-age=31536000; SameSite=Lax`
    } else {
      // Try localStorage first (works across dev/prod ports)
      const tokenFromStorage = localStorage.getItem('motus_token')
      if (tokenFromStorage) {
        authToken.value = tokenFromStorage
        setAuthToken(tokenFromStorage)
      } else {
        // Fallback to cookie (for compatibility)
        const cookies = document.cookie.split(';')
        for (let cookie of cookies) {
          const [name, value] = cookie.trim().split('=')
          if (name === 'motus_token') {
            authToken.value = value
            setAuthToken(value)
            localStorage.setItem('motus_token', value) // Sync to localStorage
            break
          }
        }
      }
    }

    // Load config to get defaults
    let configAbsolutePaths = false
    try {
      const config = await apiCall('/api/config')
      currentMode.value = config.default_mode || 'easy'
      maxUploadSize.value = config.max_upload_size || 0
      configAbsolutePaths = config.absolute_paths || false
    } catch (e) {
      console.error('Failed to load config:', e)
      currentMode.value = 'easy'
    }

    // Load user preferences (overrides config defaults)
    const prefs = await loadPreferences(apiCall)
    if (prefs.view_mode) {
      viewMode.value = prefs.view_mode
    }
    if (prefs.show_hidden_files !== undefined) {
      showHiddenFiles.value = prefs.show_hidden_files
    }
    if (prefs.theme) {
      theme.value = prefs.theme
    }
    // Use preference if set, otherwise use config default
    if (prefs.absolute_paths !== undefined) {
      absolutePathsMode.value = prefs.absolute_paths
    } else {
      absolutePathsMode.value = configAbsolutePaths
    }

    // Apply initial theme
    applyTheme()

    // Listen for OS theme changes when in auto mode
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (theme.value === 'auto') {
          applyTheme()
        }
      })
    }
  }

  function setMode(mode) {
    currentMode.value = mode
  }

  function toggleViewMode() {
    viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
    savePreferences(apiCall, {
      view_mode: viewMode.value,
      show_hidden_files: showHiddenFiles.value,
      theme: theme.value,
      absolute_paths: absolutePathsMode.value
    })
  }

  function toggleHiddenFiles() {
    showHiddenFiles.value = !showHiddenFiles.value
    savePreferences(apiCall, {
      view_mode: viewMode.value,
      show_hidden_files: showHiddenFiles.value,
      theme: theme.value,
      absolute_paths: absolutePathsMode.value
    })
  }

  function toggleAbsolutePaths() {
    absolutePathsMode.value = !absolutePathsMode.value
    savePreferences(apiCall, {
      view_mode: viewMode.value,
      show_hidden_files: showHiddenFiles.value,
      theme: theme.value,
      absolute_paths: absolutePathsMode.value
    })

    // Notify components that absolute paths mode changed
    // This triggers alias re-detection and pane refresh
    window.dispatchEvent(new CustomEvent('absolute-paths-mode-changed', {
      detail: { enabled: absolutePathsMode.value }
    }))
  }

  function toggleTheme() {
    // Cycle through: auto -> light -> dark -> auto
    if (theme.value === 'auto') {
      theme.value = 'light'
    } else if (theme.value === 'light') {
      theme.value = 'dark'
    } else {
      theme.value = 'auto'
    }

    applyTheme()
    savePreferences(apiCall, {
      view_mode: viewMode.value,
      show_hidden_files: showHiddenFiles.value,
      theme: theme.value,
      absolute_paths: absolutePathsMode.value
    })
  }

  function applyTheme() {
    // Apply the effective theme to the document element
    document.documentElement.setAttribute('data-theme', effectiveTheme.value)
  }

  function clearPaneSelection(pane) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.selectedIndexes = []
  }

  function setPaneFiles(pane, files) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.files = files
  }

  function setPanePath(pane, path) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.path = path
  }

  function setPaneRemote(pane, remote) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.remote = remote
  }

  function setPaneAliasBasePath(pane, aliasBasePath) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.aliasBasePath = aliasBasePath
  }

  function setPaneSelection(pane, selectedIndexes) {
    const state = pane === 'left' ? leftPane.value : rightPane.value
    state.selectedIndexes = selectedIndexes
  }

  function setAbsolutePathsMode(enabled) {
    absolutePathsMode.value = enabled
  }

  function setLastFocusedPane(pane) {
    lastFocusedPane.value = pane
  }

  function openManageRemotes() {
    showManageRemotesModal.value = true
  }

  function closeManageRemotes() {
    showManageRemotesModal.value = false
  }

  return {
    // State
    currentMode,
    authToken,
    viewMode,
    showHiddenFiles,
    theme,
    lastFocusedPane,
    maxUploadSize,
    showManageRemotesModal,
    absolutePathsMode,
    leftPane,
    rightPane,
    contextMenu,

    // Computed
    isEasyMode,
    isExpertMode,
    effectiveTheme,

    // Actions
    initialize,
    setMode,
    toggleViewMode,
    toggleHiddenFiles,
    toggleAbsolutePaths,
    toggleTheme,
    applyTheme,
    clearPaneSelection,
    setPaneFiles,
    setPanePath,
    setPaneRemote,
    setPaneAliasBasePath,
    setPaneSelection,
    setAbsolutePathsMode,
    setLastFocusedPane,
    openManageRemotes,
    closeManageRemotes
  }
})
