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
          <label>Path:</label>
          <input
            type="text"
            v-model="lsPath"
            placeholder="/path or remote:/path"
          />
          <div class="hint">Example: /tmp or myS3:/bucket/folder</div>
        </div>
        <button @click="listFiles">List Files</button>
        <div v-if="lsOutput" class="output">{{ lsOutput }}</div>

        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

        <div class="form-group">
          <label>Create Directory:</label>
          <input
            type="text"
            v-model="mkdirPath"
            placeholder="/path/to/newdir or remote:/path/newdir"
          />
        </div>
        <button @click="createDirectory">Create Directory</button>
        <div v-if="mkdirOutput" :class="['status', mkdirOutput.type]">
          {{ mkdirOutput.message }}
        </div>

        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

        <div class="form-group">
          <label>Delete Path:</label>
          <input
            type="text"
            v-model="deletePath"
            placeholder="/path or remote:/path"
          />
        </div>
        <button @click="deleteFile" style="background: #dc3545;">Delete</button>
        <div v-if="deleteOutput" :class="['status', deleteOutput.type]">
          {{ deleteOutput.message }}
        </div>

        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

        <div class="form-group">
          <label>Download Path:</label>
          <input
            type="text"
            v-model="downloadPath"
            placeholder="/path/to/file or remote:/path/to/folder"
          />
          <div class="hint">Download files or folders to your computer</div>
        </div>
        <button @click="downloadFile" style="background: #17a2b8;">⬇️ Download</button>
        <div v-if="downloadOutput" :class="['status', downloadOutput.type]">
          {{ downloadOutput.message }}
        </div>
      </div>

      <!-- Job Management Section -->
      <div class="section">
        <h2>📦 Job Management</h2>

        <div class="form-group">
          <label>Source Path:</label>
          <input
            ref="srcPathInput"
            type="text"
            v-model="copySource"
            placeholder="/source or remote:/source"
            @keydown="handleJobPathKeypress($event, 'src')"
          />
        </div>
        <div class="form-group">
          <label>Destination Path:</label>
          <input
            ref="dstPathInput"
            type="text"
            v-model="copyDest"
            placeholder="/destination or remote:/destination"
            @keydown="handleJobPathKeypress($event, 'dst')"
          />
        </div>
        <div class="form-group">
          <label style="display: inline-flex; align-items: center; font-weight: normal;">
            <input type="checkbox" v-model="copyLinks" style="width: auto; margin-right: 5px;">
            Follow Symlinks
          </label>
        </div>
        <button @click="startCopy">Copy</button>
        <button @click="startMove" style="background: #ffc107; color: #000;">Move</button>
        <button @click="startCheck" style="background: #17a2b8;">Check Integrity</button>
        <button @click="startSync" style="background: #dc3545;">Sync (Destructive)</button>
        <div v-if="jobStartOutput" :class="['status', jobStartOutput.type]">
          {{ jobStartOutput.message }}
        </div>

        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

        <div class="form-group">
          <label>Job ID:</label>
          <input
            type="number"
            v-model.number="statusJobId"
            placeholder="Enter job ID"
            @keydown.enter="getJobStatus"
          />
          <div class="hint">Press ENTER to get status</div>
        </div>
        <button @click="getJobStatus">Get Status</button>
        <button @click="watchJob" :disabled="isWatching" style="background: #17a2b8;">
          {{ isWatching ? 'Watching...' : 'Watch Progress (SSE)' }}
        </button>
        <button @click="stopWatching" v-if="isWatching" style="background: #6c757d;">Stop Watching</button>
        <button @click="showJobLog" style="background: #6c757d;">Show Log</button>
        <button @click="resumeJob" style="background: #28a745;">Resume</button>
        <button @click="stopJob" style="background: #dc3545;">Stop Job</button>
        <div v-if="statusOutput" class="output">{{ statusOutput }}</div>

        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">

        <button @click="listAllJobs">List All Jobs</button>
        <button @click="listRunningJobs" style="background: #28a745;">List Running</button>
        <button @click="listAbortedJobs" style="background: #ffc107; color: #000;">List Aborted</button>
        <button @click="clearStoppedJobs" style="background: #6c757d;">Clear All Stopped Jobs</button>
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
const downloadPath = ref('')
const downloadOutput = ref(null)

// Job Management
const copySource = ref('')
const copyDest = ref('')
const copyLinks = ref(false)
const jobStartOutput = ref(null)
const srcPathInput = ref(null)
const dstPathInput = ref(null)

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
 * Download file or directory
 */
async function downloadFile() {
  if (!downloadPath.value.trim()) {
    downloadOutput.value = { type: 'error', message: 'Please enter a path to download' }
    return
  }

  try {
    downloadOutput.value = { type: 'info', message: 'Preparing download...' }

    // Call prepare endpoint
    const response = await apiCall('/api/files/download/prepare', 'POST', {
      paths: [downloadPath.value],
      remote_config: null
    })

    if (response.type === 'direct') {
      // Direct download
      downloadOutput.value = { type: 'info', message: 'Downloading file...' }
      await downloadDirect(response.path)
      downloadOutput.value = { type: 'success', message: '✓ Download started' }
      downloadPath.value = ''
    } else if (response.type === 'zip_job') {
      // ZIP job created
      downloadOutput.value = {
        type: 'info',
        message: `ZIP job created (ID: ${response.job_id}). Your download will start automatically when ready.`
      }

      // Monitor job completion
      watchJobForDownload(response.job_id)
    }
  } catch (error) {
    downloadOutput.value = {
      type: 'error',
      message: `Download failed: ${error.message}`
    }
  }
}

/**
 * Download a file directly (for small files)
 */
async function downloadDirect(path) {
  try {
    const response = await fetch('/api/files/download/direct', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `token ${appStore.authToken}`
      },
      body: JSON.stringify({ path: path, remote_config: null })
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    // Get filename from response headers or path
    const contentDisposition = response.headers.get('Content-Disposition')
    let filename = 'download'
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/)
      if (filenameMatch) filename = filenameMatch[1]
    } else {
      filename = path.split('/').pop() || 'download'
    }

    // Convert response to blob and trigger download
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
  } catch (error) {
    console.error('Direct download failed:', error)
    throw error
  }
}

/**
 * Watch for ZIP job completion and trigger download
 */
function watchJobForDownload(jobId) {
  const handleJobComplete = (event) => {
    const job = event.detail
    if (job.job_id === jobId) {
      if (job.status === 'completed') {
        // Job completed - trigger download
        const downloadToken = job.download_token
        if (downloadToken) {
          const downloadUrl = `/api/files/download/zip/${downloadToken}?token=${appStore.authToken}`
          window.location.href = downloadUrl

          downloadOutput.value = {
            type: 'success',
            message: '✓ ZIP created, download starting...'
          }
          downloadPath.value = ''
        }
        window.removeEventListener('job-completed', handleJobComplete)
      } else if (job.status === 'failed') {
        downloadOutput.value = {
          type: 'error',
          message: `Download failed: ${job.error_text || 'Unknown error'}`
        }
        window.removeEventListener('job-completed', handleJobComplete)
      }
    }
  }

  window.addEventListener('job-completed', handleJobComplete)
}

/**
 * Handle ENTER key in job path fields
 */
function handleJobPathKeypress(event, field) {
  if (event.key === 'Enter') {
    event.preventDefault()
    const srcValue = copySource.value.trim()
    const dstValue = copyDest.value.trim()

    if (field === 'src') {
      // If in source field
      if (srcValue && !dstValue) {
        // Move to destination field
        dstPathInput.value?.focus()
      } else if (srcValue && dstValue) {
        // Both filled, start copy
        startCopy()
      }
    } else if (field === 'dst') {
      // If in destination field
      if (srcValue && dstValue) {
        // Both filled, start copy
        startCopy()
      }
    }
  }
}

/**
 * Start copy job
 */
async function startCopy() {
  if (!copySource.value.trim() || !copyDest.value.trim()) {
    jobStartOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/copy', 'POST', {
      src_path: copySource.value,
      dst_path: copyDest.value,
      copy_links: copyLinks.value
    })
    statusJobId.value = data.job_id
    jobStartOutput.value = {
      type: 'success',
      message: `✓ Copy job started (ID: ${data.job_id})`
    }
  } catch (error) {
    jobStartOutput.value = {
      type: 'error',
      message: `✗ Error: ${error.message}`
    }
  }
}

/**
 * Start move job
 */
async function startMove() {
  if (!copySource.value.trim() || !copyDest.value.trim()) {
    jobStartOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/move', 'POST', {
      src_path: copySource.value,
      dst_path: copyDest.value
    })
    statusJobId.value = data.job_id
    jobStartOutput.value = {
      type: 'success',
      message: `✓ Move job started (ID: ${data.job_id})`
    }
  } catch (error) {
    jobStartOutput.value = {
      type: 'error',
      message: `✗ Error: ${error.message}`
    }
  }
}

/**
 * Start check job
 */
async function startCheck() {
  if (!copySource.value.trim() || !copyDest.value.trim()) {
    jobStartOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  try {
    const data = await apiCall('/api/jobs/check', 'POST', {
      src_path: copySource.value,
      dst_path: copyDest.value
    })
    statusJobId.value = data.job_id
    jobStartOutput.value = {
      type: 'success',
      message: `✓ Integrity check started (ID: ${data.job_id})`
    }
  } catch (error) {
    jobStartOutput.value = {
      type: 'error',
      message: `✗ Error: ${error.message}`
    }
  }
}

/**
 * Start sync job
 */
async function startSync() {
  if (!copySource.value.trim() || !copyDest.value.trim()) {
    jobStartOutput.value = { type: 'error', message: 'Please enter both source and destination' }
    return
  }

  if (!confirm(
    '⚠️ WARNING: Sync is a DESTRUCTIVE operation!\n\n' +
    'Files in the destination that don\'t exist in the source will be DELETED.\n\n' +
    'Are you sure you want to continue?'
  )) {
    return
  }

  try {
    const data = await apiCall('/api/jobs/sync', 'POST', {
      src_path: copySource.value,
      dst_path: copyDest.value
    })
    statusJobId.value = data.job_id
    jobStartOutput.value = {
      type: 'success',
      message: `✓ Sync job started (ID: ${data.job_id})`
    }
  } catch (error) {
    jobStartOutput.value = {
      type: 'error',
      message: `✗ Error: ${error.message}`
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

  // Stop watching if currently watching
  stopWatching()

  try {
    const job = await apiCall(`/api/jobs/${statusJobId.value}`)
    const output = `
Job ID: ${job.job_id}
Operation: ${job.operation}
Status: ${job.status}
Progress: ${job.progress}%
Source: ${job.src_path}
Destination: ${job.dst_path}
Created: ${job.created_at}
${job.finished_at ? 'Finished: ' + job.finished_at : ''}
${job.error_text ? 'Error: ' + job.error_text : ''}

Output:
${job.text || '(no output yet)'}
    `.trim()
    statusOutput.value = output
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
  const url = `${apiUrl}/api/stream/jobs/${statusJobId.value}?token=${appStore.authToken}`

  eventSource = new EventSource(url)
  isWatching.value = true
  statusOutput.value = `Watching job #${statusJobId.value}...\n\n`

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)

      if (data.error) {
        statusOutput.value += `\n\nError: ${data.error}`
        stopWatching()
        return
      }

      // Update progress
      let output = `Job ${statusJobId.value} - ${data.status}\n`
      output += `Progress: ${data.progress}%\n`
      if (data.text) {
        output += `\nOutput:\n${data.text}`
      }
      statusOutput.value = output

      // Auto-stop when finished
      if (data.finished) {
        setTimeout(() => {
          statusOutput.value += '\n\n[Watching stopped - job finished]'
          stopWatching()
        }, 1000)
      }
    } catch (error) {
      statusOutput.value += `\n\nError parsing SSE data: ${error.message}`
    }
  }

  eventSource.onerror = (error) => {
    statusOutput.value += '\n\n[Connection Error] SSE connection failed'
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
    if (isWatching.value) {
      statusOutput.value += '\n\n[Watching stopped by user]'
    }
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

  // Stop watching if currently watching
  stopWatching()

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}/log`)
    const logText = data.log_text || '(no log available)'
    statusOutput.value = `=== Job ${statusJobId.value} Log ===\n\n${logText}`
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

  // Stop watching if currently watching
  stopWatching()

  try {
    const data = await apiCall(`/api/jobs/${statusJobId.value}/resume`, 'POST')
    statusJobId.value = data.job_id
    jobStartOutput.value = {
      type: 'success',
      message: `✓ Job resumed (New ID: ${data.job_id})`
    }
  } catch (error) {
    jobStartOutput.value = {
      type: 'error',
      message: `✗ Error: ${error.message}`
    }
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

  // Stop watching if currently watching
  stopWatching()

  try {
    await apiCall(`/api/jobs/${statusJobId.value}/stop`, 'POST')
    statusOutput.value = `Job ${statusJobId.value} stopped`
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
    jobListOutput.value = `✓ Cleared ${data.count || 0} stopped job(s)`
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
