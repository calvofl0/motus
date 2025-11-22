/**
 * File Operations Module
 *
 * Handles file operations including context menu, rename, delete, create folder, and copy operations.
 *
 * Features:
 * - Context menu display and actions
 * - Rename files/folders
 * - Delete files/folders (with confirmation)
 * - Create folders (with relative path support)
 * - Copy operations (arrow buttons between panes)
 * - Arrow button state management
 */

export class FileOperations {
    constructor(dependencies, callbacks = {}) {
        // Store dependencies
        this.apiCall = dependencies.apiCall;
        this.buildPath = dependencies.buildPath;
        this.expandTildePath = dependencies.expandTildePath;
        this.resolveRelativePath = dependencies.resolveRelativePath;
        this.ModalManager = dependencies.ModalManager;

        // Store callbacks
        this.onRefreshPane = callbacks.onRefreshPane || (() => {});
        this.onRenderFiles = callbacks.onRenderFiles || (() => {});
        this.onShowDragDropConfirm = callbacks.onShowDragDropConfirm || (() => {});

        // State references (will be set via init)
        this.leftPaneState = null;
        this.rightPaneState = null;
        this.contextMenuState = null;
        this.createFolderPane = null;
    }

    /**
     * Initialize with state references
     */
    init(stateRefs) {
        this.leftPaneState = stateRefs.leftPaneState;
        this.rightPaneState = stateRefs.rightPaneState;
        this.contextMenuState = stateRefs.contextMenuState;
        this.createFolderPane = stateRefs.createFolderPane;
    }

    /**
     * Update arrow button visual states based on selections
     */
    updateArrowButtons() {
        const leftBtn = document.getElementById('copy-left-btn');
        const rightBtn = document.getElementById('copy-right-btn');

        if (!leftBtn || !rightBtn) return;

        // Enable right arrow if left pane has selections
        if (this.leftPaneState.selectedIndexes.length > 0) {
            rightBtn.style.opacity = '1';
            rightBtn.style.cursor = 'pointer';
            rightBtn.style.transform = rightBtn.style.transform ? rightBtn.style.transform.replace('scale(1)', 'scale(1.1)') : 'scale(1.1)';
        } else {
            rightBtn.style.opacity = '0.3';
            rightBtn.style.cursor = 'not-allowed';
            rightBtn.style.transform = rightBtn.style.transform ? rightBtn.style.transform.replace('scale(1.1)', 'scale(1)') : 'scale(1)';
        }

        // Enable left arrow if right pane has selections
        if (this.rightPaneState.selectedIndexes.length > 0) {
            leftBtn.style.opacity = '1';
            leftBtn.style.cursor = 'pointer';
            // Keep rotation but add scale
            const rotation = leftBtn.style.transform.includes('rotate') ? 'rotate(180deg) ' : '';
            leftBtn.style.transform = rotation + 'scale(1.1)';
        } else {
            leftBtn.style.opacity = '0.3';
            leftBtn.style.cursor = 'not-allowed';
            // Keep rotation but reset scale
            const rotation = leftBtn.style.transform.includes('rotate') ? 'rotate(180deg) ' : '';
            leftBtn.style.transform = rotation + 'scale(1)';
        }
    }

    /**
     * Copy selected files from left to right pane
     */
    async copySelectedToRight() {
        if (this.leftPaneState.selectedIndexes.length === 0) return;

        // Build list of files and paths for confirmation
        const files = this.leftPaneState.selectedIndexes.map(index => this.leftPaneState.files[index]);
        const fileNames = files.map(f => f.Name);

        const sourcePath = this.leftPaneState.remote ?
            `${this.leftPaneState.remote}:${this.leftPaneState.path}` :
            this.leftPaneState.path;
        const destPath = this.rightPaneState.remote ?
            `${this.rightPaneState.remote}:${this.rightPaneState.path}` :
            this.rightPaneState.path;

        // Show confirmation via callback
        this.onShowDragDropConfirm({
            type: 'arrow',
            sourcePane: 'left',
            targetPane: 'right',
            sourceState: this.leftPaneState,
            targetState: this.rightPaneState,
            indexes: this.leftPaneState.selectedIndexes,
            files,
            fileNames,
            sourcePath,
            destPath
        });
    }

    /**
     * Copy selected files from right to left pane
     */
    async copySelectedToLeft() {
        if (this.rightPaneState.selectedIndexes.length === 0) return;

        // Build list of files and paths for confirmation
        const files = this.rightPaneState.selectedIndexes.map(index => this.rightPaneState.files[index]);
        const fileNames = files.map(f => f.Name);

        const sourcePath = this.rightPaneState.remote ?
            `${this.rightPaneState.remote}:${this.rightPaneState.path}` :
            this.rightPaneState.path;
        const destPath = this.leftPaneState.remote ?
            `${this.leftPaneState.remote}:${this.leftPaneState.path}` :
            this.leftPaneState.path;

        // Show confirmation via callback
        this.onShowDragDropConfirm({
            type: 'arrow',
            sourcePane: 'right',
            targetPane: 'left',
            sourceState: this.rightPaneState,
            targetState: this.leftPaneState,
            indexes: this.rightPaneState.selectedIndexes,
            files,
            fileNames,
            sourcePath,
            destPath
        });
    }

    /**
     * Show context menu at event position
     */
    showContextMenu(event, pane, lastFocusedPane) {
        // Update last focused pane (passed as param since it's not in state)
        if (lastFocusedPane !== undefined) {
            lastFocusedPane.value = pane;
        }

        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        this.contextMenuState.pane = pane;
        this.contextMenuState.items = state.selectedIndexes.map(i => state.files[i]);

        const menu = document.getElementById('context-menu');
        menu.style.display = 'block';
        menu.style.left = event.pageX + 'px';
        menu.style.top = event.pageY + 'px';

        // Get menu items
        const menuItems = menu.querySelectorAll('.context-menu-item');
        const createFolderItem = menuItems[0];  // 📁 Create Folder
        const renameItem = menuItems[1];  // ✏️ Rename
        const deleteItem = menuItems[2];  // 🗑️ Delete

        // Show/hide items based on selection
        const hasSelection = state.selectedIndexes.length > 0;
        const isSingleSelection = state.selectedIndexes.length === 1;

        // Create Folder: always available
        createFolderItem.style.display = 'block';

        // Rename: only for single selection
        if (isSingleSelection) {
            renameItem.style.display = 'block';
        } else {
            renameItem.style.display = 'none';
        }

        // Delete: only when something is selected
        if (hasSelection) {
            deleteItem.style.display = 'block';
        } else {
            deleteItem.style.display = 'none';
        }
    }

    /**
     * Handle context menu action
     */
    contextMenuAction(action) {
        document.getElementById('context-menu').style.display = 'none';

        if (action === 'rename' && this.contextMenuState.items.length === 1) {
            this.showRenameModal(this.contextMenuState.items[0].Name);
        } else if (action === 'delete') {
            this.showDeleteConfirmModal();
        } else if (action === 'newfolder') {
            this.createFolder(this.contextMenuState.pane);
        }
    }

    /**
     * Handle context menu sort action
     */
    contextMenuSortBy(field, ascending) {
        document.getElementById('context-menu').style.display = 'none';

        const pane = this.contextMenuState.pane;
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        state.sortBy = field;
        state.sortAsc = ascending;
        this.onRenderFiles(pane);
    }

    /**
     * Show rename modal
     */
    showRenameModal(currentName) {
        const input = document.getElementById('rename-input');
        input.value = currentName;

        this.ModalManager.open('rename-modal', {
            onEscape: () => this.closeRenameModal(),
            onEnter: () => this.confirmRename()
        });

        // Select text after modal opens for easy editing
        setTimeout(() => {
            input.select();
        }, 150);
    }

    /**
     * Close rename modal
     */
    closeRenameModal() {
        this.ModalManager.close('rename-modal');
    }

    /**
     * Confirm and execute rename operation
     */
    async confirmRename() {
        const newName = document.getElementById('rename-input').value.trim();
        if (!newName) {
            alert('Please enter a name');
            return;
        }

        const pane = this.contextMenuState.pane;
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const file = this.contextMenuState.items[0];

        // Skip no-op rename (same name)
        if (newName === file.Name) {
            this.closeRenameModal();
            return;
        }

        // Check if destination already exists
        const existingFile = state.files.find(f => f.Name === newName);
        if (existingFile) {
            alert(`A file or folder named "${newName}" already exists in this directory`);
            return;
        }

        const oldPath = state.remote ?
            `${state.remote}:${this.buildPath(state.path, file.Name)}` :
            this.buildPath(state.path, file.Name);
        const newPath = state.remote ?
            `${state.remote}:${this.buildPath(state.path, newName)}` :
            this.buildPath(state.path, newName);

        try {
            // Use move operation for rename
            await this.apiCall('/api/jobs/move', 'POST', {
                src_path: oldPath,
                dst_path: newPath
            });
            this.closeRenameModal();
            await this.onRefreshPane(pane);
        } catch (error) {
            alert(`Rename failed: ${error.message}`);
        }
    }

    /**
     * Show delete confirmation modal
     */
    showDeleteConfirmModal() {
        const count = this.contextMenuState.items.length;
        document.getElementById('delete-confirm-message').textContent =
            `Are you sure you want to delete ${count} item(s)?`;

        this.ModalManager.open('delete-confirm-modal', {
            onEscape: () => this.closeDeleteConfirmModal(),
            onEnter: () => this.confirmDelete()
        });
    }

    /**
     * Close delete confirmation modal
     */
    closeDeleteConfirmModal() {
        this.ModalManager.close('delete-confirm-modal');
    }

    /**
     * Confirm and execute delete operation
     */
    async confirmDelete() {
        const pane = this.contextMenuState.pane;
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;

        // Close modal immediately for better UX
        this.closeDeleteConfirmModal();

        // Perform deletes in background
        for (const file of this.contextMenuState.items) {
            const path = state.remote ?
                `${state.remote}:${this.buildPath(state.path, file.Name)}` :
                this.buildPath(state.path, file.Name);

            try {
                await this.apiCall('/api/files/delete', 'POST', { path });
            } catch (error) {
                alert(`Failed to delete ${file.Name}: ${error.message}`);
            }
        }

        // Refresh after all deletes complete
        await this.onRefreshPane(pane, true);
    }

    /**
     * Show create folder modal
     */
    createFolder(pane) {
        this.createFolderPane.value = pane;
        const input = document.getElementById('create-folder-input');
        input.value = '';

        this.ModalManager.open('create-folder-modal', {
            onEscape: () => this.closeCreateFolderModal(),
            onEnter: () => this.confirmCreateFolder()
        });
    }

    /**
     * Close create folder modal
     */
    closeCreateFolderModal() {
        this.ModalManager.close('create-folder-modal');
    }

    /**
     * Confirm and execute create folder operation
     */
    async confirmCreateFolder() {
        let name = document.getElementById('create-folder-input').value.trim();
        if (!name) {
            alert('Please enter a folder name');
            return;
        }

        const pane = this.createFolderPane.value;
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;

        // Support relative paths - resolve against current directory
        const resolvedName = this.resolveRelativePath(state.path, name);

        const path = state.remote ?
            `${state.remote}:${resolvedName}` :
            resolvedName;

        try {
            await this.apiCall('/api/files/mkdir', 'POST', { path: this.expandTildePath(path) });
            this.closeCreateFolderModal();
            await this.onRefreshPane(pane);
        } catch (error) {
            alert(`Failed to create folder: ${error.message}`);
        }
    }
}
