/**
 * Main Application Entry Point
 *
 * Initializes all modules and sets up event listeners for the Motus file manager.
 */

import { ModalManager, initModalManager } from '/js/lib/modal-manager.js';
import { state } from '/js/config.js';
import { apiCall, setAuthToken, getAuthToken } from '/js/lib/api.js';
import { buildPath, sortFiles, formatFileSize, formatFileDate, expandTildePath, resolveRelativePath } from '/js/utils/helpers.js';
import { savePreferences as savePrefs, loadPreferences as loadPrefs } from '/js/utils/preferences.js';
import { RemoteManager } from '/js/modules/remote-manager.js';
import { OAuthManager } from '/js/modules/oauth-manager.js';
import { UploadManager } from '/js/modules/upload-manager.js';
import { ExpertModeManager } from '/js/modules/expert-mode.js';
import { JobManager } from '/js/modules/job-manager.js';
import { FileBrowser } from '/js/modules/file-browser.js';
import { FileOperations } from '/js/modules/file-operations.js';
import { UIManager } from '/js/modules/ui-manager.js';
import { NavigationManager } from '/js/modules/navigation-manager.js';

// Make ModalManager available globally for compatibility
window.ModalManager = ModalManager;

// State aliases
let currentMode = state.currentMode;
let authToken = '';
let leftPaneState = state.panes.left;
let rightPaneState = state.panes.right;
let viewMode = state.ui.viewMode;
let showHiddenFiles = state.ui.showHiddenFiles;
let lastFocusedPane = state.ui.lastFocusedPane;
let contextMenuState = state.contextMenu;
let createFolderPane = state.createFolder.pane;
let pendingDragDrop = state.dragDrop.pending;
let maxUploadSize = state.upload.maxSize;

// Module instances (will be initialized in init())
let uploadManager;
let oauthManager;
let remoteManager;
let expertModeManager;
let jobManager;
let navigationManager;
let uiManager;
let fileOperations;
let fileBrowser;

/**
 * Initialize all modules
 */
function initializeModules() {
    uploadManager = new UploadManager(apiCall, getAuthToken, {
        onUploadComplete: async (pane) => {
            await fileBrowser.refreshPane(pane);
            await jobManager.updateJobs();
        }
    });

    oauthManager = new OAuthManager(apiCall, ModalManager, {
        onTokenRefreshed: async () => {
            await navigationManager.loadRemotes();
            await fileBrowser.refreshPane('left');
            await fileBrowser.refreshPane('right');
        }
    });

    remoteManager = new RemoteManager(apiCall, ModalManager, {
        onRemotesChanged: async () => {
            await navigationManager.loadRemotes();
            await fileBrowser.refreshPane('left');
            await fileBrowser.refreshPane('right');
        },
        getActivePanes: () => ({
            left: leftPaneState.remote,
            right: rightPaneState.remote
        }),
        onOAuthRefresh: (remoteName) => oauthManager.refreshToken(remoteName)
    });

    expertModeManager = new ExpertModeManager(apiCall, setAuthToken, formatFileSize);

    jobManager = new JobManager(apiCall, {
        onRefreshPane: async (dstPath) => {
            // Determine which pane to refresh based on destination
            let refreshLeft = false;
            let refreshRight = false;

            if (dstPath.includes(':')) {
                // Remote path
                const [remote, path] = dstPath.split(':', 2);
                if (leftPaneState.remote === remote && path.startsWith(leftPaneState.path)) {
                    refreshLeft = true;
                }
                if (rightPaneState.remote === remote && path.startsWith(rightPaneState.path)) {
                    refreshRight = true;
                }
            } else {
                // Local path
                if (!leftPaneState.remote && dstPath.startsWith(leftPaneState.path)) {
                    refreshLeft = true;
                }
                if (!rightPaneState.remote && dstPath.startsWith(rightPaneState.path)) {
                    refreshRight = true;
                }
            }

            // Refresh destination pane(s) with selection preservation
            if (refreshLeft) {
                await fileBrowser.refreshPane('left', true);
            }
            if (refreshRight) {
                await fileBrowser.refreshPane('right', true);
            }
        }
    });

    navigationManager = new NavigationManager({
        apiCall,
        expandTildePath
    }, {
        onRefreshPane: (pane) => fileBrowser.refreshPane(pane)
    });

    uiManager = new UIManager({
        apiCall,
        savePrefs,
        jobManager
    }, {
        onRenderFiles: (pane) => fileBrowser.renderFiles(pane),
        onRefreshPane: (pane) => fileBrowser.refreshPane(pane),
        onLoadRemotes: async () => await navigationManager.loadRemotes()
    });

    fileOperations = new FileOperations({
        apiCall,
        buildPath,
        expandTildePath,
        resolveRelativePath,
        ModalManager
    }, {
        onRefreshPane: (pane, preserveSelection = false) => fileBrowser.refreshPane(pane, preserveSelection),
        onRenderFiles: (pane) => fileBrowser.renderFiles(pane),
        onShowDragDropConfirm: (operation) => {
            pendingDragDrop = operation;
            showDragDropConfirmModal(operation.fileNames, operation.sourcePath, operation.destPath);
        }
    });

    fileBrowser = new FileBrowser({
        apiCall,
        formatFileSize,
        formatFileDate,
        expandTildePath,
        buildPath,
        sortFiles,
        uploadManager,
        jobManager
    }, {
        onArrowButtonsUpdate: () => fileOperations.updateArrowButtons(),
        onContextMenuShow: (event, pane) => fileOperations.showContextMenu(event, pane, { value: lastFocusedPane }),
        onDragDropConfirm: (operation) => {
            pendingDragDrop = operation;
            showDragDropConfirmModal(operation.fileNames, operation.sourcePath, operation.destPath);
        }
    });

    // Initialize modules with state references
    fileOperations.init({
        leftPaneState,
        rightPaneState,
        contextMenuState,
        createFolderPane: { value: createFolderPane }
    });

    fileBrowser.init({
        state,
        leftPaneState,
        rightPaneState
    });

    uiManager.init({ state });

    navigationManager.init({
        leftPaneState,
        rightPaneState
    });
}

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    // Header buttons
    document.getElementById('manage-remotes-btn').addEventListener('click', () => remoteManager.open());
    document.getElementById('view-menu-btn').addEventListener('click', (e) => uiManager.toggleViewMenu(e));
    document.getElementById('view-mode-option').addEventListener('click', () => uiManager.switchViewMode());
    document.getElementById('hidden-files-option').addEventListener('click', () => uiManager.toggleHiddenFilesOption());
    document.getElementById('mode-toggle-btn').addEventListener('click', () => uiManager.toggleMode());
    document.getElementById('quit-btn').addEventListener('click', () => uiManager.quitServer());

    // Left pane controls
    document.getElementById('left-remote').addEventListener('change', () => navigationManager.onRemoteChange('left'));
    document.getElementById('left-path').addEventListener('keypress', (e) => navigationManager.handlePathKeypress(e, 'left'));
    document.getElementById('left-refresh-btn').addEventListener('click', () => fileBrowser.refreshPane('left', true));
    document.getElementById('left-refresh-btn').addEventListener('mouseover', function() {
        this.style.transform = 'scale(1.2)';
    });
    document.getElementById('left-refresh-btn').addEventListener('mouseout', function() {
        this.style.transform = 'scale(1)';
    });

    // Right pane controls
    document.getElementById('right-remote').addEventListener('change', () => navigationManager.onRemoteChange('right'));
    document.getElementById('right-path').addEventListener('keypress', (e) => navigationManager.handlePathKeypress(e, 'right'));
    document.getElementById('right-refresh-btn').addEventListener('click', () => fileBrowser.refreshPane('right', true));
    document.getElementById('right-refresh-btn').addEventListener('mouseover', function() {
        this.style.transform = 'scale(1.2)';
    });
    document.getElementById('right-refresh-btn').addEventListener('mouseout', function() {
        this.style.transform = 'scale(1)';
    });

    // Arrow buttons
    document.getElementById('copy-right-btn').addEventListener('click', () => fileOperations.copySelectedToRight());
    document.getElementById('copy-left-btn').addEventListener('click', () => fileOperations.copySelectedToLeft());

    // Drag-and-drop for file grids
    const leftFiles = document.getElementById('left-files');
    const rightFiles = document.getElementById('right-files');

    leftFiles.addEventListener('dragover', (e) => fileBrowser.handleDragOver(e, 'left'));
    leftFiles.addEventListener('drop', (e) => fileBrowser.handleDrop(e, 'left'));
    leftFiles.addEventListener('dragleave', (e) => fileBrowser.handleDragLeave(e, 'left'));

    rightFiles.addEventListener('dragover', (e) => fileBrowser.handleDragOver(e, 'right'));
    rightFiles.addEventListener('drop', (e) => fileBrowser.handleDrop(e, 'right'));
    rightFiles.addEventListener('dragleave', (e) => fileBrowser.handleDragLeave(e, 'right'));

    // Job panel toggles
    document.getElementById('job-panel-header').addEventListener('click', () => jobManager.toggleJobPanel());
    document.getElementById('interrupted-jobs-header').addEventListener('click', () => jobManager.toggleInterruptedJobsDropdown());
    document.getElementById('failed-jobs-header').addEventListener('click', () => jobManager.toggleFailedJobsDropdown());

    // Modal buttons - Interrupted Jobs Modal
    document.getElementById('interrupted-jobs-skip-btn').addEventListener('click', () => jobManager.closeInterruptedJobsModal());
    document.getElementById('interrupted-jobs-resume-all-btn').addEventListener('click', () => jobManager.resumeAllInterruptedJobs());

    // Modal buttons - Rename Modal
    document.getElementById('rename-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') fileOperations.confirmRename();
    });
    document.getElementById('rename-cancel-btn').addEventListener('click', () => fileOperations.closeRenameModal());
    document.getElementById('rename-confirm-btn').addEventListener('click', () => fileOperations.confirmRename());

    // Modal buttons - Create Folder Modal
    document.getElementById('create-folder-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') fileOperations.confirmCreateFolder();
    });
    document.getElementById('create-folder-cancel-btn').addEventListener('click', () => fileOperations.closeCreateFolderModal());
    document.getElementById('create-folder-confirm-btn').addEventListener('click', () => fileOperations.confirmCreateFolder());

    // Modal buttons - Delete Confirm Modal
    document.getElementById('delete-cancel-btn').addEventListener('click', () => fileOperations.closeDeleteConfirmModal());
    document.getElementById('delete-confirm-btn').addEventListener('click', () => fileOperations.confirmDelete());

    // Modal buttons - Drag Drop Confirm Modal
    document.getElementById('drag-drop-cancel-btn').addEventListener('click', closeDragDropConfirmModal);
    document.getElementById('drag-drop-confirm-btn').addEventListener('click', confirmDragDrop);

    // Modal buttons - Upload Progress Modal
    document.getElementById('upload-cancel-btn').addEventListener('click', () => uploadManager.cancelUpload());

    // Modal buttons - Manage Remotes Modal
    document.getElementById('manage-remotes-close-btn').addEventListener('click', () => remoteManager.close());
    document.getElementById('add-remote-btn').addEventListener('click', () => remoteManager.showTemplateSelection());
    document.getElementById('template-close-btn').addEventListener('click', () => remoteManager.showRemotesList());
    document.getElementById('template-next-btn').addEventListener('click', () => remoteManager.showRemoteForm());
    document.getElementById('configure-close-btn').addEventListener('click', () => remoteManager.showRemotesList());
    document.getElementById('configure-back-btn').addEventListener('click', () => remoteManager.showTemplateSelection());
    document.getElementById('create-remote-btn').addEventListener('click', () => remoteManager.createRemote());

    // Modal buttons - OAuth Interactive Modal
    document.getElementById('oauth-copy-btn').addEventListener('click', () => oauthManager.copyAuthorizeCommand());
    document.getElementById('oauth-cancel-btn').addEventListener('click', () => oauthManager.closeModal());
    document.getElementById('oauth-submit-btn').addEventListener('click', () => oauthManager.submitToken());

    // Event delegation - Template selection
    document.getElementById('templates-list-container').addEventListener('click', (e) => {
        const templateItem = e.target.closest('.template-item');
        if (templateItem) {
            const templateName = templateItem.dataset.templateName;
            remoteManager.selectTemplate(templateName);
        }
    });

    // Event delegation - Remote list actions
    document.getElementById('remotes-list-container').addEventListener('click', (e) => {
        const actionBtn = e.target.closest('.remote-action-btn');
        if (actionBtn) {
            e.stopPropagation();
            const action = actionBtn.dataset.action;
            const remoteName = actionBtn.dataset.remoteName;

            if (action === 'refresh-oauth') {
                oauthManager.refreshToken(remoteName);
            } else if (action === 'edit') {
                remoteManager.editRemoteConfig(remoteName);
            } else if (action === 'delete') {
                remoteManager.deleteRemote(remoteName);
            }
            return;
        }

        const remoteRow = e.target.closest('.remote-row');
        if (remoteRow) {
            const remoteName = remoteRow.dataset.remoteName;
            remoteManager.viewRemoteConfig(remoteName);
        }
    });

    // Event delegation - Remote row hover effects
    document.getElementById('remotes-list-container').addEventListener('mouseover', (e) => {
        const remoteRow = e.target.closest('.remote-row');
        if (remoteRow) {
            remoteRow.style.backgroundColor = '#f0f8ff';
        }
    });
    document.getElementById('remotes-list-container').addEventListener('mouseout', (e) => {
        const remoteRow = e.target.closest('.remote-row');
        if (remoteRow) {
            remoteRow.style.backgroundColor = 'white';
        }
    });

    // Modal buttons - View Remote Config Modal
    document.getElementById('view-remote-close-btn').addEventListener('click', () => remoteManager.closeViewRemoteConfigModal());
    document.getElementById('copy-remote-config-btn').addEventListener('click', () => remoteManager.copyRemoteConfigToClipboard());

    // Modal buttons - Edit Remote Config Modal
    document.getElementById('edit-remote-cancel-btn').addEventListener('click', () => remoteManager.closeEditRemoteConfigModal());
    document.getElementById('edit-remote-save-btn').addEventListener('click', () => remoteManager.saveRemoteConfig());

    // Expert Mode buttons
    document.getElementById('expert-auth-btn').addEventListener('click', () => expertModeManager.authenticate());
    document.getElementById('expert-list-remotes-btn').addEventListener('click', () => expertModeManager.listRemotes());
    document.getElementById('ls-path').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') expertModeManager.listFiles();
    });
    document.getElementById('expert-list-files-btn').addEventListener('click', () => expertModeManager.listFiles());
    document.getElementById('mkdir-path').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') expertModeManager.makeDirectory();
    });
    document.getElementById('expert-mkdir-btn').addEventListener('click', () => expertModeManager.makeDirectory());
    document.getElementById('delete-path').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') expertModeManager.deletePath();
    });
    document.getElementById('expert-delete-btn').addEventListener('click', () => expertModeManager.deletePath());

    // Expert Mode - Job Management
    document.getElementById('job-src').addEventListener('keypress', (e) => expertModeManager.handleJobPathKeypress(e, 'src'));
    document.getElementById('job-dst').addEventListener('keypress', (e) => expertModeManager.handleJobPathKeypress(e, 'dst'));
    document.getElementById('expert-copy-btn').addEventListener('click', () => expertModeManager.startCopyJob());
    document.getElementById('expert-move-btn').addEventListener('click', () => expertModeManager.startMoveJob());
    document.getElementById('expert-integrity-btn').addEventListener('click', () => expertModeManager.checkIntegrity());
    document.getElementById('expert-sync-btn').addEventListener('click', () => expertModeManager.syncJob());
    document.getElementById('job-id').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') expertModeManager.getJobStatus();
    });
    document.getElementById('expert-job-status-btn').addEventListener('click', () => expertModeManager.getJobStatus());
    document.getElementById('expert-watch-progress-btn').addEventListener('click', () => expertModeManager.watchJobProgress(getAuthToken));
    document.getElementById('expert-stop-watch-btn').addEventListener('click', () => expertModeManager.stopWatchingJobProgress());
    document.getElementById('expert-show-log-btn').addEventListener('click', () => expertModeManager.showJobLog());
    document.getElementById('expert-resume-btn').addEventListener('click', () => expertModeManager.resumeJobById());
    document.getElementById('expert-stop-job-btn').addEventListener('click', () => expertModeManager.stopJob());
    document.getElementById('expert-list-all-btn').addEventListener('click', () => expertModeManager.listAllJobs());
    document.getElementById('expert-list-running-btn').addEventListener('click', () => expertModeManager.listRunningJobs());
    document.getElementById('expert-list-aborted-btn').addEventListener('click', () => expertModeManager.listAbortedJobs());
    document.getElementById('expert-clear-stopped-btn').addEventListener('click', () => expertModeManager.clearStoppedJobs());

    // Context Menu - Event delegation
    document.getElementById('context-menu').addEventListener('click', (e) => {
        const item = e.target.closest('.context-menu-item');
        if (!item) return;

        const action = item.getAttribute('data-action');
        if (action) {
            fileOperations.contextMenuAction(action);
            return;
        }

        const sortBy = item.getAttribute('data-sort');
        if (sortBy) {
            const asc = item.getAttribute('data-asc') === 'true';
            fileOperations.contextMenuSortBy(sortBy, asc);
        }
    });

    // Dynamic Job Buttons - Event delegation for active jobs
    document.getElementById('job-list').addEventListener('click', (e) => {
        const button = e.target.closest('.job-icon-btn');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const jobId = parseInt(button.getAttribute('data-job-id'));

        if (action === 'cancel-job') {
            jobManager.cancelJob(jobId);
        }
    });

    // Dynamic Job Buttons - Event delegation for interrupted jobs
    document.getElementById('interrupted-jobs-list').addEventListener('click', (e) => {
        const button = e.target.closest('.job-icon-btn');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const jobId = parseInt(button.getAttribute('data-job-id'));

        if (action === 'resume-interrupted') {
            jobManager.resumeInterruptedJobFromDropdown(jobId);
        } else if (action === 'cancel-interrupted') {
            jobManager.cancelInterruptedJob(jobId);
        }
    });

    // Dynamic Job Buttons - Event delegation for failed jobs
    document.getElementById('failed-jobs-list').addEventListener('click', (e) => {
        const button = e.target.closest('.job-icon-btn');
        if (!button) return;

        const action = button.getAttribute('data-action');
        const jobId = parseInt(button.getAttribute('data-job-id'));

        if (action === 'resume-failed') {
            jobManager.resumeFailedJobFromDropdown(jobId);
        } else if (action === 'cancel-failed') {
            jobManager.cancelFailedJob(jobId);
        }
    });
}

/**
 * Setup global event listeners (keyboard shortcuts, menus, etc.)
 */
function setupGlobalListeners() {
    // Hide context menu and view dropdown on click outside
    document.addEventListener('click', () => {
        document.getElementById('context-menu').style.display = 'none';
        document.getElementById('view-dropdown').classList.add('hidden');
    });

    // Add context menu to empty container backgrounds
    ['left', 'right'].forEach(pane => {
        const container = document.getElementById(`${pane}-files`);
        container.addEventListener('contextmenu', (e) => {
            if (e.target === container || e.target.tagName === 'TABLE') {
                e.preventDefault();
                const state = pane === 'left' ? leftPaneState : rightPaneState;
                if (state.selectedIndexes.length > 0) {
                    state.selectedIndexes = [];
                    fileBrowser.renderFiles(pane);
                }
                fileOperations.showContextMenu(e, pane, { value: lastFocusedPane });
            }
        });
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        const renameModal = document.getElementById('rename-modal');
        const deleteModal = document.getElementById('delete-confirm-modal');
        const createFolderModal = document.getElementById('create-folder-modal');
        const dragDropModal = document.getElementById('drag-drop-confirm-modal');
        const editRemoteModal = document.getElementById('edit-remote-config-modal');
        const viewRemoteModal = document.getElementById('view-remote-config-modal');

        // Handle Escape key
        if (e.key === 'Escape') {
            if (renameModal.style.display === 'flex') {
                fileOperations.closeRenameModal();
                return;
            }
            if (deleteModal.style.display === 'flex') {
                fileOperations.closeDeleteConfirmModal();
                return;
            }
            if (createFolderModal.style.display === 'flex') {
                fileOperations.closeCreateFolderModal();
                return;
            }
            if (dragDropModal.style.display === 'flex') {
                closeDragDropConfirmModal();
                return;
            }
            if (editRemoteModal.style.display === 'flex') {
                e.stopImmediatePropagation();
                remoteManager.closeEditRemoteConfigModal();
                return;
            }
            if (viewRemoteModal.style.display === 'flex') {
                e.stopImmediatePropagation();
                remoteManager.closeViewRemoteConfigModal();
                return;
            }
            document.getElementById('context-menu').style.display = 'none';
            document.getElementById('view-dropdown').classList.add('hidden');
            return;
        }

        // Handle Enter key for modals
        if (e.key === 'Enter') {
            if (renameModal.style.display === 'flex') {
                e.preventDefault();
                fileOperations.confirmRename();
                return;
            }
            if (deleteModal.style.display === 'flex') {
                e.preventDefault();
                fileOperations.confirmDelete();
                return;
            }
            if (createFolderModal.style.display === 'flex') {
                e.preventDefault();
                fileOperations.confirmCreateFolder();
                return;
            }
            if (dragDropModal.style.display === 'flex') {
                e.preventDefault();
                confirmDragDrop();
                return;
            }
        }

        // Ignore other shortcuts when typing in input fields
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        // F2 - Rename selected file/folder
        if (e.key === 'F2') {
            e.preventDefault();
            const state = lastFocusedPane === 'left' ? leftPaneState : rightPaneState;
            if (state.selectedIndexes.length === 1) {
                const file = state.files[state.selectedIndexes[0]];
                contextMenuState.pane = lastFocusedPane;
                contextMenuState.items = [file];
                fileOperations.showRenameModal(file.Name);
            }
            return;
        }

        // Delete - Delete selected files/folders
        if (e.key === 'Delete') {
            e.preventDefault();
            const state = lastFocusedPane === 'left' ? leftPaneState : rightPaneState;
            if (state.selectedIndexes.length > 0) {
                contextMenuState.pane = lastFocusedPane;
                contextMenuState.items = state.selectedIndexes.map(i => state.files[i]);
                fileOperations.showDeleteConfirmModal();
            }
            return;
        }
    });

    // Click whitespace to deselect and track focused pane
    document.getElementById('left-files').addEventListener('click', (e) => {
        lastFocusedPane = 'left';
        if (e.target.id === 'left-files' || e.target.classList.contains('file-grid') || e.target.classList.contains('file-list')) {
            leftPaneState.selectedIndexes = [];
            fileBrowser.renderFiles('left');
        }
    });
    document.getElementById('right-files').addEventListener('click', (e) => {
        lastFocusedPane = 'right';
        if (e.target.id === 'right-files' || e.target.classList.contains('file-grid') || e.target.classList.contains('file-list')) {
            rightPaneState.selectedIndexes = [];
            fileBrowser.renderFiles('right');
        }
    });
}

/**
 * Drag-drop confirmation modal functions
 */
function showDragDropConfirmModal(fileNames, sourcePath, destPath) {
    const fileListHtml = fileNames.map(name => `• ${name}`).join('<br>');
    document.getElementById('drag-drop-file-list').innerHTML = fileListHtml;
    document.getElementById('drag-drop-source').textContent = sourcePath;
    document.getElementById('drag-drop-destination').textContent = destPath;
    document.getElementById('drag-drop-confirm-modal').style.display = 'flex';
}

function closeDragDropConfirmModal() {
    document.getElementById('drag-drop-confirm-modal').style.display = 'none';
    pendingDragDrop = null;
}

async function confirmDragDrop() {
    if (!pendingDragDrop) return;

    const operation = pendingDragDrop;
    closeDragDropConfirmModal();

    // Handle external file drop
    if (operation.isExternal) {
        const { externalFiles, targetState, targetPane, hasDirectories } = operation;
        await uploadManager.handleExternalFileUpload(externalFiles, targetState, targetPane, hasDirectories);
        return;
    }

    // Handle internal drag-drop
    const { sourceState, targetState, targetPane, indexes } = operation;

    for (const index of indexes) {
        const file = sourceState.files[index];
        const srcPath = sourceState.remote ?
            `${sourceState.remote}:${buildPath(sourceState.path, file.Name)}` :
            buildPath(sourceState.path, file.Name);
        const dstPath = targetState.remote ?
            `${targetState.remote}:${targetState.path}/` :
            `${targetState.path}/`;

        try {
            await apiCall('/api/jobs/copy', 'POST', {
                src_path: srcPath,
                dst_path: dstPath,
                copy_links: false
            });
        } catch (error) {
            console.error('Copy failed:', error);
            alert(`Failed to copy ${file.Name}: ${error.message}`);
        }
    }

    fileBrowser.refreshPane(targetPane);
    jobManager.updateJobs();
}

/**
 * Main initialization function
 */
async function init() {
    // Initialize modal manager
    initModalManager();

    // Initialize modules
    initializeModules();

    // Setup event listeners
    setupEventListeners();
    setupGlobalListeners();

    // Try to load token from URL
    const urlParams = new URLSearchParams(window.location.search);
    const tokenFromUrl = urlParams.get('token');
    if (tokenFromUrl) {
        authToken = tokenFromUrl;
        setAuthToken(tokenFromUrl);
        document.getElementById('token').value = tokenFromUrl;
        document.cookie = `motus_token=${tokenFromUrl}; path=/; max-age=31536000; SameSite=Lax`;
    } else {
        // Try to load from cookie
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'motus_token') {
                authToken = value;
                setAuthToken(value);
                document.getElementById('token').value = value;
                break;
            }
        }
    }

    // Load config to get default mode and upload size limit
    try {
        const config = await apiCall('/api/config');
        currentMode = config.default_mode || 'easy';
        maxUploadSize = config.max_upload_size || 0;
        uploadManager.setMaxUploadSize(maxUploadSize);
        uiManager.setMode(currentMode);
    } catch (e) {
        console.error('Failed to load config:', e);
        uiManager.setMode('easy');
    }

    // Load user preferences from backend
    const prefs = await loadPrefs(apiCall);
    if (prefs.view_mode) {
        viewMode = prefs.view_mode;
        state.ui.viewMode = prefs.view_mode;
    }
    if (prefs.show_hidden_files !== undefined) {
        showHiddenFiles = prefs.show_hidden_files;
        state.ui.showHiddenFiles = prefs.show_hidden_files;
    }

    // Load remotes for easy mode
    if (currentMode === 'easy') {
        await navigationManager.loadRemotes();
        // If using Local Filesystem, start in home directory
        if (leftPaneState.remote === '') {
            leftPaneState.path = '~/';
            document.getElementById('left-path').value = '~/';
        }
        if (rightPaneState.remote === '') {
            rightPaneState.path = '~/';
            document.getElementById('right-path').value = '~/';
        }
        await fileBrowser.refreshPane('left');
        await fileBrowser.refreshPane('right');
        jobManager.start();
    }

    // Check for interrupted jobs modal (only on startup)
    jobManager.checkInterruptedJobs();
}

// Start the application when DOM is ready
document.addEventListener('DOMContentLoaded', init);
