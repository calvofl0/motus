/**
 * Navigation Manager Module
 *
 * Handles navigation between remotes and paths in the file browser.
 *
 * Features:
 * - Load and populate remote dropdowns
 * - Handle remote selection changes
 * - Navigate to typed paths
 * - Path input keyboard handling
 */

export class NavigationManager {
    constructor(dependencies, callbacks = {}) {
        // Store dependencies
        this.apiCall = dependencies.apiCall;
        this.expandTildePath = dependencies.expandTildePath;

        // Store callbacks
        this.onRefreshPane = callbacks.onRefreshPane || (() => {});
    }

    /**
     * Initialize with state references
     */
    init(stateRefs) {
        this.leftPaneState = stateRefs.leftPaneState;
        this.rightPaneState = stateRefs.rightPaneState;
        this.isReverting = { value: false };  // Use object to share state
    }

    /**
     * Load remotes from backend and populate dropdown menus
     */
    async loadRemotes() {
        try {
            const data = await this.apiCall('/api/remotes');
            const leftSelect = document.getElementById('left-remote');
            const rightSelect = document.getElementById('right-remote');

            // Clear existing options except first
            leftSelect.innerHTML = '<option value="">Local Filesystem</option>';
            rightSelect.innerHTML = '<option value="">Local Filesystem</option>';

            data.remotes.forEach(remote => {
                leftSelect.innerHTML += `<option value="${remote.name}">${remote.name}</option>`;
                rightSelect.innerHTML += `<option value="${remote.name}">${remote.name}</option>`;
            });
        } catch (error) {
            console.error('Failed to load remotes:', error);
        }
    }

    /**
     * Handle remote dropdown change
     */
    async onRemoteChange(pane) {
        // Prevent recursion during revert
        if (this.isReverting.value) {
            this.isReverting.value = false;
            return;
        }

        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const select = document.getElementById(`${pane}-remote`);
        const pathInput = document.getElementById(`${pane}-path`);
        const oldRemote = state.remote;
        const oldPath = state.path;
        const newRemote = select.value;

        // When switching to Local Filesystem, go to home
        const newPath = (newRemote === '') ? '~/' : '/';

        state.remote = newRemote;
        state.path = newPath;
        pathInput.value = newPath;

        try {
            await this.onRefreshPane(pane);
        } catch (error) {
            // Revert to old remote and path on error
            this.isReverting.value = true;
            state.remote = oldRemote;
            state.path = oldPath;
            select.value = oldRemote;
            pathInput.value = oldPath;

            alert(`Failed to access remote: ${error.message}`);
        }
    }

    /**
     * Browse to the path typed in the input field
     */
    browsePath(pane) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        let path = document.getElementById(`${pane}-path`).value;
        // Expand tilde
        path = this.expandTildePath(path);
        state.path = path;
        document.getElementById(`${pane}-path`).value = path;
        this.onRefreshPane(pane);
    }

    /**
     * Handle keypress events in path input fields
     */
    handlePathKeypress(event, pane) {
        if (event.key === 'Enter') {
            event.preventDefault();
            this.browsePath(pane);
        }
    }
}
