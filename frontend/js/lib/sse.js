/**
 * Server-Sent Events (SSE) Helper
 *
 * Provides utilities for establishing and managing SSE connections
 * for real-time job progress tracking.
 */

/**
 * SSE Connection Manager
 * Manages EventSource connections with automatic cleanup
 */
export class SSEConnection {
    constructor() {
        this.eventSource = null;
        this.onMessageCallback = null;
        this.onErrorCallback = null;
    }

    /**
     * Start SSE connection
     * @param {string} url - SSE endpoint URL
     * @param {Function} onMessage - Callback for message events
     * @param {Function} onError - Callback for error events
     */
    connect(url, onMessage, onError) {
        // Close any existing connection
        this.disconnect();

        this.onMessageCallback = onMessage;
        this.onErrorCallback = onError;

        // Create EventSource connection
        this.eventSource = new EventSource(url);

        this.eventSource.onmessage = (event) => {
            if (this.onMessageCallback) {
                this.onMessageCallback(event);
            }
        };

        this.eventSource.onerror = (error) => {
            console.error('SSE error:', error);
            if (this.onErrorCallback) {
                this.onErrorCallback(error);
            }
            this.disconnect();
        };
    }

    /**
     * Disconnect SSE connection
     */
    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    }

    /**
     * Check if connection is active
     * @returns {boolean} True if connected
     */
    isConnected() {
        return this.eventSource !== null;
    }
}

/**
 * Job Progress Watcher
 * Specialized SSE connection for watching job progress
 */
export class JobProgressWatcher {
    constructor() {
        this.connection = new SSEConnection();
        this.currentJobId = null;
    }

    /**
     * Start watching a job's progress
     * @param {string} jobId - Job ID to watch
     * @param {string} token - Authentication token
     * @param {Function} onUpdate - Callback(data) for progress updates
     * @param {Function} onError - Callback(error) for errors
     */
    watch(jobId, token, onUpdate, onError) {
        this.currentJobId = jobId;

        const baseUrl = window.location.origin;
        const sseUrl = `${baseUrl}/api/stream/jobs/${jobId}?token=${token}`;

        this.connection.connect(
            sseUrl,
            // onMessage handler
            (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.error) {
                        if (onError) {
                            onError(new Error(data.error));
                        }
                        this.stop();
                        return;
                    }

                    if (onUpdate) {
                        onUpdate(data);
                    }

                    // Auto-stop when job finishes
                    if (data.finished) {
                        setTimeout(() => this.stop(), 1000);
                    }
                } catch (error) {
                    console.error('Error parsing SSE data:', error);
                    if (onError) {
                        onError(error);
                    }
                }
            },
            // onError handler
            (error) => {
                if (onError) {
                    onError(error);
                }
            }
        );
    }

    /**
     * Stop watching job progress
     */
    stop() {
        this.connection.disconnect();
        this.currentJobId = null;
    }

    /**
     * Check if currently watching a job
     * @returns {boolean} True if watching
     */
    isWatching() {
        return this.connection.isConnected();
    }

    /**
     * Get currently watched job ID
     * @returns {string|null} Job ID or null
     */
    getCurrentJobId() {
        return this.currentJobId;
    }
}
