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
import { ref, onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import ManageRemotesModal from './components/modals/ManageRemotesModal.vue'
import InterruptedJobsModal from './components/modals/InterruptedJobsModal.vue'
import { useAppStore } from './stores/app'
import { apiCall } from './services/api'

const appStore = useAppStore()
const showInterruptedJobsModal = ref(false)
const interruptedJobs = ref([])

onMounted(async () => {
  // Initialize app on mount
  await appStore.initialize()

  // Check for interrupted jobs after initialization
  await checkInterruptedJobs()
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
