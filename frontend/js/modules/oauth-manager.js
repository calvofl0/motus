/**
 * OAuth Manager Module
 *
 * Handles OAuth token authorization and refresh for rclone remotes.
 */

export class OAuthManager {
    constructor(apiCall, modalManager, callbacks = {}) {
        this.apiCall = apiCall;
        this.modalManager = modalManager;

        // Callbacks
        this.onTokenRefreshed = callbacks.onTokenRefreshed || (() => {});

        // Internal state
        this.currentRemote = null;
    }

    /**
     * Refresh OAuth token for a remote
     * @param {string} remoteName - Name of the remote
     */
    async refreshToken(remoteName) {
        try {
            this.currentRemote = remoteName;

            // Call API to start OAuth refresh
            const response = await this.apiCall(`/api/remotes/${remoteName}/oauth/refresh`, 'POST');

            if (response.status === 'needs_token') {
                // Populate modal with authorize command
                document.getElementById('oauth-authorize-command').textContent = response.authorize_command;
                document.getElementById('oauth-token-input').value = '';
                document.getElementById('oauth-status-message').style.display = 'none';
                document.getElementById('oauth-submit-btn').disabled = false;

                // Open modal using ModalManager
                this.modalManager.open('oauth-interactive-modal', {
                    onEscape: () => this.closeModal(),
                    onEnter: () => this.submitToken(),
                    onClose: () => {
                        // Cleanup when modal closes
                        this.currentRemote = null;
                    }
                });
            } else if (response.status === 'complete') {
                // Token refresh completed immediately (shouldn't normally happen, but handle it)
                alert(`OAuth token successfully refreshed for "${remoteName}"`);
                await this.onTokenRefreshed();
                this.currentRemote = null;
            } else if (response.status === 'error') {
                // Error occurred
                alert(`Failed to refresh OAuth token: ${response.message || 'Unknown error'}`);
                this.currentRemote = null;
            } else {
                // Unexpected response
                alert(`Unexpected response from server: ${response.status}`);
                this.currentRemote = null;
            }
        } catch (error) {
            this.currentRemote = null;
            alert(`Failed to refresh OAuth token: ${error.message}`);
        }
    }

    /**
     * Submit OAuth token
     */
    async submitToken() {
        if (!this.currentRemote) {
            alert('No OAuth session active');
            return;
        }

        const token = document.getElementById('oauth-token-input').value.trim();
        if (!token) {
            this.showStatus('Please paste the token before submitting', 'error');
            return;
        }

        // Disable submit button during submission
        const submitBtn = document.getElementById('oauth-submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';

        try {
            this.showStatus('Submitting token...', 'info');

            // Submit token to API
            const response = await this.apiCall(
                `/api/remotes/${this.currentRemote}/oauth/submit-token`,
                'POST',
                { token: token }
            );

            if (response.status === 'complete') {
                // Success!
                this.showStatus('✓ Token successfully submitted! OAuth refresh complete.', 'success');

                // Wait a moment before closing
                setTimeout(async () => {
                    this.closeModal();
                    await this.onTokenRefreshed();
                    // Success - no alert needed, just close and refresh
                }, 1500);
            } else if (response.status === 'error') {
                // Error
                this.showStatus(`Error: ${response.message || 'Unknown error'}`, 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Token';
            } else {
                // Unexpected status
                this.showStatus(`Unexpected response: ${response.status}`, 'error');
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit Token';
            }
        } catch (error) {
            this.showStatus(`Failed to submit token: ${error.message}`, 'error');
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit Token';
        }
    }

    /**
     * Show status message
     * @param {string} message - Status message
     * @param {string} type - Message type ('success', 'error', 'info')
     */
    showStatus(message, type) {
        const statusDiv = document.getElementById('oauth-status-message');
        statusDiv.textContent = message;
        statusDiv.style.display = 'block';

        // Set background color based on type
        if (type === 'success') {
            statusDiv.style.background = '#d4edda';
            statusDiv.style.color = '#155724';
            statusDiv.style.border = '1px solid #c3e6cb';
        } else if (type === 'error') {
            statusDiv.style.background = '#f8d7da';
            statusDiv.style.color = '#721c24';
            statusDiv.style.border = '1px solid #f5c6cb';
        } else {
            // info
            statusDiv.style.background = '#d1ecf1';
            statusDiv.style.color = '#0c5460';
            statusDiv.style.border = '1px solid #bee5eb';
        }
    }

    /**
     * Copy authorize command to clipboard
     */
    async copyAuthorizeCommand() {
        const commandText = document.getElementById('oauth-authorize-command').textContent;

        try {
            await navigator.clipboard.writeText(commandText);

            // Show tooltip
            const tooltip = document.getElementById('oauth-copy-tooltip');
            tooltip.style.display = 'inline';

            // Hide after 1 second
            setTimeout(() => {
                tooltip.style.display = 'none';
            }, 1000);
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);

            // Fallback for older browsers or when clipboard API fails
            try {
                const textArea = document.createElement('textarea');
                textArea.value = commandText;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);

                // Show tooltip even with fallback
                const tooltip = document.getElementById('oauth-copy-tooltip');
                tooltip.style.display = 'inline';
                setTimeout(() => {
                    tooltip.style.display = 'none';
                }, 1000);
            } catch (err) {
                alert('Failed to copy to clipboard. Please copy manually.');
            }
        }
    }

    /**
     * Close OAuth modal
     */
    closeModal() {
        // Clean up modal UI
        document.getElementById('oauth-token-input').value = '';
        document.getElementById('oauth-status-message').style.display = 'none';
        document.getElementById('oauth-submit-btn').disabled = false;
        document.getElementById('oauth-submit-btn').textContent = 'Submit Token';

        // Close via ModalManager (will trigger onClose handler which sets currentRemote = null)
        this.modalManager.close('oauth-interactive-modal');
    }
}
