import { ref } from 'vue'
import { useAppStore } from '../stores/app'
import { apiCall } from '../services/api'

export function useUpload() {
  const appStore = useAppStore()

  const showUploadModal = ref(false)
  const uploadMessage = ref('Preparing upload...')
  const uploadProgress = ref(0)
  const uploadDetails = ref('')
  const canCancelUpload = ref(true)

  let abortController = null
  let startTime = null
  let cleanupJobId = null

  /**
   * Format size in bytes to human-readable format
   */
  function formatSize(bytes) {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  /**
   * Update upload progress
   */
  function updateProgress(loaded, total) {
    const percent = Math.round((loaded / total) * 100)
    const elapsedSeconds = (Date.now() - startTime) / 1000
    const speedMBps = (loaded / 1024 / 1024) / elapsedSeconds

    uploadProgress.value = percent

    const loadedMB = (loaded / 1024 / 1024).toFixed(1)
    const totalMB = (total / 1024 / 1024).toFixed(1)
    uploadDetails.value = `${loadedMB} MB / ${totalMB} MB (${speedMBps.toFixed(1)} MB/s)`
  }

  /**
   * Cancel ongoing upload
   */
  function cancelUpload() {
    if (abortController) {
      abortController.abort()
      canCancelUpload.value = false
      uploadMessage.value = 'Canceling upload...'
    }
  }

  /**
   * Clean up upload cache
   */
  async function cleanupCache(jobId) {
    try {
      await fetch(`/api/upload/cleanup/${jobId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `token ${appStore.authToken}`
        }
      })
    } catch (error) {
      console.error('Cache cleanup failed:', error)
    }
  }

  /**
   * Monitor upload job and clean up cache when complete
   */
  async function monitorUploadJobForCleanup(copyJobId, uploadJobId) {
    const checkInterval = setInterval(async () => {
      try {
        const job = await apiCall(`/api/jobs/${copyJobId}`)

        if (job.status === 'completed' || job.status === 'failed') {
          clearInterval(checkInterval)
          await cleanupCache(uploadJobId)
          console.log(`Cleaned up cache for upload job ${uploadJobId}`)
        }
      } catch (error) {
        console.error('Error monitoring upload job:', error)
        clearInterval(checkInterval)
      }
    }, 5000)
  }

  /**
   * Upload files using XMLHttpRequest for progress tracking
   */
  function uploadWithProgress(formData) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest()

      // Track upload progress
      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          updateProgress(e.loaded, e.total)
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch (e) {
            reject(new Error('Invalid response from server'))
          }
        } else {
          // Try to parse error message from response
          let errorMsg = xhr.statusText
          try {
            const errorData = JSON.parse(xhr.responseText)
            if (errorData.error) {
              errorMsg = errorData.error
            }
          } catch (e) {
            // Keep default error message
          }
          reject(new Error('Upload failed: ' + errorMsg))
        }
      })

      xhr.addEventListener('error', () => {
        reject(new Error('Network error during upload'))
      })

      xhr.addEventListener('abort', () => {
        reject(new Error('Upload canceled'))
      })

      xhr.open('POST', '/api/upload')
      xhr.setRequestHeader('Authorization', `token ${appStore.authToken}`)

      // Wire up abort controller
      if (abortController) {
        abortController.signal.addEventListener('abort', () => {
          xhr.abort()
        })
      }

      xhr.send(formData)
    })
  }

  /**
   * Handle upload directly to local filesystem
   */
  async function handleDirectLocalUpload(files, targetPath, hasDirectories, onComplete) {
    // Show progress modal
    showUploadModal.value = true
    uploadMessage.value = `Uploading ${files.length} file${files.length !== 1 ? 's' : ''}...`
    uploadProgress.value = 0
    uploadDetails.value = ''
    canCancelUpload.value = true
    abortController = new AbortController()
    startTime = Date.now()

    try {
      const formData = new FormData()

      // Handle both formats: array of Files or array of {file, path} objects
      if (hasDirectories) {
        for (const item of files) {
          formData.append('files[]', item.file)
          formData.append('paths[]', item.path)
        }
      } else {
        for (const file of files) {
          formData.append('files[]', file)
        }
      }

      formData.append('job_id', 'direct-' + Date.now())
      formData.append('destination', targetPath)
      formData.append('direct_upload', 'true')
      formData.append('has_directories', hasDirectories ? 'true' : 'false')

      const uploadData = await uploadWithProgress(formData)

      // Update progress message
      uploadMessage.value = 'Upload complete!'
      canCancelUpload.value = false

      // Close progress modal after a short delay
      setTimeout(() => {
        showUploadModal.value = false
      }, 1000)

      // Notify completion
      if (onComplete) {
        await onComplete()
      }

    } catch (error) {
      console.error('Direct local upload failed:', error)
      showUploadModal.value = false
      alert(`Failed to upload files: ${error.message}`)
    } finally {
      abortController = null
      startTime = null
    }
  }

  /**
   * Handle upload to remote destination (via cache)
   */
  async function handleRemoteUpload(files, targetRemote, targetPath, hasDirectories, onComplete) {
    // Generate unique job ID
    const jobId = 'upload-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9)
    cleanupJobId = jobId

    // Show progress modal
    showUploadModal.value = true
    uploadMessage.value = `Uploading ${files.length} file${files.length !== 1 ? 's' : ''}...`
    uploadProgress.value = 0
    uploadDetails.value = ''
    canCancelUpload.value = true
    abortController = new AbortController()
    startTime = Date.now()

    try {
      // Step 1: Upload files to cache
      const formData = new FormData()

      if (hasDirectories) {
        for (const item of files) {
          formData.append('files[]', item.file)
          formData.append('paths[]', item.path)
        }
      } else {
        for (const file of files) {
          formData.append('files[]', file)
        }
      }

      formData.append('job_id', jobId)
      formData.append('has_directories', hasDirectories ? 'true' : 'false')

      const destPath = `${targetRemote}:${targetPath}`
      formData.append('destination', destPath)

      const uploadData = await uploadWithProgress(formData)

      // Update progress message
      uploadMessage.value = 'Upload complete! Starting transfer to destination...'
      canCancelUpload.value = false

      // Step 2: Copy from cache to destination
      const cachePath = uploadData.cache_path
      const dstPath = `${targetRemote}:${targetPath}/`

      const copyResult = await apiCall('/api/jobs/copy', 'POST', {
        src_path: cachePath + '/',
        dst_path: dstPath,
        copy_links: false
      })

      // Step 3: Schedule cache cleanup after job completes
      monitorUploadJobForCleanup(copyResult.job_id, jobId)

      // Close progress modal
      setTimeout(() => {
        showUploadModal.value = false
      }, 1000)

      // Notify completion
      if (onComplete) {
        await onComplete()
      }

      // Trigger job update event
      window.dispatchEvent(new CustomEvent('update-jobs'))

    } catch (error) {
      console.error('External file upload/copy failed:', error)
      showUploadModal.value = false
      alert(`Failed to upload files: ${error.message}`)

      // Clean up cache on error
      if (cleanupJobId) {
        await cleanupCache(cleanupJobId)
      }
    } finally {
      abortController = null
      startTime = null
      cleanupJobId = null
    }
  }

  /**
   * Handle external file upload (from OS drag-drop)
   */
  async function handleExternalFileUpload(files, targetRemote, targetPath, hasDirectories, onComplete) {
    const isLocalDestination = !targetRemote

    if (isLocalDestination) {
      await handleDirectLocalUpload(files, targetPath, hasDirectories, onComplete)
    } else {
      await handleRemoteUpload(files, targetRemote, targetPath, hasDirectories, onComplete)
    }
  }

  return {
    showUploadModal,
    uploadMessage,
    uploadProgress,
    uploadDetails,
    canCancelUpload,
    cancelUpload,
    handleExternalFileUpload
  }
}
