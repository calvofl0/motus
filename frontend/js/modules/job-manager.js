/**
 * Job Manager Module
 *
 * Handles all job management functionality including:
 * - Active jobs tracking and display
 * - Interrupted jobs management
 * - Failed jobs management
 * - Job progress tracking and auto-refresh
 */

export class JobManager {
    constructor(apiCall, callbacks = {}) {
        this.apiCall = apiCall;

        // Callbacks
        this.onRefreshPane = callbacks.onRefreshPane || (() => {});

        // State
        this.jobsData = { jobs: [] };
        this.interruptedJobsData = { jobs: [] };
        this.failedJobsData = { jobs: [] };

        // Tracking
        this.trackedJobs = new Set();
        this.jobPanelManuallyToggled = false;
        this.previousJobState = 'empty';

        // Update intervals
        this.jobUpdateInterval = null;
        this.interruptedJobsInterval = null;
        this.failedJobsInterval = null;
    }

    /**
     * Initialize job management - start all update intervals
     */
    start() {
        this.startJobUpdates();
        this.startInterruptedJobsUpdates();
        this.startFailedJobsUpdates();
    }

    /**
     * Stop all job update intervals
     */
    stop() {
        if (this.jobUpdateInterval) {
            clearInterval(this.jobUpdateInterval);
            this.jobUpdateInterval = null;
        }
        if (this.interruptedJobsInterval) {
            clearInterval(this.interruptedJobsInterval);
            this.interruptedJobsInterval = null;
        }
        if (this.failedJobsInterval) {
            clearInterval(this.failedJobsInterval);
            this.failedJobsInterval = null;
        }
    }

    /**
     * Get count of currently running jobs
     */
    getRunningCount() {
        return this.jobsData.jobs ? this.jobsData.jobs.length : 0;
    }

    // ========== ACTIVE JOBS ==========

    /**
     * Toggle job panel collapse/expand
     */
    toggleJobPanel() {
        const panel = document.getElementById('job-panel');
        panel.classList.toggle('collapsed');
        // Mark that user manually toggled the panel
        this.jobPanelManuallyToggled = !panel.classList.contains('collapsed');
    }

    /**
     * Start periodic job updates
     */
    startJobUpdates() {
        this.updateJobs();
        this.jobUpdateInterval = setInterval(() => this.updateJobs(), 2000);
    }

    /**
     * Update active jobs list
     */
    async updateJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=running');
            const oldCount = this.jobsData.jobs.length;
            const previousJobs = new Set(this.jobsData.jobs.map(j => j.job_id));
            this.jobsData.jobs = data.jobs || [];
            const newCount = this.jobsData.jobs.length;
            const currentJobs = new Set(this.jobsData.jobs.map(j => j.job_id));

            // Detect completed jobs (were tracked, now not in running list)
            const completedJobs = [...this.trackedJobs].filter(id => !currentJobs.has(id));

            // Auto-refresh destination pane for completed jobs
            for (const jobId of completedJobs) {
                // Fetch job details to get destination path
                try {
                    const jobDetails = await this.apiCall(`/api/jobs/${jobId}`);
                    if (jobDetails && jobDetails.status === 'completed') {
                        // Call the callback to refresh appropriate panes
                        await this.onRefreshPane(jobDetails.dst_path);
                    }
                } catch (err) {
                    console.error(`Failed to auto-refresh after job ${jobId}:`, err);
                }
            }

            // Update tracked jobs
            this.trackedJobs = currentJobs;

            // State-based auto-expand/collapse: only change on state transitions
            const panel = document.getElementById('job-panel');
            const isCollapsed = panel.classList.contains('collapsed');
            const currentState = newCount === 0 ? 'empty' : 'non-empty';

            // Only auto-open/close on state transitions (empty ↔ non-empty)
            if (!this.jobPanelManuallyToggled) {
                // Transition from empty to non-empty: auto-open
                if (this.previousJobState === 'empty' && currentState === 'non-empty') {
                    panel.classList.remove('collapsed');
                }
                // Transition from non-empty to empty: auto-close
                else if (this.previousJobState === 'non-empty' && currentState === 'empty') {
                    panel.classList.add('collapsed');
                }
                // No state change: keep panel as is
            }

            this.previousJobState = currentState;
            this.renderJobs();
        } catch (error) {
            console.error('Failed to update jobs:', error);
        }
    }

    /**
     * Cancel a running job
     */
    async cancelJob(jobId) {
        try {
            await this.apiCall(`/api/jobs/${jobId}/stop`, 'POST');
            this.updateJobs();
        } catch (error) {
            alert(`Failed to cancel job: ${error.message}`);
        }
    }

    /**
     * Render active jobs list
     */
    renderJobs() {
        const container = document.getElementById('job-list');
        const count = document.getElementById('job-count');
        count.textContent = this.jobsData.jobs.length;

        if (this.jobsData.jobs.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: #999;">No active jobs</p>';
            return;
        }

        // Helper function to format time as "1h23min22s" or "10min5s" or "10s"
        // No unnecessary zeros
        function formatTime(seconds) {
            // Ensure we have a valid positive number
            if (!seconds || seconds < 0) return '0s';

            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = seconds % 60;

            if (hours > 0) {
                return `${hours}h${minutes}min${secs}s`;
            } else if (minutes > 0) {
                return `${minutes}min${secs}s`;
            } else {
                return `${secs}s`;
            }
        }

        // Helper function to parse transfer info from rclone text output
        // Text format: "Transferred (bytes):   123.45 MiB / 500 MiB, 25%, 10.5 MiB/s, ETA 35s"
        // or legacy: "Transferred:   123.45 MiB / 500 MiB, 25%, 10.5 MiB/s, ETA 35s"
        function parseTransferInfo(text) {
            if (!text) return null;

            // Look for "Transferred (bytes):" or "Transferred:" line with byte-based progress
            const transferMatch = text.match(/Transferred(?:\s+\(bytes\))?:\s+([0-9.]+)\s*([A-Za-z]+)\s*\/\s*([0-9.]+)\s*([A-Za-z]+).*?([0-9.]+)\s*([A-Za-z/]+)s.*?ETA\s+(.+?)$/m);
            if (transferMatch) {
                const transferred = transferMatch[1];
                const transferredUnit = transferMatch[2];
                const total = transferMatch[3];
                const totalUnit = transferMatch[4];
                const speed = transferMatch[5];
                const speedUnit = transferMatch[6];
                const eta = transferMatch[7].trim();

                return {
                    transferred: `${transferred} ${transferredUnit}`,
                    total: `${total} ${totalUnit}`,
                    speed: `${speed} ${speedUnit}/s`,
                    eta: eta
                };
            }

            return null;
        }

        container.innerHTML = this.jobsData.jobs.map(job => {
            // Calculate elapsed time with proper timestamp parsing
            let elapsedSec = 0;
            try {
                // SQLite CURRENT_TIMESTAMP returns UTC time as "YYYY-MM-DD HH:MM:SS"
                // We need to tell JavaScript it's UTC by adding 'Z' suffix
                const timestampStr = job.created_at;

                let createdAt;
                if (timestampStr.includes('T')) {
                    // Already ISO format, might have 'Z'
                    createdAt = new Date(timestampStr);
                } else {
                    // SQLite format: "YYYY-MM-DD HH:MM:SS" (UTC)
                    // Convert to ISO format and add 'Z' to indicate UTC
                    createdAt = new Date(timestampStr.replace(' ', 'T') + 'Z');
                }

                const now = new Date();

                // Validate the date is valid
                if (!isNaN(createdAt.getTime())) {
                    elapsedSec = Math.floor((now - createdAt) / 1000);
                    // Sanity check: if elapsed time is negative or absurdly large, use 0
                    if (elapsedSec < 0 || elapsedSec > 86400 * 365) {
                        console.warn(`Job ${job.job_id}: Invalid elapsed time ${elapsedSec}s from timestamp ${timestampStr}`);
                        elapsedSec = 0;
                    }
                } else {
                    console.error(`Job ${job.job_id}: Invalid timestamp ${timestampStr}`);
                }
            } catch (e) {
                console.error('Error parsing job timestamp:', job.created_at, e);
                elapsedSec = 0;
            }

            const elapsedStr = formatTime(elapsedSec);

            // Parse transfer information from job text
            const transferInfo = parseTransferInfo(job.text);
            const progress = job.progress || 0;

            // Build transfer status string
            let transferStatus = '';
            if (transferInfo) {
                // We have detailed transfer info from rclone
                transferStatus = `${transferInfo.eta} left - ${transferInfo.transferred} out of ${transferInfo.total} (${transferInfo.speed})`;
            } else {
                // Fallback: calculate ETA from progress or show progress percentage
                if (progress >= 100) {
                    transferStatus = 'Done';
                } else if (progress > 0) {
                    // Show calculated ETA if we have progress
                    if (elapsedSec > 1) {
                        const remainingPercent = 100 - progress;
                        const etaSec = Math.floor((elapsedSec / progress) * remainingPercent);
                        const etaStr = formatTime(etaSec);
                        transferStatus = `${etaStr} left (${progress}%)`;
                    } else {
                        transferStatus = `${progress}% - Starting...`;
                    }
                } else {
                    // No progress yet
                    transferStatus = 'Starting...';
                }
            }

            return `
                <div class="job-item ${job.status}">
                    <span class="job-id">Job #${job.job_id} - ${job.operation}</span>
                    <span class="job-path">${job.src_path} → ${job.dst_path} (${elapsedStr})</span>
                    <span class="job-time-info">${transferStatus}</span>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${progress}%">
                            ${progress}%
                        </div>
                    </div>
                    <span class="job-status">${job.status}</span>
                    <button class="job-icon-btn cancel" data-action="cancel-job" data-job-id="${job.job_id}" title="Cancel job">×</button>
                </div>
            `;
        }).join('');
    }

    // ========== INTERRUPTED JOBS ==========

    /**
     * Toggle interrupted jobs dropdown
     */
    toggleInterruptedJobsDropdown() {
        const list = document.getElementById('interrupted-jobs-list');
        list.classList.toggle('hidden');
    }

    /**
     * Start periodic interrupted jobs updates
     */
    startInterruptedJobsUpdates() {
        this.updateInterruptedJobs();
        this.interruptedJobsInterval = setInterval(() => this.updateInterruptedJobs(), 5000);
    }

    /**
     * Update interrupted jobs list
     */
    async updateInterruptedJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=interrupted');
            this.interruptedJobsData.jobs = data.jobs || [];
            this.renderInterruptedJobs();
        } catch (error) {
            console.error('Failed to update interrupted jobs:', error);
        }
    }

    /**
     * Render interrupted jobs dropdown
     */
    renderInterruptedJobs() {
        const dropdown = document.getElementById('interrupted-jobs-dropdown');
        const list = document.getElementById('interrupted-jobs-list');
        const count = document.getElementById('interrupted-count');

        if (this.interruptedJobsData.jobs.length === 0) {
            dropdown.classList.add('hidden');
            return;
        }

        dropdown.classList.remove('hidden');
        count.textContent = this.interruptedJobsData.jobs.length;

        list.innerHTML = this.interruptedJobsData.jobs.map(job => `
            <div class="interrupted-job-item">
                <div class="interrupted-job-info">
                    Job #${job.job_id}: ${job.src_path} → ${job.dst_path}
                </div>
                <div class="interrupted-job-actions">
                    <button class="job-icon-btn resume" data-action="resume-interrupted" data-job-id="${job.job_id}" title="Resume this job">▶</button>
                    <button class="job-icon-btn cancel" data-action="cancel-interrupted" data-job-id="${job.job_id}" title="Cancel this job">×</button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Cancel an interrupted job
     */
    async cancelInterruptedJob(jobId) {
        try {
            await this.apiCall(`/api/jobs/${jobId}/stop`, 'POST');
            this.updateInterruptedJobs();
        } catch (error) {
            alert(`Failed to cancel job: ${error.message}`);
        }
    }

    /**
     * Resume an interrupted job from dropdown
     */
    async resumeInterruptedJobFromDropdown(jobId) {
        try {
            const data = await this.apiCall(`/api/jobs/${jobId}/resume`, 'POST');
            this.updateInterruptedJobs();
            this.updateJobs();  // Refresh active jobs too
        } catch (error) {
            alert(`Failed to resume job: ${error.message}`);
        }
    }

    /**
     * Check for interrupted jobs at startup
     */
    async checkInterruptedJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=resumable');
            if (data.jobs && data.jobs.length > 0) {
                this.showInterruptedJobsModal(data.jobs);
            }
        } catch (error) {
            console.error('Failed to check interrupted jobs:', error);
        }
    }

    /**
     * Show interrupted jobs modal
     */
    showInterruptedJobsModal(jobs) {
        const list = document.getElementById('interrupted-jobs-list');
        list.innerHTML = jobs.map(job => `
            <div style="padding: 8px; background: #f8f9fa; margin: 5px 0; border-radius: 4px;">
                Job #${job.job_id}: ${job.src_path} → ${job.dst_path}
            </div>
        `).join('');
        document.getElementById('interrupted-jobs-modal').style.display = 'flex';
    }

    /**
     * Close interrupted jobs modal
     */
    closeInterruptedJobsModal() {
        document.getElementById('interrupted-jobs-modal').style.display = 'none';
    }

    /**
     * Resume all interrupted jobs
     */
    async resumeAllInterruptedJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=resumable');
            for (const job of data.jobs) {
                await this.apiCall(`/api/jobs/${job.job_id}/resume`, 'POST');
            }
            this.closeInterruptedJobsModal();
            this.updateInterruptedJobs();
            this.updateJobs();
        } catch (error) {
            alert(`Failed to resume jobs: ${error.message}`);
        }
    }

    // ========== FAILED JOBS ==========

    /**
     * Toggle failed jobs dropdown
     */
    toggleFailedJobsDropdown() {
        const list = document.getElementById('failed-jobs-list');
        list.classList.toggle('hidden');
    }

    /**
     * Start periodic failed jobs updates
     */
    startFailedJobsUpdates() {
        this.updateFailedJobs();
        this.failedJobsInterval = setInterval(() => this.updateFailedJobs(), 5000);
    }

    /**
     * Update failed jobs list
     */
    async updateFailedJobs() {
        try {
            const data = await this.apiCall('/api/jobs?status=failed');
            this.failedJobsData.jobs = data.jobs || [];
            this.renderFailedJobs();
        } catch (error) {
            console.error('Failed to update failed jobs:', error);
        }
    }

    /**
     * Render failed jobs dropdown
     */
    renderFailedJobs() {
        const dropdown = document.getElementById('failed-jobs-dropdown');
        const list = document.getElementById('failed-jobs-list');
        const count = document.getElementById('failed-count');

        if (this.failedJobsData.jobs.length === 0) {
            dropdown.classList.add('hidden');
            return;
        }

        dropdown.classList.remove('hidden');
        count.textContent = this.failedJobsData.jobs.length;

        list.innerHTML = this.failedJobsData.jobs.map(job => `
            <div class="failed-job-item">
                <div class="failed-job-info">
                    Job #${job.job_id}: ${job.src_path} → ${job.dst_path}
                    ${job.error_text ? '<br><span style="color: #dc3545; font-size: 11px;">' + job.error_text.substring(0, 100) + '...</span>' : ''}
                </div>
                <div class="failed-job-actions">
                    <button class="job-icon-btn resume" data-action="resume-failed" data-job-id="${job.job_id}" title="Resume this job">▶</button>
                    <button class="job-icon-btn cancel" data-action="cancel-failed" data-job-id="${job.job_id}" title="Cancel this job">×</button>
                </div>
            </div>
        `).join('');
    }

    /**
     * Cancel a failed job
     */
    async cancelFailedJob(jobId) {
        try {
            await this.apiCall(`/api/jobs/${jobId}/stop`, 'POST');
            this.updateFailedJobs();
        } catch (error) {
            alert(`Failed to cancel job: ${error.message}`);
        }
    }

    /**
     * Resume a failed job from dropdown
     */
    async resumeFailedJobFromDropdown(jobId) {
        try {
            const data = await this.apiCall(`/api/jobs/${jobId}/resume`, 'POST');
            this.updateFailedJobs();
            this.updateJobs();  // Refresh active jobs too
        } catch (error) {
            alert(`Failed to resume job: ${error.message}`);
        }
    }
}
