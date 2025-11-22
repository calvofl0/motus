/**
 * Expert Mode Manager Module
 *
 * Handles all Expert Mode functionality - the API testing interface
 * for advanced users who want direct access to backend endpoints.
 */

import { JobProgressWatcher } from '../lib/sse.js';

export class ExpertModeManager {
    constructor(apiCall, setAuthToken, formatFileSize) {
        this.apiCall = apiCall;
        this.setAuthToken = setAuthToken;
        this.formatFileSize = formatFileSize;
        this.jobProgressWatcher = new JobProgressWatcher();
    }

    /**
     * Authenticate with token
     */
    async authenticate() {
        const authToken = document.getElementById('token').value;
        this.setAuthToken(authToken);
        document.cookie = `motus_token=${authToken}; path=/; max-age=31536000`;
        try {
            await this.apiCall('/api/health');
            document.getElementById('auth-status').innerHTML = '<div class="success">✓ Authenticated successfully</div>';
        } catch (error) {
            document.getElementById('auth-status').innerHTML = `<div class="error">✗ Authentication failed: ${error.message}</div>`;
        }
    }

    /**
     * List all remotes
     */
    async listRemotes() {
        try {
            const data = await this.apiCall('/api/remotes');
            document.getElementById('remotes-output').textContent =
                `Found ${data.count} remote(s):\n\n` + data.remotes.join('\n');
        } catch (error) {
            document.getElementById('remotes-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * List files in a path
     */
    async listFiles() {
        const path = document.getElementById('ls-path').value;
        try {
            const data = await this.apiCall('/api/files/ls', 'POST', { path });

            // Backend returns rclone's format: Name, Size, IsDir, ModTime
            const output = data.files.map(f => {
                const type = f.IsDir ? 'DIR ' : 'FILE';
                const size = f.IsDir ? '' : this.formatFileSize(f.Size);
                return `${type} ${f.Name.padEnd(40)} ${size}`;
            }).join('\n');

            document.getElementById('ls-output').textContent = output || 'Empty directory';
        } catch (error) {
            document.getElementById('ls-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * Create a directory
     */
    async makeDirectory() {
        const path = document.getElementById('mkdir-path').value;
        try {
            await this.apiCall('/api/files/mkdir', 'POST', { path });
            document.getElementById('mkdir-status').innerHTML = `<div class="success">✓ Directory created: ${path}</div>`;
        } catch (error) {
            document.getElementById('mkdir-status').innerHTML = `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Delete a path
     */
    async deletePath() {
        const path = document.getElementById('delete-path').value;
        if (!confirm(`Are you sure you want to delete: ${path}?`)) return;

        try {
            await this.apiCall('/api/files/delete', 'POST', { path });
            document.getElementById('delete-status').innerHTML = `<div class="success">✓ Deleted: ${path}</div>`;
        } catch (error) {
            document.getElementById('delete-status').innerHTML = `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Start a copy job
     */
    async startCopyJob() {
        const src = document.getElementById('job-src').value.trim();
        const dst = document.getElementById('job-dst').value.trim();

        if (!src || !dst) {
            alert('Please provide both source and destination paths');
            return;
        }

        const copyLinks = document.getElementById('copy-links').checked;

        try {
            const data = await this.apiCall('/api/jobs/copy', 'POST', {
                src_path: src,
                dst_path: dst,
                copy_links: copyLinks
            });
            document.getElementById('job-id').value = data.job_id;
            document.getElementById('job-start-status').innerHTML =
                `<div class="success">✓ Copy job started (ID: ${data.job_id})</div>`;
        } catch (error) {
            document.getElementById('job-start-status').innerHTML =
                `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Resume a job by ID
     */
    async resumeJobById() {
        const jobIdValue = document.getElementById('job-id').value.trim();
        const jobId = parseInt(jobIdValue);

        if (!jobId) {
            alert('Please enter a valid job ID');
            return;
        }

        try {
            const data = await this.apiCall(`/api/jobs/${jobId}/resume`, 'POST');
            document.getElementById('job-id').value = data.job_id;
            document.getElementById('job-start-status').innerHTML =
                `<div class="success">✓ Job resumed (New ID: ${data.job_id})</div>`;
        } catch (error) {
            document.getElementById('job-start-status').innerHTML =
                `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Start a move job
     */
    async startMoveJob() {
        const src = document.getElementById('job-src').value;
        const dst = document.getElementById('job-dst').value;

        try {
            const data = await this.apiCall('/api/jobs/move', 'POST', {
                src_path: src,
                dst_path: dst
            });
            document.getElementById('job-id').value = data.job_id;
            document.getElementById('job-start-status').innerHTML =
                `<div class="success">✓ Move job started (ID: ${data.job_id})</div>`;
        } catch (error) {
            document.getElementById('job-start-status').innerHTML =
                `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Start an integrity check job
     */
    async checkIntegrity() {
        const src = document.getElementById('job-src').value;
        const dst = document.getElementById('job-dst').value;

        try {
            const data = await this.apiCall('/api/jobs/check', 'POST', {
                src_path: src,
                dst_path: dst
            });
            document.getElementById('job-id').value = data.job_id;
            document.getElementById('job-start-status').innerHTML =
                `<div class="success">✓ Integrity check started (ID: ${data.job_id})</div>`;
        } catch (error) {
            document.getElementById('job-start-status').innerHTML =
                `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Start a sync job (destructive)
     */
    async syncJob() {
        const src = document.getElementById('job-src').value;
        const dst = document.getElementById('job-dst').value;

        if (!confirm(
            '⚠️ WARNING: Sync is a DESTRUCTIVE operation!\n\n' +
            'Files in the destination that don\'t exist in the source will be DELETED.\n\n' +
            'Are you sure you want to continue?'
        )) {
            return;
        }

        try {
            const data = await this.apiCall('/api/jobs/sync', 'POST', {
                src_path: src,
                dst_path: dst
            });
            document.getElementById('job-id').value = data.job_id;
            document.getElementById('job-start-status').innerHTML =
                `<div class="success">✓ Sync job started (ID: ${data.job_id})</div>`;
        } catch (error) {
            document.getElementById('job-start-status').innerHTML =
                `<div class="error">✗ Error: ${error.message}</div>`;
        }
    }

    /**
     * Get job status
     */
    async getJobStatus() {
        const jobId = document.getElementById('job-id').value;
        if (!jobId) {
            alert('Please enter a job ID');
            return;
        }

        try {
            const job = await this.apiCall(`/api/jobs/${jobId}`);
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
            `.trim();
            document.getElementById('job-status-output').textContent = output;
        } catch (error) {
            document.getElementById('job-status-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * Show job log
     */
    async showJobLog() {
        const jobId = document.getElementById('job-id').value;
        if (!jobId) {
            alert('Please enter a job ID');
            return;
        }

        try {
            const data = await this.apiCall(`/api/jobs/${jobId}/log`);
            const logText = data.log_text || '(no log available)';
            document.getElementById('job-status-output').textContent = `=== Job ${jobId} Log ===\n\n${logText}`;
        } catch (error) {
            document.getElementById('job-status-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * Watch job progress with SSE
     */
    watchJobProgress(getAuthToken) {
        const jobId = document.getElementById('job-id').value;
        if (!jobId) {
            alert('Please enter a job ID');
            return;
        }

        if (this.jobProgressWatcher.isWatching()) {
            alert('Already watching a job. Stop the current watch first.');
            return;
        }

        document.getElementById('job-status-output').textContent = `Watching job ${jobId}...\n`;

        this.jobProgressWatcher.watch(
            jobId,
            getAuthToken(),
            (data) => {
                // Update progress
                let output = `Job ${jobId} - ${data.status}\n`;
                output += `Progress: ${data.progress}%\n`;
                if (data.text) {
                    output += `\nOutput:\n${data.text}`;
                }
                document.getElementById('job-status-output').textContent = output;

                // Auto-stop when finished
                if (data.finished) {
                    setTimeout(() => {
                        document.getElementById('job-status-output').textContent += '\n\n[Watching stopped - job finished]';
                    }, 1000);
                }
            },
            (error) => {
                document.getElementById('job-status-output').textContent += `\n\nError: ${error.message}`;
            }
        );
    }

    /**
     * Stop watching job progress
     */
    stopWatchingJobProgress() {
        this.jobProgressWatcher.stop();
        document.getElementById('job-status-output').textContent += '\n\n[Watching stopped by user]';
    }

    /**
     * Handle ENTER key in job path fields
     */
    handleJobPathKeypress(event, field) {
        if (event.key === 'Enter') {
            event.preventDefault();
            const srcValue = document.getElementById('job-src').value.trim();
            const dstValue = document.getElementById('job-dst').value.trim();

            if (field === 'src') {
                // If in source field
                if (srcValue && !dstValue) {
                    // Move to destination field
                    document.getElementById('job-dst').focus();
                } else if (srcValue && dstValue) {
                    // Both filled, start copy
                    this.startCopyJob();
                }
            } else if (field === 'dst') {
                // If in destination field
                if (srcValue && dstValue) {
                    // Both filled, start copy
                    this.startCopyJob();
                }
            }
        }
    }

    /**
     * Stop a running job
     */
    async stopJob() {
        const jobId = document.getElementById('job-id').value;
        if (!jobId) {
            alert('Please enter a job ID');
            return;
        }

        try {
            await this.apiCall(`/api/jobs/${jobId}/stop`, 'POST');
            document.getElementById('job-status-output').textContent = `Job ${jobId} stopped`;
        } catch (error) {
            document.getElementById('job-status-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * List all jobs
     */
    async listAllJobs() {
        try {
            const data = await this.apiCall('/api/jobs');
            const output = data.jobs.map(j =>
                `#${j.job_id} ${j.operation} ${j.status} ${j.progress}% - ${j.src_path} → ${j.dst_path}`
            ).join('\n');
            document.getElementById('all-jobs-output').textContent = output || 'No jobs';
        } catch (error) {
            document.getElementById('all-jobs-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * List running jobs
     */
    async listRunningJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=running');
            const output = data.jobs.map(j =>
                `#${j.job_id} ${j.operation} ${j.progress}% - ${j.src_path} → ${j.dst_path}`
            ).join('\n');
            document.getElementById('all-jobs-output').textContent = output || 'No running jobs';
        } catch (error) {
            document.getElementById('all-jobs-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * List aborted jobs
     */
    async listAbortedJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=aborted');
            const output = data.jobs.map(j =>
                `#${j.job_id} ${j.operation} - ${j.src_path} → ${j.dst_path}`
            ).join('\n');
            document.getElementById('all-jobs-output').textContent = output || 'No aborted jobs';
        } catch (error) {
            document.getElementById('all-jobs-output').textContent = `Error: ${error.message}`;
        }
    }

    /**
     * Clear stopped jobs
     */
    async clearStoppedJobs() {
        if (!confirm('Clear all stopped jobs?')) return;

        try {
            const data = await this.apiCall('/api/jobs/clear_stopped', 'POST');
            document.getElementById('all-jobs-output').textContent =
                `✓ Cleared ${data.count} stopped job(s)`;
        } catch (error) {
            document.getElementById('all-jobs-output').textContent = `Error: ${error.message}`;
        }
    }
}
