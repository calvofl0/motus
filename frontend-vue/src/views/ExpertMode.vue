<template>
  <div id="expert-mode">
    <div class="container">
      <div class="section">
        <h2>🔐 Authentication</h2>
        <div class="form-group">
          <label>Access Token:</label>
          <input
            type="text"
            v-model="token"
            placeholder="Enter your token (check server logs)"
          />
          <div class="hint">The token is displayed when you start the server</div>
        </div>
        <button @click="authenticate">Authenticate</button>
        <div v-if="authStatus" :class="['status', authStatus.type]">
          {{ authStatus.message }}
        </div>
      </div>

      <div class="section">
        <h2>🌐 Available Remotes</h2>
        <div class="hint">
          Configure remotes using: <code>rclone config</code><br>
          List remotes using: <code>rclone listremotes</code>
        </div>
        <button @click="listRemotes">List Remotes</button>
        <div v-if="remotesOutput" class="output">{{ remotesOutput }}</div>
      </div>

      <!-- More expert mode sections will be added here -->
      <div class="section">
        <p style="color: #666; text-align: center; padding: 40px;">
          Expert mode is being migrated to Vue.js...<br>
          More functionality will be added soon.
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall, setAuthToken } from '../services/api'

const appStore = useAppStore()

const token = ref(appStore.authToken)
const authStatus = ref(null)
const remotesOutput = ref('')

async function authenticate() {
  try {
    setAuthToken(token.value)
    appStore.authToken = token.value

    // Save to cookie
    document.cookie = `motus_token=${token.value}; path=/; max-age=31536000; SameSite=Lax`

    authStatus.value = {
      type: 'success',
      message: '✓ Token set successfully'
    }
  } catch (error) {
    authStatus.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

async function listRemotes() {
  try {
    const data = await apiCall('/api/remotes')
    remotesOutput.value = data.remotes.map(r => `• ${r.name} (${r.type})`).join('\n')
  } catch (error) {
    remotesOutput.value = `Error: ${error.message}`
  }
}
</script>

<style scoped>
.status {
  margin-top: 10px;
  padding: 10px;
  border-radius: 4px;
}

.status.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.status.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
</style>
