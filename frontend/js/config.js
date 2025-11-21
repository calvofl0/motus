/**
 * Global Application State
 *
 * Centralized state management for the entire application.
 * All modules import and modify this state object.
 */

/**
 * Application state object
 */
export const state = {
    // Current mode
    currentMode: 'easy',  // 'easy' or 'expert'

    // UI preferences
    ui: {
        viewMode: 'list',  // 'grid' or 'list'
        showHiddenFiles: false,
        lastFocusedPane: 'left'
    },

    // File browser panes
    panes: {
        left: {
            remote: '',
            path: '/',
            files: [],
            selectedIndexes: [],
            sortBy: 'name',  // 'name', 'size', 'date'
            sortAsc: true
        },
        right: {
            remote: '',
            path: '/',
            files: [],
            selectedIndexes: [],
            sortBy: 'name',
            sortAsc: true
        }
    },

    // Context menu state
    contextMenu: {
        pane: null,
        items: []
    },

    // Job management
    jobs: {
        active: {
            jobs: []
        },
        interrupted: {
            jobs: []
        },
        failed: {
            jobs: []
        },
        updateInterval: null,
        interruptedInterval: null,
        failedInterval: null,
        panelManuallyToggled: false,
        previousState: 'empty',  // 'empty' or 'non-empty'
        tracked: new Set()  // Track running jobs for completion detection
    },

    // Remote management modal state
    remoteManagement: {
        remotes: [],
        templates: [],
        selectedTemplate: null,
        formValues: {}
    },

    // OAuth management
    oauth: {
        currentRemote: null
    },

    // Upload state
    upload: {
        abortController: null,
        startTime: null,
        maxSize: 0  // 0 = unlimited
    },

    // Drag-drop operation
    dragDrop: {
        pending: null  // Pending drag-drop operation for confirmation
    },

    // Folder creation
    createFolder: {
        pane: null
    }
};

/**
 * Helper functions to access commonly used state
 */

/**
 * Get pane state by name
 * @param {string} pane - 'left' or 'right'
 * @returns {Object} Pane state object
 */
export function getPaneState(pane) {
    return state.panes[pane];
}

/**
 * Set pane path
 * @param {string} pane - 'left' or 'right'
 * @param {string} path - New path
 */
export function setPanePath(pane, path) {
    state.panes[pane].path = path;
}

/**
 * Set pane remote
 * @param {string} pane - 'left' or 'right'
 * @param {string} remote - Remote name
 */
export function setPaneRemote(pane, remote) {
    state.panes[pane].remote = remote;
}

/**
 * Set pane files
 * @param {string} pane - 'left' or 'right'
 * @param {Array} files - Array of file objects
 */
export function setPaneFiles(pane, files) {
    state.panes[pane].files = files;
}

/**
 * Clear pane selection
 * @param {string} pane - 'left' or 'right'
 */
export function clearPaneSelection(pane) {
    state.panes[pane].selectedIndexes = [];
}

/**
 * Toggle pane sort
 * @param {string} pane - 'left' or 'right'
 * @param {string} field - Sort field
 */
export function togglePaneSort(pane, field) {
    const paneState = state.panes[pane];
    if (paneState.sortBy === field) {
        paneState.sortAsc = !paneState.sortAsc;
    } else {
        paneState.sortBy = field;
        paneState.sortAsc = true;
    }
}
