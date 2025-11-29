<template>
  <div id="app">
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
import { apiCall } from './services/api'

const appStore = useAppStore()
const showInterruptedJobsModal = ref(false)
const interruptedJobs = ref([])

// Idle timeout tracking
let maxIdleTime = 0 // seconds, 0 = disabled
let lastActivityTime = Date.now()
let idleCheckInterval = null

onMounted(async () => {
  // Initialize app on mount
  await appStore.initialize()

  // Check for interrupted jobs after initialization
  await checkInterruptedJobs()

  // Setup idle timeout if configured
  setupIdleTimeout()
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
    // Check if there are running jobs
    try {
      const jobsData = await apiCall('/api/jobs?status=running')
      const runningJobs = jobsData.jobs || []

      if (runningJobs.length === 0) {
        // No running jobs and idle timeout reached - quit without confirmation
        console.log(`[Idle Timeout] Reached ${maxIdleTime}s with no activity and no running jobs - quitting`)
        await performAutoQuit()
      } else {
        console.log(`[Idle Timeout] Idle for ${idleTime}s but ${runningJobs.length} job(s) running - not quitting`)
      }
    } catch (error) {
      console.error('[Idle Timeout] Failed to check running jobs:', error)
    }
  }
}

async function performAutoQuit() {
  try {
    // Notify components to stop polling
    window.dispatchEvent(new CustomEvent('server-shutting-down'))

    // Delay to let components clean up
    await new Promise(resolve => setTimeout(resolve, 500))

    // Shutdown server
    const shutdownData = await apiCall('/api/shutdown', 'POST')

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
  }
}

onUnmounted(() => {
  // Cleanup idle timeout
  if (idleCheckInterval) {
    clearInterval(idleCheckInterval)
  }

  const activityEvents = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart', 'click']
  activityEvents.forEach(event => {
    document.removeEventListener(event, handleUserActivity)
  })
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
</style>
