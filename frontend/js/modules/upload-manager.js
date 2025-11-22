/**
 * Upload Manager Module
 *
 * Handles file uploads from external sources (OS drag-drop) to both
 * local and remote destinations.
 */

export class UploadManager {
    constructor(apiCall, getAuthToken, callbacks = {}) {
        this.apiCall = apiCall;
        this.getAuthToken = getAuthToken;

        // Callbacks
        this.onUploadComplete = callbacks.onUploadComplete || (() => {});

        // Internal state
        this.abortController = null;
        this.startTime = null;
        this.maxUploadSize = 0;  // 0 = unlimited
    }

    /**
     * Set maximum upload size limit
     * @param {number} size - Maximum size in bytes (0 = unlimited)
     */
    setMaxUploadSize(size) {
        this.maxUploadSize = size;
    }

    /**
     * Format size in bytes to human-readable format
     * @param {number} bytes - Size in bytes
     * @returns {string} Formatted size
     */
    formatSize(bytes) {
        if (bytes === 0) return 'unlimited';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    /**
     * Check if upload size exceeds limit
     * @param {Array} files - Array of File objects or {file, path} objects
     * @returns {Object} {valid: boolean, totalSize: number, error: string}
     */
    checkUploadSizeLimit(files) {
        // Skip check if no limit configured (0 = unlimited)
        if (this.maxUploadSize === 0) {
            return { valid: true, totalSize: 0 };
        }

        // Calculate total size
        let totalSize = 0;
        for (const item of files) {
            // Handle both File objects and {file, path} objects
            const file = item.file || item;
            totalSize += file.size;
        }

        // Check if exceeds limit
        if (totalSize > this.maxUploadSize) {
            return {
                valid: false,
                totalSize,
                error: `Total upload size (${this.formatSize(totalSize)}) exceeds maximum allowed (${this.formatSize(this.maxUploadSize)})`
            };
        }

        return { valid: true, totalSize };
    }

    /**
     * Show upload progress modal
     * @param {number} fileCount - Number of files being uploaded
     */
    showProgressModal(fileCount) {
        // Reset progress
        this.abortController = new AbortController();
        this.startTime = Date.now();

        document.getElementById('upload-progress-message').textContent =
            `Uploading ${fileCount} file${fileCount !== 1 ? 's' : ''}...`;
        document.getElementById('upload-progress-bar').style.width = '0%';
        document.getElementById('upload-progress-percent').textContent = '0%';
        document.getElementById('upload-progress-details').textContent = '';
        document.getElementById('upload-cancel-btn').disabled = false;

        document.getElementById('upload-progress-modal').style.display = 'flex';
    }

    /**
     * Update upload progress
     * @param {number} loaded - Bytes loaded
     * @param {number} total - Total bytes
     */
    updateProgress(loaded, total) {
        const percent = Math.round((loaded / total) * 100);
        const elapsedSeconds = (Date.now() - this.startTime) / 1000;
        const speedMBps = (loaded / 1024 / 1024) / elapsedSeconds;

        document.getElementById('upload-progress-bar').style.width = percent + '%';
        document.getElementById('upload-progress-percent').textContent = percent + '%';

        const loadedMB = (loaded / 1024 / 1024).toFixed(1);
        const totalMB = (total / 1024 / 1024).toFixed(1);
        document.getElementById('upload-progress-details').textContent =
            `${loadedMB} MB / ${totalMB} MB (${speedMBps.toFixed(1)} MB/s)`;
    }

    /**
     * Close upload progress modal
     */
    closeProgressModal() {
        document.getElementById('upload-progress-modal').style.display = 'none';
        this.abortController = null;
        this.startTime = null;
    }

    /**
     * Cancel ongoing upload
     */
    cancelUpload() {
        if (this.abortController) {
            this.abortController.abort();
            document.getElementById('upload-cancel-btn').disabled = true;
            document.getElementById('upload-progress-message').textContent = 'Canceling upload...';
        }
    }

    /**
     * Handle upload of external files (from OS drag-drop)
     * @param {Array} externalFiles - Array of File objects or {file, path} objects
     * @param {Object} targetState - Target pane state {remote, path, ...}
     * @param {string} targetPane - Target pane name ('left' or 'right')
     * @param {boolean} hasDirectories - Whether files include directory structure
     */
    async handleExternalFileUpload(externalFiles, targetState, targetPane, hasDirectories) {
        console.log('Starting external file upload. Files:', externalFiles);
        console.log('Target state:', targetState);
        console.log('Number of files:', externalFiles.length);
        console.log('Has directories:', hasDirectories);

        // Check if destination is local (no remote) - if so, upload directly
        const isLocalDestination = !targetState.remote;

        if (isLocalDestination) {
            console.log('Uploading directly to local filesystem:', targetState.path);
            // Direct upload to local filesystem (no cache needed)
            await this.handleDirectLocalUpload(externalFiles, targetState, targetPane, hasDirectories);
            return;
        }

        // Remote destination - use cache approach
        console.log('Uploading to remote via cache:', targetState.remote);
        await this.handleRemoteUpload(externalFiles, targetState, targetPane, hasDirectories);
    }

    /**
     * Handle upload to remote destination (via cache)
     * @param {Array} externalFiles - Files to upload
     * @param {Object} targetState - Target pane state
     * @param {string} targetPane - Target pane name
     * @param {boolean} hasDirectories - Whether files include directories
     */
    async handleRemoteUpload(externalFiles, targetState, targetPane, hasDirectories) {
        // Generate unique job ID
        const jobId = 'upload-' + Date.now() + '-' + Math.random().toString(36).substr(2, 9);
        console.log('Generated job ID:', jobId);

        // Show progress modal
        this.showProgressModal(externalFiles.length);

        try {
            // Step 1: Upload files to cache
            const formData = new FormData();

            // Handle both formats: array of Files or array of {file, path} objects
            if (hasDirectories) {
                // filesWithPaths format: [{file: File, path: "folder/file.txt"}, ...]
                for (const item of externalFiles) {
                    formData.append('files[]', item.file);
                    formData.append('paths[]', item.path);  // Relative path including folders
                }
            } else {
                // Simple File array format
                for (const file of externalFiles) {
                    formData.append('files[]', file);
                }
            }

            formData.append('job_id', jobId);
            formData.append('has_directories', hasDirectories ? 'true' : 'false');

            // Destination path
            const destPath = `${targetState.remote}:${targetState.path}`;
            formData.append('destination', destPath);

            // Upload files with progress tracking using XMLHttpRequest
            const uploadData = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();

                // Track upload progress
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        this.updateProgress(e.loaded, e.total);
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            resolve(JSON.parse(xhr.responseText));
                        } catch (e) {
                            reject(new Error('Invalid response from server'));
                        }
                    } else {
                        // Try to parse error message from response
                        let errorMsg = xhr.statusText;
                        try {
                            const errorData = JSON.parse(xhr.responseText);
                            if (errorData.error) {
                                errorMsg = errorData.error;
                            }
                        } catch (e) {
                            // Keep default error message
                        }
                        reject(new Error('Upload failed: ' + errorMsg));
                    }
                });

                xhr.addEventListener('error', () => {
                    reject(new Error('Network error during upload'));
                });

                xhr.addEventListener('abort', () => {
                    reject(new Error('Upload canceled'));
                });

                xhr.open('POST', '/api/upload');
                const authToken = this.getAuthToken();
                console.log('Upload auth token:', authToken ? 'present' : 'MISSING');
                xhr.setRequestHeader('Authorization', `token ${authToken}`);

                // Wire up abort controller
                if (this.abortController) {
                    this.abortController.signal.addEventListener('abort', () => {
                        xhr.abort();
                    });
                }

                xhr.send(formData);
            });

            console.log('Files uploaded to cache:', uploadData);

            // Update progress message
            document.getElementById('upload-progress-message').textContent = 'Upload complete! Starting transfer to destination...';
            document.getElementById('upload-cancel-btn').disabled = true;

            // Step 2: Copy from cache to destination
            const cachePath = uploadData.cache_path;
            const dstPath = `${targetState.remote}:${targetState.path}/`;

            const copyResult = await this.apiCall('/api/jobs/copy', 'POST', {
                src_path: cachePath + '/',  // Copy all files from cache directory
                dst_path: dstPath,
                copy_links: false
            });

            console.log('Copy job started:', copyResult);

            // Step 3: Schedule cache cleanup after job completes
            // This will be monitored by watching the job status
            this.monitorUploadJobForCleanup(copyResult.job_id, jobId);

            // Close progress modal
            setTimeout(() => {
                this.closeProgressModal();
            }, 1000);  // Keep modal visible for 1 second to show completion

            // Notify completion
            await this.onUploadComplete(targetPane);

        } catch (error) {
            console.error('External file upload/copy failed:', error);
            this.closeProgressModal();
            alert(`Failed to upload files: ${error.message}`);

            // Clean up cache on error
            try {
                await fetch(`/api/upload/cleanup/${jobId}`, {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `token ${this.getAuthToken()}`
                    }
                });
            } catch (cleanupError) {
                console.error('Cache cleanup failed:', cleanupError);
            }
        }
    }

    /**
     * Handle upload directly to local filesystem
     * @param {Array} files - Files to upload
     * @param {Object} targetState - Target pane state
     * @param {string} targetPane - Target pane name
     * @param {boolean} hasDirectories - Whether files include directories
     */
    async handleDirectLocalUpload(files, targetState, targetPane, hasDirectories) {
        // Upload directly to local filesystem
        console.log('handleDirectLocalUpload called with', files.length, 'files');
        console.log('Destination:', targetState.path);
        console.log('Has directories:', hasDirectories);

        // Show progress modal
        this.showProgressModal(files.length);

        try {
            const formData = new FormData();

            // Handle both formats: array of Files or array of {file, path} objects
            if (hasDirectories) {
                // filesWithPaths format: [{file: File, path: "folder/file.txt"}, ...]
                for (const item of files) {
                    console.log('Adding file to FormData:', item.path, 'size:', item.file.size);
                    formData.append('files[]', item.file);
                    formData.append('paths[]', item.path);  // Relative path including folders
                }
            } else {
                // Simple File array format
                for (const file of files) {
                    console.log('Adding file to FormData:', file.name, 'size:', file.size);
                    formData.append('files[]', file);
                }
            }

            // Use a placeholder job_id (not actually used for direct upload)
            formData.append('job_id', 'direct-' + Date.now());
            formData.append('destination', targetState.path);
            formData.append('direct_upload', 'true');  // Flag for direct upload
            formData.append('has_directories', hasDirectories ? 'true' : 'false');

            console.log('Sending upload request...');

            // Upload with progress tracking using XMLHttpRequest
            const uploadData = await new Promise((resolve, reject) => {
                const xhr = new XMLHttpRequest();

                // Track upload progress
                xhr.upload.addEventListener('progress', (e) => {
                    if (e.lengthComputable) {
                        this.updateProgress(e.loaded, e.total);
                    }
                });

                xhr.addEventListener('load', () => {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            resolve(JSON.parse(xhr.responseText));
                        } catch (e) {
                            reject(new Error('Invalid response from server'));
                        }
                    } else {
                        // Try to parse error message from response
                        let errorMsg = xhr.statusText;
                        try {
                            const errorData = JSON.parse(xhr.responseText);
                            if (errorData.error) {
                                errorMsg = errorData.error;
                            }
                        } catch (e) {
                            // Keep default error message
                        }
                        reject(new Error('Upload failed: ' + errorMsg));
                    }
                });

                xhr.addEventListener('error', () => {
                    reject(new Error('Network error during upload'));
                });

                xhr.addEventListener('abort', () => {
                    reject(new Error('Upload canceled'));
                });

                xhr.open('POST', '/api/upload');
                const authToken = this.getAuthToken();
                console.log('Upload auth token:', authToken ? 'present' : 'MISSING');
                xhr.setRequestHeader('Authorization', `token ${authToken}`);

                // Wire up abort controller
                if (this.abortController) {
                    this.abortController.signal.addEventListener('abort', () => {
                        xhr.abort();
                    });
                }

                xhr.send(formData);
            });

            console.log('Files uploaded directly to local filesystem:', uploadData);

            // Update progress message
            document.getElementById('upload-progress-message').textContent = 'Upload complete!';
            document.getElementById('upload-cancel-btn').disabled = true;

            // Close progress modal after a short delay
            setTimeout(() => {
                this.closeProgressModal();
            }, 1000);

            // Notify completion
            await this.onUploadComplete(targetPane);

        } catch (error) {
            console.error('Direct local upload failed:', error);
            this.closeProgressModal();
            alert(`Failed to upload files: ${error.message}`);
        }
    }

    /**
     * Monitor upload job and clean up cache when complete
     * @param {string} copyJobId - Copy job ID
     * @param {string} uploadJobId - Upload job ID (for cache cleanup)
     */
    async monitorUploadJobForCleanup(copyJobId, uploadJobId) {
        // Poll job status until completion
        const checkInterval = setInterval(async () => {
            try {
                const job = await this.apiCall(`/api/jobs/${copyJobId}`);

                if (job.status === 'completed' || job.status === 'failed') {
                    clearInterval(checkInterval);

                    // Clean up cache
                    await fetch(`/api/upload/cleanup/${uploadJobId}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `token ${this.getAuthToken()}`
                        }
                    });

                    console.log(`Cleaned up cache for upload job ${uploadJobId}`);
                }
            } catch (error) {
                console.error('Error monitoring upload job:', error);
                clearInterval(checkInterval);
            }
        }, 5000);  // Check every 5 seconds
    }
}
