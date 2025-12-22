<template>
  <div id="app">
    <!-- Connection Loss Banner -->
    <div v-if="connectionLost" class="connection-banner">
      ⚠️ Lost connection to server. Retrying... Check your internet connection, or restart Motus to resume jobs
    </div>

    <!-- Dim overlay when connection lost -->
    <div v-if="connectionLost" class="connection-overlay"></div>

    <AppHeader />
    <router-view />

    <!-- Global Modals -->
    <ManageRemotesModal />
    <InterruptedJobsModal
      v-model="showInterruptedJobsModal"
      :jobs="interruptedJobs"
      @jobs-resumed="onJobsResumed"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import ManageRemotesModal from './components/modals/ManageRemotesModal.vue'
import InterruptedJobsModal from './components/modals/InterruptedJobsModal.vue'
import { useAppStore } from './stores/app'
import { apiCall, getApiUrl } from './services/api'

const appStore = useAppStore()
const showInterruptedJobsModal = ref(false)
const interruptedJobs = ref([])

// Frontend registration
let frontendId = null
let heartbeatInterval = null

// Connection loss tracking
const connectionLost = ref(false)

// Idle timeout tracking
let maxIdleTime = 0 // seconds, 0 = disabled
let lastActivityTime = Date.now()
let idleCheckInterval = null

onMounted(async () => {
  // Initialize app on mount
  await appStore.initialize()

  // Register frontend with backend
  await registerFrontend()

  // Check for interrupted jobs after initialization
  await checkInterruptedJobs()

  // Setup idle timeout if configured
  setupIdleTimeout()

  // Setup beforeunload handler to unregister on tab close/refresh
  window.addEventListener('beforeunload', handleBeforeUnload)
})

async function checkInterruptedJobs() {
  try {
    const data = await apiCall('/api/jobs?status=resumable')
    if (data.jobs && data.jobs.length > 0) {
      interruptedJobs.value = data.jobs
      showInterruptedJobsModal.value = true
    }
  } catch (error) {
    console.error('Failed to check interrupted jobs:', error)
  }
}

function onJobsResumed() {
  // Could refresh job list or show a notification here
  console.log('Jobs resumed successfully')
}

// Frontend registration management
async function registerFrontend() {
  try {
    const data = await apiCall('/api/frontend/register', 'POST')
    frontendId = data.frontend_id
    console.log(`[Frontend] Registered with ID: ${frontendId}`)

    // Start heartbeat interval (every 5 seconds)
    heartbeatInterval = setInterval(sendHeartbeat, 5000)
  } catch (error) {
    console.error('[Frontend] Registration failed:', error)
    handleConnectionError(error)
  }
}

async function sendHeartbeat() {
  if (!frontendId) return

  try {
    const response = await apiCall('/api/frontend/heartbeat', 'POST', { frontend_id: frontendId })

    // Check if server is shutting down
    if (response.shutting_down) {
      console.log('[Frontend] Server shutting down - showing shutdown page')
      showShutdownPage()
      return
    }

    // Connection successful, clear connection lost flag
    if (connectionLost.value) {
      console.log('[Frontend] Connection restored')
      connectionLost.value = false
    }
  } catch (error) {
    console.error('[Frontend] Heartbeat failed:', error)
    handleConnectionError(error)
  }
}

async function unregisterFrontend() {
  if (!frontendId) return

  try {
    await apiCall('/api/frontend/unregister', 'POST', { frontend_id: frontendId })
    console.log(`[Frontend] Unregistered: ${frontendId}`)
    frontendId = null
  } catch (error) {
    // Ignore errors during unregister (server might be down)
    console.log('[Frontend] Unregister failed (server may be down):', error)
  }
}

function handleBeforeUnload() {
  // Use sendBeacon for reliable delivery on tab close/refresh
  console.log('[Frontend] beforeunload event fired, frontendId:', frontendId)

  if (frontendId) {
    try {
      const payload = { frontend_id: frontendId }
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })

      console.log('[Frontend] Sending unregister beacon with payload:', payload)

      // sendBeacon returns false if queuing failed
      const success = navigator.sendBeacon(getApiUrl('/api/frontend/unregister'), blob)
      console.log('[Frontend] sendBeacon result:', success)

      if (!success) {
        console.warn('[Frontend] sendBeacon failed to queue the request')
      }
    } catch (error) {
      console.error('[Frontend] Error in handleBeforeUnload:', error)
    }
  } else {
    console.warn('[Frontend] beforeunload fired but no frontendId available')
  }
}

function showShutdownPage() {
  // Stop heartbeat interval
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
    heartbeatInterval = null
  }

  // Notify components to stop polling
  window.dispatchEvent(new CustomEvent('server-shutting-down'))

  // Show shutdown message
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

function handleConnectionError(error) {
  // Mark connection as lost
  connectionLost.value = true
}

// Idle timeout management
async function setupIdleTimeout() {
  try {
    // Get max idle time from config
    const config = await apiCall('/api/config')
    maxIdleTime = config.max_idle_time || 0

    if (maxIdleTime > 0) {
      console.log(`[Idle Timeout] Enabled: ${maxIdleTime} seconds`)

      // Track user activity
      const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click']
      activityEvents.forEach(event => {
        document.addEventListener(event, handleUserActivity, { passive: true })
      })

      // Check idle status every 10 seconds
      idleCheckInterval = setInterval(checkIdleStatus, 10000)
    }
  } catch (error) {
    console.error('[Idle Timeout] Failed to setup:', error)
  }
}

function handleUserActivity() {
  lastActivityTime = Date.now()
}

async function checkIdleStatus() {
  if (maxIdleTime === 0) return

  const now = Date.now()
  const idleTime = Math.floor((now - lastActivityTime) / 1000) // seconds

  if (idleTime >= maxIdleTime) {
    // Idle timeout reached - unregister and show shutdown page
    // Check if there are running jobs (defensive check, backend also checks)
    try {
      const jobsData = await apiCall('/api/jobs?status=running')
      const runningJobs = jobsData.jobs || []

      if (runningJobs.length === 0) {
        // No running jobs and idle timeout reached - unregister frontend
        console.log(`[Idle Timeout] Reached ${maxIdleTime}s with no activity and no running jobs - unregistering`)
        await performAutoQuit()
      } else {
        console.log(`[Idle Timeout] Idle for ${idleTime}s but ${runningJobs.length} job(s) running - not quitting`)
      }
    } catch (error) {
      // Connection lost - treat as timeout and show shutdown page
      console.log('[Idle Timeout] Connection lost during idle check, treating as timeout')
      await performAutoQuit()
    }
  }
}

async function performAutoQuit() {
  try {
    // Stop heartbeat interval
    if (heartbeatInterval) {
      clearInterval(heartbeatInterval)
      heartbeatInterval = null
    }

    // Notify components to stop polling
    window.dispatchEvent(new CustomEvent('server-shutting-down'))

    // Unregister frontend (backend will shutdown when counter reaches 0)
    await unregisterFrontend()

    // Show success message
    document.body.innerHTML = `
      <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <h1 style="color:#28a745; margin-bottom:20px;">✓ Server Stopped (Idle Timeout)</h1>
        <p style="font-size:18px; color:#666; margin-bottom:30px;">
          The Motus server has been shut down automatically due to inactivity.
        </p>
        <p style="color:#999; font-size:14px;">
          You can close this window now.
        </p>
      </div>
    `
  } catch (error) {
    console.error('[Idle Timeout] Auto-quit failed:', error)
    // Still show the message even if unregister failed
    document.body.innerHTML = `
      <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
        <h1 style="color:#28a745; margin-bottom:20px;">✓ Server Stopped (Idle Timeout)</h1>
        <p style="font-size:18px; color:#666; margin-bottom:30px;">
          The Motus server has been shut down automatically due to inactivity.
        </p>
        <p style="color:#999; font-size:14px;">
          You can close this window now.
        </p>
      </div>
    `
  }
}

onUnmounted(() => {
  // Cleanup heartbeat interval
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval)
  }

  // Cleanup idle timeout
  if (idleCheckInterval) {
    clearInterval(idleCheckInterval)
  }

  // Remove event listeners
  const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click']
  activityEvents.forEach(event => {
    document.removeEventListener(event, handleUserActivity)
  })

  window.removeEventListener('beforeunload', handleBeforeUnload)

  // Unregister frontend on component unmount (shouldn't happen in normal operation)
  unregisterFrontend()
})
</script>

<style>
/* Global app styles */
html, body {
  overflow: hidden;
  height: 100vh;
}

#app {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Connection loss banner */
.connection-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  background: #ff9800;
  color: #000;
  padding: 12px 20px;
  text-align: center;
  font-weight: 500;
  z-index: 10000;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

/* Overlay to dim and disable UI when connection lost */
.connection-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 9999;
  pointer-events: all;
}
</style>
