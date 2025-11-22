/**
 * UI Manager Module
 *
 * Handles UI state management including view modes, hidden files, and mode switching.
 *
 * Features:
 * - View menu (grid/list toggle, hidden files)
 * - Mode switching (easy/expert)
 * - Server shutdown
 * - Preferences integration
 */

export class UIManager {
    constructor(dependencies, callbacks = {}) {
        // Store dependencies
        this.apiCall = dependencies.apiCall;
        this.savePrefs = dependencies.savePrefs;
        this.jobManager = dependencies.jobManager;

        // Store callbacks
        this.onRenderFiles = callbacks.onRenderFiles || (() => {});
        this.onRefreshPane = callbacks.onRefreshPane || (() => {});
        this.onLoadRemotes = callbacks.onLoadRemotes || (() => {});

        // State references (set via init)
        this.state = null;
        this.viewMode = null;
        this.showHiddenFiles = null;
        this.currentMode = null;
    }

    /**
     * Initialize with state references
     */
    init(stateRefs) {
        this.state = stateRefs.state;
    }

    /**
     * Toggle view dropdown menu
     */
    toggleViewMenu(event) {
        event.stopPropagation();
        const dropdown = document.getElementById('view-dropdown');
        dropdown.classList.toggle('hidden');

        if (!dropdown.classList.contains('hidden')) {
            this.updateViewMenuItems();
        }
    }

    /**
     * Update view menu items based on current state
     */
    updateViewMenuItems() {
        // Update view mode text
        const viewModeText = document.getElementById('view-mode-text');
        viewModeText.textContent = this.state.ui.viewMode === 'grid' ? 'List View' : 'Grid View';

        // Update hidden files text
        const hiddenText = document.getElementById('hidden-files-text');
        hiddenText.textContent = this.state.ui.showHiddenFiles ? "Don't show hidden files" : "Show hidden files";
    }

    /**
     * Switch between grid and list view
     */
    switchViewMode() {
        this.state.ui.viewMode = this.state.ui.viewMode === 'grid' ? 'list' : 'grid';
        document.getElementById('view-dropdown').classList.add('hidden');

        // Save preference to backend
        this.savePrefs(this.apiCall, {
            view_mode: this.state.ui.viewMode,
            show_hidden_files: this.state.ui.showHiddenFiles
        });

        // Re-render both panes
        this.onRenderFiles('left');
        this.onRenderFiles('right');
    }

    /**
     * Toggle hidden files visibility
     */
    toggleHiddenFilesOption() {
        this.state.ui.showHiddenFiles = !this.state.ui.showHiddenFiles;
        document.getElementById('view-dropdown').classList.add('hidden');

        // Save preference to backend
        this.savePrefs(this.apiCall, {
            view_mode: this.state.ui.viewMode,
            show_hidden_files: this.state.ui.showHiddenFiles
        });

        // Re-render both panes
        this.onRenderFiles('left');
        this.onRenderFiles('right');
    }

    /**
     * Toggle between easy and expert mode
     */
    toggleMode() {
        this.setMode(this.state.currentMode === 'easy' ? 'expert' : 'easy');
    }

    /**
     * Set the current mode (easy or expert)
     */
    setMode(mode) {
        this.state.currentMode = mode;

        if (mode === 'easy') {
            document.getElementById('easy-mode').classList.remove('hidden');
            document.getElementById('expert-mode').classList.add('hidden');
            document.getElementById('mode-button-text').textContent = 'Expert Mode';

            if (this.jobManager.getRunningCount() === 0) {
                this.onLoadRemotes();
                this.onRefreshPane('left');
                this.onRefreshPane('right');
                this.jobManager.start();
            }
        } else {
            document.getElementById('easy-mode').classList.add('hidden');
            document.getElementById('expert-mode').classList.remove('hidden');
            document.getElementById('mode-button-text').textContent = 'Easy Mode';
            this.jobManager.stop();
        }
    }

    /**
     * Quit server with confirmation if jobs are running
     */
    async quitServer() {
        const runningCount = this.jobManager.getRunningCount();
        if (runningCount > 0) {
            const confirmed = confirm(
                `⚠️ Warning: ${runningCount} job(s) are currently running.\n\n` +
                `If you quit now, these jobs will be stopped and marked as interrupted.\n\n` +
                `Are you sure you want to quit?`
            );
            if (!confirmed) return;
        }

        try {
            const data = await this.apiCall('/api/shutdown', 'POST');

            // Replace page content with shutdown message
            document.body.innerHTML = `
                <div style="max-width:800px; margin:100px auto; text-align:center; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                    <h1 style="color:#28a745; margin-bottom:20px;">✓ Server Stopped Successfully</h1>
                    <p style="font-size:18px; color:#666; margin-bottom:30px;">
                        The Motus server has been shut down gracefully.
                    </p>
                    ${data.running_jobs_stopped > 0 ?
                        `<p style="color:#666; margin-bottom:20px;">
                            ${data.running_jobs_stopped} running job(s) were stopped and marked as interrupted.
                            You can resume them next time you start the server.
                        </p>` : ''}
                    <p style="color:#999; font-size:14px;">
                        You can close this window now.
                    </p>
                </div>
            `;
        } catch (error) {
            alert(`Failed to shutdown server: ${error.message}`);
        }
    }
}
