<template>
  <div id="app">
    <AppHeader />
    <router-view />

    <!-- Global Modals -->
    <ManageRemotesModal />
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import AppHeader from './components/AppHeader.vue'
import ManageRemotesModal from './components/modals/ManageRemotesModal.vue'
import { useAppStore } from './stores/app'

const appStore = useAppStore()

onMounted(async () => {
  // Initialize app on mount
  await appStore.initialize()
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
