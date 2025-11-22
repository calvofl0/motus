<template>
  <div id="expert-mode">
    <div class="container">
      <!-- Authentication Section -->
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

      <!-- Available Remotes Section -->
      <div class="section">
        <h2>🌐 Available Remotes</h2>
        <div class="hint">
          Configure remotes using: <code>rclone config</code><br>
          List remotes using: <code>rclone listremotes</code>
        </div>
        <button @click="listRemotes">List Remotes</button>
        <div v-if="remotesOutput" class="output">{{ remotesOutput }}</div>
      </div>

      <!-- File Operations Section -->
      <div class="section">
        <h2>📁 File Operations</h2>

        <div class="form-group">
          <label>List Files (ls):</label>
          <input
            type="text"
            v-model="lsPath"
            placeholder="Path (e.g., /home/user or remote:path)"
          />
          <button @click="listFiles">List Files</button>
        </div>
        <div v-if="lsOutput" class="output">{{ lsOutput }}</div>

        <div class="form-group">
          <label>Create Directory (mkdir):</label>
          <input
            type="text"
            v-model="mkdirPath"
            placeholder="Path to create"
          />
          <button @click="createDirectory">Create Directory</button>
        </div>
        <div v-if="mkdirOutput" :class="['status', mkdirOutput.type]">
          {{ mkdirOutput.message }}
        </div>

        <div class="form-group">
          <label>Delete File/Directory:</label>
          <input
            type="text"
            v-model="deletePath"
            placeholder="Path to delete"
          />
          <button @click="deleteFile" style="background: #dc3545;">Delete</button>
        </div>
        <div v-if="deleteOutput" :class="['status', deleteOutput.type]">
          {{ deleteOutput.message }}
        </div>
      </div>

      <!-- Job Management Section -->
      <div class="section">
        <h2>⚙️ Job Management</h2>

        <div class="form-group">
          <label>Copy:</label>
          <input
            type="text"
            v-model="copySource"
            placeholder="Source path"
          />
          <input
            type="text"
            v-model="copyDest"
            placeholder="Destination path"
            style="margin-top: 5px;"
          />
          <div style="margin-top: 10px;">
            <label style="display: inline-flex; align-items: center; font-weight: normal;">
              <input type="checkbox" v-model="copyLinks" style="width: auto; margin-right: 5px;">
              Copy symlinks as symlinks
            </label>
          </div>
          <button @click="startCopy">Start Copy Job</button>
        </div>
        <div v-if="copyOutput" :class="['status', copyOutput.type]">
          {{ copyOutput.message }}
        </div>

        <div class="form-group">
          <label>Move:</label>
          <input
            type="text"
            v-model="moveSource"
            placeholder="Source path"
          />
          <input
            type="text"
            v-model="moveDest"
            placeholder="Destination path"
            style="margin-top: 5px;"
          />
          <button @click="startMove">Start Move Job</button>
        </div>
        <div v-if="moveOutput" :class="['status', moveOutput.type]">
          {{ moveOutput.message }}
        </div>

        <div class="form-group">
          <label>Check (Integrity Verification):</label>
          <input
            type="text"
            v-model="checkSource"
            placeholder="Source path"
          />
          <input
            type="text"
            v-model="checkDest"
            placeholder="Destination path"
            style="margin-top: 5px;"
          />
          <button @click="startCheck">Start Check Job</button>
        </div>
        <div v-if="checkOutput" :class="['status', checkOutput.type]">
          {{ checkOutput.message }}
        </div>

        <div class="form-group">
          <label>Sync (⚠️ Destructive - makes destination identical to source):</label>
          <input
            type="text"
            v-model="syncSource"
            placeholder="Source path"
          />
          <input
            type="text"
            v-model="syncDest"
            placeholder="Destination path"
            style="margin-top: 5px;"
          />
          <button @click="startSync" style="background: #ff6b6b;">Start Sync Job</button>
        </div>
        <div v-if="syncOutput" :class="['status', syncOutput.type]">
          {{ syncOutput.message }}
        </div>
      </div>

      <!-- Job Status/Control Section -->
      <div class="section">
        <h2>📊 Job Status & Control</h2>

        <div class="form-group">
          <label>Job ID:</label>
          <input
            type="number"
            v-model.number="statusJobId"
            placeholder="Enter job ID"
          />
          <button @click="getJobStatus">Get Status</button>
          <button @click="watchJob" :disabled="isWatching">
            {{ isWatching ? 'Watching...' : 'Watch (SSE)' }}
          </button>
          <button @click="stopWatching" v-if="isWatching">Stop Watching</button>
          <button @click="showJobLog">Show Log</button>
          <button @click="resumeJob">Resume</button>
          <button @click="stopJob" style="background: #dc3545;">Stop Job</button>
        </div>
        <div v-if="statusOutput" class="output">{{ statusOutput }}</div>
      </div>

      <!-- Job Listing Section -->
      <div class="section">
        <h2>📋 Job Listing</h2>

        <div class="form-group">
          <button @click="listAllJobs">List All Jobs</button>
          <button @click="listRunningJobs">List Running Jobs</button>
          <button @click="listAbortedJobs">List Aborted Jobs</button>
          <button @click="clearStoppedJobs" style="background: #ffc107; color: #000;">
            Clear Stopped Jobs
          </button>
        </div>
        <div v-if="jobListOutput" class="output">{{ jobListOutput }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall, setAuthToken } from '../services/api'
import { formatFileSize } from '../services/helpers'

const appStore = useAppStore()

// Authentication
const token = ref(appStore.authToken)
const authStatus = ref(null)
const remotesOutput = ref('')

// File Operations
const lsPath = ref('')
const lsOutput = ref('')
const mkdirPath = ref('')
const mkdirOutput = ref(null)
const deletePath = ref('')
const deleteOutput = ref(null)

// Job Management
const copySource = ref('')
const copyDest = ref('')
const copyLinks = ref(false)
const copyOutput = ref(null)

const moveSource = ref('')
const moveDest = ref('')
const moveOutput = ref(null)

const checkSource = ref('')
const checkDest = ref('')
const checkOutput = ref(null)

const syncSource = ref('')
const syncDest = ref('')
const syncOutput = ref(null)

// Job Status/Control
const statusJobId = ref(null)
const statusOutput = ref('')
const isWatching = ref(false)
let eventSource = null

// Job Listing
const jobListOutput = ref('')

/**
 * Authentication
 */
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

/**
 * List configured remotes
 */
async function listRemotes() {
  try {
    const data = await apiCall('/api/remotes')
    remotesOutput.value = data.remotes.map(r => `• ${r.name} (${r.type})`).join('\n')
  } catch (error) {
    remotesOutput.value = `Error: ${error.message}`
  }
}

/**
 * List files at path
 */
async function listFiles() {
  if (!lsPath.value.trim()) {
    lsOutput.value = 'Error: Please enter a path'
    return
  }

  try {
    const data = await apiCall('/api/files/ls', 'POST', { path: lsPath.value })

    if (!data.files || data.files.length === 0) {
      lsOutput.value = '(empty directory)'
      return
    }

    // Format file list similar to ls -l
    lsOutput.value = data.files.map(file => {
      const type = file.IsDir ? 'DIR ' : 'FILE'
      const size = file.IsDir ? '        ' : formatFileSize(file.Size).padStart(8)
      const time = new Date(file.ModTime).toLocaleString()
      return `${type}  ${size}  ${time}  ${file.Name}`
    }).join('\n')
  } catch (error) {
    lsOutput.value = `Error: ${error.message}`
  }
}

/**
 * Create directory
 */
async function createDirectory() {
  if (!mkdirPath.value.trim()) {
    mkdirOutput.value = { type: 'error', message: 'Please enter a path' }
    return
  }

  try {
    await apiCall('/api/files/mkdir', 'POST', { path: mkdirPath.value })
    mkdirOutput.value = {
      type: 'success',
      message: `✓ Directory created: ${mkdirPath.value}`
    }
    mkdirPath.value = ''
  } catch (error) {
    mkdirOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Delete file or directory
 */
async function deleteFile() {
  if (!deletePath.value.trim()) {
    deleteOutput.value = { type: 'error', message: 'Please enter a path' }
    return
  }

  if (!confirm(`Are you sure you want to delete: ${deletePath.value}?`)) {
    return
  }

  try {
    await apiCall('/api/files/delete', 'POST', { path: deletePath.value })
    deleteOutput.value = {
      type: 'success',
      message: `✓ Deleted: ${deletePath.value}`
    }
    deletePath.value = ''
  } catch (error) {
    deleteOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Start copy job
 */
async function startCopy() {
  if (!copySource.value.trim() || !copyDest.value.trim()) {
    copyOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/copy', 'POST', {
      src_path: copySource.value,
      dst_path: copyDest.value,
      copy_links: copyLinks.value
    })
    copyOutput.value = {
      type: 'success',
      message: `✓ Copy job started: Job #${data.job_id}`
    }
  } catch (error) {
    copyOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Start move job
 */
async function startMove() {
  if (!moveSource.value.trim() || !moveDest.value.trim()) {
    moveOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/move', 'POST', {
      src_path: moveSource.value,
      dst_path: moveDest.value
    })
    moveOutput.value = {
      type: 'success',
      message: `✓ Move job started: Job #${data.job_id}`
    }
  } catch (error) {
    moveOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Start check job
 */
async function startCheck() {
  if (!checkSource.value.trim() || !checkDest.value.trim()) {
    checkOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/check', 'POST', {
      src_path: checkSource.value,
      dst_path: checkDest.value
    })
    checkOutput.value = {
      type: 'success',
      message: `✓ Check job started: Job #${data.job_id}`
    }
  } catch (error) {
    checkOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Start sync job
 */
async function startSync() {
  if (!syncSource.value.trim() || !syncDest.value.trim()) {
    syncOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  if (!confirm('⚠️ WARNING: Sync is destructive! It will make destination identical to source. Continue?')) {
    return
  }

  try {
    const data = await apiCall('/api/jobs/sync', 'POST', {
      src_path: syncSource.value,
      dst_path: syncDest.value
    })
    syncOutput.value = {
      type: 'success',
      message: `✓ Sync job started: Job #${data.job_id}`
    }
  } catch (error) {
    syncOutput.value = {
      type: 'error',
      message: `Failed: ${error.message}`
    }
  }
}

/**
 * Get job status
 */
async function getJobStatus() {
  if (!statusJobId.value) {
    statusOutput.value = 'Error: Please enter a job ID'
    return
  }

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}`)
    statusOutput.value = JSON.stringify(data, null, 2)
  } catch (error) {
    statusOutput.value = `Error: ${error.message}`
  }
}

/**
 * Watch job progress via SSE
 */
function watchJob() {
  if (!statusJobId.value) {
    statusOutput.value = 'Error: Please enter a job ID'
    return
  }

  // Close any existing connection
  stopWatching()

  const apiUrl = window.location.origin
  const url = `${apiUrl}/api/stream/job/${statusJobId.value}?token=${appStore.authToken}`

  eventSource = new EventSource(url)
  isWatching.value = true
  statusOutput.value = `Watching job #${statusJobId.value}...\n\n`

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      const timestamp = new Date().toLocaleTimeString()
      statusOutput.value += `[${timestamp}] ${JSON.stringify(data, null, 2)}\n\n`
    } catch (error) {
      statusOutput.value += `[Parse Error] ${event.data}\n\n`
    }
  }

  eventSource.onerror = (error) => {
    statusOutput.value += `\n[Connection Error] SSE connection failed\n`
    stopWatching()
  }
}

/**
 * Stop watching job
 */
function stopWatching() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  isWatching.value = false
}

/**
 * Show job log
 */
async function showJobLog() {
  if (!statusJobId.value) {
    statusOutput.value = 'Error: Please enter a job ID'
    return
  }

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}/log`)
    statusOutput.value = data.log || '(no log available)'
  } catch (error) {
    statusOutput.value = `Error: ${error.message}`
  }
}

/**
 * Resume job
 */
async function resumeJob() {
  if (!statusJobId.value) {
    statusOutput.value = 'Error: Please enter a job ID'
    return
  }

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}/resume`, 'POST')
    statusOutput.value = `✓ Job #${statusJobId.value} resumed\n\n${JSON.stringify(data, null, 2)}`
  } catch (error) {
    statusOutput.value = `Error: ${error.message}`
  }
}

/**
 * Stop job
 */
async function stopJob() {
  if (!statusJobId.value) {
    statusOutput.value = 'Error: Please enter a job ID'
    return
  }

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}/stop`, 'POST')
    statusOutput.value = `✓ Job #${statusJobId.value} stopped\n\n${JSON.stringify(data, null, 2)}`
  } catch (error) {
    statusOutput.value = `Error: ${error.message}`
  }
}

/**
 * List all jobs
 */
async function listAllJobs() {
  try {
    const data = await apiCall('/api/jobs')
    formatJobList(data.jobs)
  } catch (error) {
    jobListOutput.value = `Error: ${error.message}`
  }
}

/**
 * List running jobs
 */
async function listRunningJobs() {
  try {
    const data = await apiCall('/api/jobs?status=running')
    formatJobList(data.jobs)
  } catch (error) {
    jobListOutput.value = `Error: ${error.message}`
  }
}

/**
 * List aborted jobs
 */
async function listAbortedJobs() {
  try {
    const data = await apiCall('/api/jobs?status=aborted')
    formatJobList(data.jobs)
  } catch (error) {
    jobListOutput.value = `Error: ${error.message}`
  }
}

/**
 * Format job list for display
 */
function formatJobList(jobs) {
  if (!jobs || jobs.length === 0) {
    jobListOutput.value = '(no jobs)'
    return
  }

  jobListOutput.value = jobs.map(job => {
    const id = `#${job.job_id}`.padEnd(6)
    const operation = job.operation.padEnd(10)
    const status = job.status.padEnd(12)
    const progress = job.progress ? `${job.progress}%`.padStart(5) : '  N/A'
    const created = new Date(job.created_at).toLocaleString()
    return `${id} ${operation} ${status} ${progress}  ${created}\n       ${job.src_path} → ${job.dst_path || 'N/A'}`
  }).join('\n\n')
}

/**
 * Clear stopped jobs
 */
async function clearStoppedJobs() {
  if (!confirm('Clear all stopped jobs?')) {
    return
  }

  try {
    const data = await apiCall('/api/jobs/clear_stopped', 'POST')
    jobListOutput.value = `✓ Cleared ${data.cleared || 0} stopped jobs`
  } catch (error) {
    jobListOutput.value = `Error: ${error.message}`
  }
}

// Cleanup on unmount
onUnmounted(() => {
  stopWatching()
})
</script>

<style scoped>
#expert-mode {
  flex: 1;
  overflow-y: auto;
}

.container {
  max-width: 1200px;
  margin: 20px auto;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  padding: 20px;
}

.section {
  margin-bottom: 30px;
  padding: 20px;
  background: #f9f9f9;
  border-radius: 6px;
}

.section h2 {
  color: #444;
  margin-bottom: 15px;
  font-size: 18px;
}

.form-group {
  margin-bottom: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  color: #555;
  font-weight: 500;
}

input[type="text"],
input[type="password"],
input[type="number"],
textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

button {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-right: 10px;
  margin-top: 10px;
}

button:hover {
  background: #0056b3;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.output {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 15px;
  margin-top: 15px;
  font-family: monospace;
  font-size: 13px;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
}

.hint {
  font-size: 12px;
  color: #888;
  margin-top: 5px;
  margin-bottom: 15px;
}

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

code {
  background: #e9ecef;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 13px;
}
</style>
