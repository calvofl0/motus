import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
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
  const showCompletedJobsModal = ref(false)
  const absolutePathsMode = ref(false) // Loaded from config
  const allowExpertMode = ref(false) // Whether expert mode toggle is allowed (from config)

  // Preferences state (centralized cache to avoid race conditions)
  const preferences = ref({})
  const preferencesLoaded = ref(false)

  // Remote configuration state (for dynamic local-fs behavior)
  const localFsName = ref('Local Filesystem') // Display name for local filesystem (always non-empty)
  const hideLocalFsConfig = ref(false) // Config preference: hide local-fs when possible (from config)
  const showLocalFs = ref(true) // Dynamic runtime visibility (true = show in dropdown, false = hide)
  const localFsLockedByStartup = ref(false) // True when startup-remote is unset (local-fs cannot be disabled)
  const startupRemote = ref(null) // The configured startup remote

  // Alias detection state (shared between panes, detected once)
  const allAliases = ref([]) // All detected aliases and implicit remote aliases
  const aliasesDetected = ref(false) // Flag to ensure detection only runs once
  let detectAliasesPromise = null // Promise for in-flight detection (mutex)

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
  function initializeAuth() {
    // Try to load token from URL, localStorage, or cookie
    // This must happen before any API calls (including frontend registration)
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
  }

  async function initialize() {
    // Load config to get defaults
    let configAbsolutePaths = false
    try {
      const config = await apiCall('/api/config')
      currentMode.value = config.default_mode || 'easy'
      maxUploadSize.value = config.max_upload_size || 0
      configAbsolutePaths = config.absolute_paths || false
      allowExpertMode.value = config.allow_expert_mode || false
    } catch (e) {
      console.error('Failed to load config:', e)
      currentMode.value = 'easy'
    }

    // Load user preferences (overrides config defaults)
    const prefs = await loadPreferences(apiCall)

    // Store preferences in centralized cache
    preferences.value = prefs
    preferencesLoaded.value = true

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

    // Initialize remote configuration
    await initializeRemoteConfig()

    // Detect aliases once during initialization (before panes mount)
    await detectAliases()

    // Listen for OS theme changes when in auto mode
    if (window.matchMedia) {
      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
        if (theme.value === 'auto') {
          applyTheme()
        }
      })
    }
  }

  async function initializeRemoteConfig() {
    // Load remote configuration from API
    // Backend has already normalized: local_fs is always a string, hide_local_fs is always boolean
    try {
      const config = await apiCall('/api/config')
      startupRemote.value = config.startup_remote || null

      // Store the normalized values (both always set by backend)
      localFsName.value = config.local_fs || 'Local Filesystem'
      hideLocalFsConfig.value = config.hide_local_fs || false

      // Determine if local-fs should be locked (cannot be hidden)
      // Constraint: If no startup-remote, local-fs must stay visible
      let locked = false
      if (!startupRemote.value || startupRemote.value === 'none') {
        locked = true
      }

      // Try to validate startup-remote if it's set
      if (startupRemote.value && startupRemote.value !== 'none') {
        try {
          // Try browsing the startup remote to verify it exists and is accessible
          await apiCall('/api/files/ls', 'POST', { path: `${startupRemote.value}:/` })
        } catch (error) {
          console.warn(`Startup remote '${startupRemote.value}' failed to browse:`, error.message)
          // Fallback: Lock local-fs (must stay visible)
          locked = true
        }
      }

      localFsLockedByStartup.value = locked

      // Determine initial visibility: show if locked, absolute-paths enabled, or not configured to hide
      showLocalFs.value = locked || absolutePathsMode.value || !hideLocalFsConfig.value
    } catch (error) {
      console.error('Failed to load remote config:', error)
      // Fallback to safe defaults
      localFsName.value = 'Local Filesystem'
      hideLocalFsConfig.value = false
      showLocalFs.value = true
      localFsLockedByStartup.value = true
    }
  }

  function setMode(mode) {
    // With <keep-alive>, components stay mounted and preserve their own state
    // We just update the mode value - router navigation is handled by AppHeader
    currentMode.value = mode
  }

  // Centralized preference methods (prevents race conditions)
  async function getPreference(key) {
    // Wait for preferences to load if not loaded yet
    while (!preferencesLoaded.value) {
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    return preferences.value[key]
  }

  async function setPreference(key, value) {
    // Update local cache
    preferences.value[key] = value
    // Save to backend
    await savePreferences(apiCall, preferences.value)
  }

  async function getAllPreferences() {
    // Wait for preferences to load if not loaded yet
    while (!preferencesLoaded.value) {
      await new Promise(resolve => setTimeout(resolve, 50))
    }
    return { ...preferences.value }
  }

  function toggleViewMode() {
    viewMode.value = viewMode.value === 'grid' ? 'list' : 'grid'
    // Update centralized cache
    preferences.value.view_mode = viewMode.value
    savePreferences(apiCall, preferences.value)
  }

  function toggleHiddenFiles() {
    showHiddenFiles.value = !showHiddenFiles.value
    // Update centralized cache
    preferences.value.show_hidden_files = showHiddenFiles.value
    savePreferences(apiCall, preferences.value)
  }

  function toggleAbsolutePaths() {
    absolutePathsMode.value = !absolutePathsMode.value
    // Update centralized cache
    preferences.value.absolute_paths = absolutePathsMode.value
    savePreferences(apiCall, preferences.value)

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
    // Update centralized cache
    preferences.value.theme = theme.value
    savePreferences(apiCall, preferences.value)
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

  function openCompletedJobs() {
    showCompletedJobsModal.value = true
  }

  function closeCompletedJobs() {
    showCompletedJobsModal.value = false
  }

  // Detect all aliases and add implicit remote aliases (runs once, shared by both panes)
  // Set force=true to re-detect (e.g., when remotes change)
  async function detectAliases(force = false) {
    // If already detected and not forcing, return immediately
    if (aliasesDetected.value && !force) {
      return
    }

    // If detection is already in progress, return the existing promise (mutex)
    if (detectAliasesPromise && !force) {
      return detectAliasesPromise
    }

    // Reset state if forcing re-detection
    if (force) {
      aliasesDetected.value = false
      detectAliasesPromise = null
    }

    // Start new detection
    detectAliasesPromise = (async () => {
      try {
        // Fetch all remotes
        const remotesData = await apiCall('/api/remotes')
        const remotes = remotesData.remotes || []

        const detectedAliases = []

        for (const remote of remotes) {
          // Special case: "local" type remotes are aliases to root of local filesystem
          if (remote.type === 'local') {
            detectedAliases.push({
              name: remote.name,
              basePath: '/',
              isLocal: true,
              isRemote: false
            })
            continue
          }

          // Check if this is an alias type remote
          if (remote.type === 'alias') {
            try {
              // Resolve the alias to get its base location
              const response = await apiCall('/api/remotes/resolve-alias', 'POST', {
                remote: remote.name,
                path: ''
              })

              const resolvedPath = response.resolved_path || ''

              // Check if it resolves to something (local path or remote path)
              if (resolvedPath.includes(':')) {
                const colonIndex = resolvedPath.indexOf(':')
                const beforeColon = resolvedPath.substring(0, colonIndex)
                const afterColon = resolvedPath.substring(colonIndex + 1)

                if (beforeColon.startsWith('/')) {
                  // Local filesystem path - concatenate
                  detectedAliases.push({
                    name: remote.name,
                    basePath: beforeColon + afterColon,
                    isLocal: true,
                    isRemote: false
                  })
                } else {
                  // Remote path (e.g., "gdrive:MyFiles")
                  detectedAliases.push({
                    name: remote.name,
                    basePath: resolvedPath,
                    isLocal: false,
                    isRemote: false
                  })
                }
              } else if (resolvedPath.startsWith('/')) {
                // Direct local path (no colon)
                detectedAliases.push({
                  name: remote.name,
                  basePath: resolvedPath,
                  isLocal: true,
                  isRemote: false
                })
              }
            } catch (error) {
              console.warn(`[AppStore] Failed to resolve alias '${remote.name}':`, error.message)
            }
          } else {
            // Non-alias remote - add as implicit root alias (e.g., "onedrive" -> "onedrive:")
            detectedAliases.push({
              name: remote.name,
              basePath: remote.name + ':',
              isLocal: false,
              isRemote: true // Mark as actual remote (not an alias)
            })
          }
        }

        // Sort by name for consistent ordering
        detectedAliases.sort((a, b) => a.name.localeCompare(b.name))
        allAliases.value = detectedAliases
        aliasesDetected.value = true
      } catch (error) {
        console.error('[AppStore] Failed to detect aliases:', error)
        aliasesDetected.value = true // Mark as attempted to avoid retries
      } finally {
        detectAliasesPromise = null // Clear the promise when done
      }
    })()

    return detectAliasesPromise
  }

  // Watch for absolutePathsMode changes to enforce dynamic local-fs behavior
  watch(absolutePathsMode, (newVal, oldVal) => {
    if (newVal && !oldVal) {
      // Toggling TO absolute paths - always show local-fs
      showLocalFs.value = true
    } else if (!newVal && oldVal) {
      // Toggling FROM absolute paths - restore config preference
      if (!localFsLockedByStartup.value && hideLocalFsConfig.value) {
        // Config said to hide it, so hide it again
        // Emit event that local-fs is being disabled
        // FilePanes will switch away from local-fs if they're on it
        window.dispatchEvent(new CustomEvent('local-fs-disabling'))

        // Wait for panes to react, then hide local-fs
        setTimeout(() => {
          showLocalFs.value = false
        }, 100)
      }
    }
  })

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
    showCompletedJobsModal,
    absolutePathsMode,
    allowExpertMode,
    leftPane,
    rightPane,
    contextMenu,
    localFsName,
    hideLocalFsConfig,
    showLocalFs,
    localFsLockedByStartup,
    startupRemote,
    allAliases,

    // Computed
    isEasyMode,
    isExpertMode,
    effectiveTheme,

    // Actions
    initializeAuth,
    initialize,
    initializeRemoteConfig,
    detectAliases,
    setMode,
    getPreference,
    setPreference,
    getAllPreferences,
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
    closeManageRemotes,
    openCompletedJobs,
    closeCompletedJobs
  }
})
