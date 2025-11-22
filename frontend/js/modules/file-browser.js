/**
 * File Browser Module
 *
 * Handles file browsing, rendering, navigation, selection, and drag-drop for dual-pane interface.
 *
 * Features:
 * - Grid and list view rendering
 * - File navigation (up/into directories)
 * - File selection (single/multi/range with Shift/Ctrl)
 * - Drag-drop between panes
 * - External file/folder drop support
 * - Context menu integration
 * - Column resizing in list view
 */

export class FileBrowser {
    constructor(dependencies, callbacks = {}) {
        // Store dependencies
        this.apiCall = dependencies.apiCall;
        this.formatFileSize = dependencies.formatFileSize;
        this.formatFileDate = dependencies.formatFileDate;
        this.expandTildePath = dependencies.expandTildePath;
        this.buildPath = dependencies.buildPath;
        this.sortFiles = dependencies.sortFiles;
        this.uploadManager = dependencies.uploadManager;
        this.jobManager = dependencies.jobManager;

        // Store callbacks
        this.onArrowButtonsUpdate = callbacks.onArrowButtonsUpdate || (() => {});
        this.onContextMenuShow = callbacks.onContextMenuShow || (() => {});
        this.onDragDropConfirm = callbacks.onDragDropConfirm || (() => {});

        // Column resizing state
        this.resizingColumn = null;
        this.startX = 0;
        this.startWidth = 0;

        // State references (will be set via init)
        this.state = null;
        this.leftPaneState = null;
        this.rightPaneState = null;
        this.viewMode = null;
        this.showHiddenFiles = null;
        this.lastFocusedPane = null;
    }

    /**
     * Initialize with state references
     * Must be called before using the FileBrowser
     */
    init(stateRefs) {
        this.state = stateRefs.state;
        this.leftPaneState = stateRefs.leftPaneState;
        this.rightPaneState = stateRefs.rightPaneState;
    }

    /**
     * Get the current value of viewMode from state
     */
    getViewMode() {
        return this.state.ui.viewMode;
    }

    /**
     * Get the current value of showHiddenFiles from state
     */
    getShowHiddenFiles() {
        return this.state.ui.showHiddenFiles;
    }

    /**
     * Set sort field and direction for a pane
     */
    setSortBy(pane, field) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        if (state.sortBy === field) {
            state.sortAsc = !state.sortAsc;
        } else {
            state.sortBy = field;
            state.sortAsc = true;
        }
        this.renderFiles(pane);
    }

    /**
     * Start column resizing in list view
     */
    startColumnResize(e, th) {
        e.preventDefault();
        e.stopPropagation();

        this.resizingColumn = th;
        this.startX = e.pageX;
        this.startWidth = th.offsetWidth;

        document.addEventListener('mousemove', this.doColumnResize.bind(this));
        document.addEventListener('mouseup', this.stopColumnResize.bind(this));
    }

    /**
     * Handle column resizing
     */
    doColumnResize(e) {
        if (!this.resizingColumn) return;

        const diff = e.pageX - this.startX;
        const newWidth = this.startWidth + diff;

        // Enforce minimum width
        const minWidth = parseInt(window.getComputedStyle(this.resizingColumn).minWidth) || 50;
        if (newWidth >= minWidth) {
            this.resizingColumn.style.width = newWidth + 'px';
        }
    }

    /**
     * Stop column resizing
     */
    stopColumnResize() {
        this.resizingColumn = null;
        document.removeEventListener('mousemove', this.doColumnResize.bind(this));
        document.removeEventListener('mouseup', this.stopColumnResize.bind(this));
    }

    /**
     * Refresh pane by fetching files from backend
     */
    async refreshPane(pane, preserveSelection = false) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const fullPath = state.remote ? `${state.remote}:${state.path}` : state.path;

        // Save current selection if preserving
        const selectedFileNames = preserveSelection ?
            state.selectedIndexes.map(idx => state.files[idx]?.Name).filter(n => n) :
            [];

        try {
            const data = await this.apiCall('/api/files/ls', 'POST', { path: fullPath });
            state.files = data.files || [];

            if (preserveSelection && selectedFileNames.length > 0) {
                // Restore selection by matching file names
                state.selectedIndexes = [];
                selectedFileNames.forEach(name => {
                    const idx = state.files.findIndex(f => f.Name === name);
                    if (idx !== -1) {
                        state.selectedIndexes.push(idx);
                    }
                });
            } else {
                state.selectedIndexes = [];
            }

            this.renderFiles(pane);
        } catch (error) {
            console.error(`Failed to refresh ${pane} pane:`, error);
            alert(`Error: ${error.message}`);
            throw error; // Re-throw so callers can handle it
        }
    }

    /**
     * Render files in grid or list view
     */
    renderFiles(pane) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const container = document.getElementById(`${pane}-files`);

        // Filter hidden files if needed
        const showHidden = this.getShowHiddenFiles();
        let filesToShow = state.files;
        if (!showHidden) {
            filesToShow = state.files.filter(f => !f.Name.startsWith('.'));
        }

        // Add original index to each file before sorting
        const filesWithIndex = filesToShow.map((file, idx) => ({
            ...file,
            _originalIndex: state.files.indexOf(file)
        }));

        // Sort files
        const sortedFiles = this.sortFiles(filesWithIndex, state.sortBy, state.sortAsc);

        // Store visual order mapping for Shift+click range selection
        // Maps original index -> visual position
        state.visualOrder = {};
        sortedFiles.forEach((file, visualPos) => {
            state.visualOrder[file._originalIndex] = visualPos;
        });

        container.innerHTML = '';
        const currentViewMode = this.getViewMode();
        container.className = currentViewMode === 'grid' ? 'file-grid' : 'file-list';

        if (currentViewMode === 'grid') {
            this.renderGridView(pane, sortedFiles, container, state);
        } else {
            this.renderListView(pane, sortedFiles, container, state);
        }

        // Update arrow button states
        this.onArrowButtonsUpdate();
    }

    /**
     * Render grid view
     */
    renderGridView(pane, files, container, state) {
        // Add parent directory if not at root
        if (state.path !== '/') {
            const parentDiv = this.createFileElement({
                Name: '..',
                IsDir: true
            }, -1, pane);
            container.appendChild(parentDiv);
        }

        files.forEach((file) => {
            const fileDiv = this.createFileElement(file, file._originalIndex, pane);
            container.appendChild(fileDiv);
        });
    }

    /**
     * Render list view with table
     */
    renderListView(pane, files, container, state) {
        const table = document.createElement('table');

        // Create table header with sortable columns
        const thead = document.createElement('thead');
        const headerRow = document.createElement('tr');

        const headers = [
            { label: 'Name', field: 'name', className: 'col-name' },
            { label: 'Size', field: 'size', className: 'col-size' },
            { label: 'Date', field: 'date', className: 'col-date' }
        ];

        headers.forEach((h, idx) => {
            const th = document.createElement('th');
            th.className = h.className;
            th.textContent = h.label;
            if (state.sortBy === h.field) {
                const indicator = document.createElement('span');
                indicator.className = 'sort-indicator';
                indicator.textContent = state.sortAsc ? '▲' : '▼';
                th.appendChild(indicator);
            }
            th.onclick = (e) => {
                // Don't sort if clicking on resize handle
                if (!e.target.classList.contains('resize-handle')) {
                    this.setSortBy(pane, h.field);
                }
            };

            // Add resize handle (except for last column)
            if (idx < headers.length - 1) {
                const resizeHandle = document.createElement('div');
                resizeHandle.className = 'resize-handle';
                resizeHandle.addEventListener('mousedown', (e) => this.startColumnResize(e, th));
                th.appendChild(resizeHandle);
            }

            headerRow.appendChild(th);
        });

        thead.appendChild(headerRow);
        table.appendChild(thead);

        // Create table body
        const tbody = document.createElement('tbody');

        // Add parent directory if not at root
        if (state.path !== '/') {
            const tr = this.createListRow({ Name: '..', IsDir: true }, -1, pane);
            tbody.appendChild(tr);
        }

        files.forEach((file) => {
            const tr = this.createListRow(file, file._originalIndex, pane);
            tbody.appendChild(tr);
        });

        table.appendChild(tbody);
        container.appendChild(table);
    }

    /**
     * Create file element for grid view
     */
    createFileElement(file, index, pane) {
        const div = document.createElement('div');
        div.className = 'file-item';

        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        if (index >= 0 && state.selectedIndexes.includes(index)) {
            div.classList.add('selected');
        }

        const icon = file.IsDir ? '📁' : '📄';
        div.innerHTML = `
            <div class="file-icon">${icon}</div>
            <div class="file-name">${file.Name}</div>
        `;

        // Double-click to navigate
        div.addEventListener('dblclick', () => {
            if (file.Name === '..') {
                this.navigateUp(pane);
            } else if (file.IsDir) {
                this.navigateInto(pane, file.Name);
            }
        });

        // Single click for selection
        if (index >= 0) {
            div.addEventListener('click', (e) => {
                this.handleFileClick(pane, index, e);
            });

            // Draggable - handle mousedown for immediate selection before drag
            div.draggable = true;
            div.addEventListener('mousedown', (e) => {
                this.handleMouseDownBeforeDrag(e, pane, index, div);
            });
            div.addEventListener('dragstart', (e) => {
                this.handleDragStart(e, pane, index);
            });

            // Right-click context menu
            div.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                if (!state.selectedIndexes.includes(index)) {
                    state.selectedIndexes = [index];
                    this.renderFiles(pane);
                }
                this.onContextMenuShow(e, pane);
            });
        } else {
            // For ".." parent directory, add context menu without selection
            div.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                // Clear selection for ".." - it's not a selectable item
                state.selectedIndexes = [];
                this.renderFiles(pane);
                this.onContextMenuShow(e, pane);
            });
        }

        return div;
    }

    /**
     * Create list row for list view
     */
    createListRow(file, index, pane) {
        const tr = document.createElement('tr');
        tr.className = 'file-row';

        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        if (index >= 0 && state.selectedIndexes.includes(index)) {
            tr.classList.add('selected');
        }

        const icon = file.IsDir ? '📁' : '📄';

        // Name column
        const nameCell = document.createElement('td');
        nameCell.className = 'file-name-col';
        nameCell.innerHTML = `
            <span class="file-icon-small">${icon}</span>
            <span>${file.Name}</span>
        `;
        tr.appendChild(nameCell);

        // Size column
        const sizeCell = document.createElement('td');
        sizeCell.className = 'file-size-col';
        sizeCell.textContent = file.IsDir ? '' : this.formatFileSize(file.Size);
        tr.appendChild(sizeCell);

        // Date column
        const dateCell = document.createElement('td');
        dateCell.className = 'file-date-col';
        dateCell.textContent = this.formatFileDate(file.ModTime);
        tr.appendChild(dateCell);

        // Double-click to navigate
        tr.addEventListener('dblclick', () => {
            if (file.Name === '..') {
                this.navigateUp(pane);
            } else if (file.IsDir) {
                this.navigateInto(pane, file.Name);
            }
        });

        // Single click for selection
        if (index >= 0) {
            tr.addEventListener('click', (e) => {
                this.handleFileClick(pane, index, e);
            });

            // Draggable - handle mousedown for immediate selection before drag
            tr.draggable = true;
            tr.addEventListener('mousedown', (e) => {
                this.handleMouseDownBeforeDrag(e, pane, index, tr);
            });
            tr.addEventListener('dragstart', (e) => {
                this.handleDragStart(e, pane, index);
            });

            // Right-click context menu
            tr.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                if (!state.selectedIndexes.includes(index)) {
                    state.selectedIndexes = [index];
                    this.renderFiles(pane);
                }
                this.onContextMenuShow(e, pane);
            });
        } else {
            // For ".." parent directory, add context menu without selection
            tr.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                // Clear selection for ".." - it's not a selectable item
                state.selectedIndexes = [];
                this.renderFiles(pane);
                this.onContextMenuShow(e, pane);
            });
        }

        return tr;
    }

    /**
     * Handle mousedown before drag to ensure file is selected
     */
    handleMouseDownBeforeDrag(event, pane, index, element) {
        // Only handle left mouse button without modifier keys
        // If Ctrl/Cmd/Shift are pressed, let the click handler deal with multi-selection
        if (event.button === 0 && !event.ctrlKey && !event.metaKey && !event.shiftKey) {
            const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;

            // Select file immediately if not already selected
            // This ensures visual feedback before drag starts
            if (!state.selectedIndexes.includes(index)) {
                console.log(`mousedown: Auto-selecting file ${index} before drag`);

                // Clear opposite pane selection
                const oppositeState = pane === 'left' ? this.rightPaneState : this.leftPaneState;
                const oppositePane = pane === 'left' ? 'right' : 'left';
                if (oppositeState.selectedIndexes.length > 0) {
                    oppositeState.selectedIndexes = [];
                    const oppositeContainer = document.getElementById(oppositePane === 'left' ? 'left-files' : 'right-files');
                    oppositeContainer.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
                }

                // Update state
                state.selectedIndexes = [index];
                // Update DOM directly without re-rendering to avoid interrupting drag
                const container = document.getElementById(pane === 'left' ? 'left-files' : 'right-files');
                container.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
                element.classList.add('selected');
            }
        }
    }

    /**
     * Navigate up one directory level
     */
    async navigateUp(pane) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        let newPath;

        // Handle tilde paths specially
        if (state.path.startsWith('~/')) {
            if (state.path === '~/' || state.path === '~') {
                // Already at home, can't go up
                return;
            }
            // Remove tilde prefix, process, then add it back
            const pathWithoutTilde = state.path.substring(2); // Remove '~/'
            const pathParts = pathWithoutTilde.split('/').filter(p => p);
            pathParts.pop();
            if (pathParts.length === 0) {
                newPath = '~/';
            } else {
                newPath = '~/' + pathParts.join('/');
            }
        } else {
            // Regular path handling
            const pathParts = state.path.split('/').filter(p => p);
            pathParts.pop();
            newPath = '/' + pathParts.join('/');
        }

        // Save old path in case navigation fails
        const oldPath = state.path;
        state.path = newPath;
        document.getElementById(`${pane}-path`).value = newPath;

        try {
            await this.refreshPane(pane);
        } catch (error) {
            // Revert to old path if navigation failed
            state.path = oldPath;
            document.getElementById(`${pane}-path`).value = oldPath;
        }
    }

    /**
     * Navigate into a directory
     */
    async navigateInto(pane, dirname) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const oldPath = state.path;
        const newPath = state.path.endsWith('/') ? state.path + dirname : state.path + '/' + dirname;

        state.path = newPath;
        document.getElementById(`${pane}-path`).value = newPath;

        try {
            await this.refreshPane(pane);
        } catch (error) {
            // Revert to old path if navigation failed
            state.path = oldPath;
            document.getElementById(`${pane}-path`).value = oldPath;
        }
    }

    /**
     * Handle file click for selection
     */
    handleFileClick(pane, index, event) {
        // Update last focused pane in state
        this.state.ui.lastFocusedPane = pane;

        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;
        const oppositeState = pane === 'left' ? this.rightPaneState : this.leftPaneState;
        const oppositePane = pane === 'left' ? 'right' : 'left';
        let selectionChanged = false;
        let oppositeChanged = false;

        // Clear selection on opposite pane
        if (oppositeState.selectedIndexes.length > 0) {
            oppositeState.selectedIndexes = [];
            oppositeChanged = true;
        }

        if (event.ctrlKey || event.metaKey) {
            // Toggle selection
            const idx = state.selectedIndexes.indexOf(index);
            if (idx >= 0) {
                state.selectedIndexes.splice(idx, 1);
            } else {
                state.selectedIndexes.push(index);
            }
            selectionChanged = true;
        } else if (event.shiftKey && state.selectedIndexes.length > 0) {
            // Range selection from last selected to current
            // Use visual order (sorted) not array order
            const lastIndex = state.selectedIndexes[state.selectedIndexes.length - 1];
            const lastVisual = state.visualOrder[lastIndex] ?? lastIndex;
            const currentVisual = state.visualOrder[index] ?? index;
            const visualStart = Math.min(lastVisual, currentVisual);
            const visualEnd = Math.max(lastVisual, currentVisual);

            // Convert visual positions back to original indexes
            state.selectedIndexes = [];
            Object.keys(state.visualOrder).forEach(origIndex => {
                const visualPos = state.visualOrder[origIndex];
                if (visualPos >= visualStart && visualPos <= visualEnd) {
                    state.selectedIndexes.push(parseInt(origIndex));
                }
            });
            selectionChanged = true;
        } else {
            // Single selection - only change if different
            if (state.selectedIndexes.length !== 1 || state.selectedIndexes[0] !== index) {
                state.selectedIndexes = [index];
                selectionChanged = true;
            }
        }

        // Re-render panes if selection changed
        if (selectionChanged) {
            this.renderFiles(pane);
        }
        if (oppositeChanged) {
            this.renderFiles(oppositePane);
        }
        // Always update arrow buttons after any selection change
        this.onArrowButtonsUpdate();
    }

    /**
     * Handle drag start
     */
    handleDragStart(event, pane, index) {
        const state = pane === 'left' ? this.leftPaneState : this.rightPaneState;

        // Note: Selection already happened in mousedown handler
        // This ensures the file is visually selected before drag starts

        event.dataTransfer.effectAllowed = 'copy';
        event.dataTransfer.setData('text/plain', JSON.stringify({
            pane,
            indexes: state.selectedIndexes
        }));
    }

    /**
     * Handle drag over
     */
    handleDragOver(event, targetPane) {
        event.preventDefault();
        event.dataTransfer.dropEffect = 'copy';
        document.getElementById(`${targetPane}-files`).classList.add('drag-over');
    }

    /**
     * Handle drag leave
     */
    handleDragLeave(event, targetPane) {
        document.getElementById(`${targetPane}-files`).classList.remove('drag-over');
    }

    /**
     * Handle drop
     */
    async handleDrop(event, targetPane) {
        event.preventDefault();
        document.getElementById(`${targetPane}-files`).classList.remove('drag-over');

        // Check if this is external file drop (from desktop)
        const dragDataText = event.dataTransfer.getData('text/plain');
        const items = event.dataTransfer.items;
        const externalFiles = event.dataTransfer.files;

        if ((items || externalFiles) && externalFiles.length > 0 && !dragDataText) {
            // External file drop from desktop - check for folders
            if (items && items.length > 0) {
                // Use DataTransferItem API to support folders (Chrome/Edge/Safari)
                await this.handleExternalDropWithFolders(items, targetPane);
            } else {
                // Fallback to simple file drop (Firefox)
                await this.handleExternalFileDrop(externalFiles, targetPane);
            }
            return;
        }

        // Internal drag-drop between panes
        const data = JSON.parse(dragDataText);
        const sourcePane = data.pane;

        if (sourcePane === targetPane) {
            return; // Can't drop on same pane
        }

        const sourceState = sourcePane === 'left' ? this.leftPaneState : this.rightPaneState;
        const targetState = targetPane === 'left' ? this.leftPaneState : this.rightPaneState;

        // Build file list and paths for confirmation dialog
        const files = data.indexes.map(index => sourceState.files[index]);
        const fileNames = files.map(f => f.Name);

        // Build source and destination paths
        const sourcePath = sourceState.remote ?
            `${sourceState.remote}:${sourceState.path}` :
            sourceState.path;
        const destPath = targetState.remote ?
            `${targetState.remote}:${targetState.path}` :
            targetState.path;

        // Show confirmation dialog via callback
        this.onDragDropConfirm({
            type: 'internal',
            sourcePane,
            targetPane,
            sourceState,
            targetState,
            indexes: data.indexes,
            files,
            fileNames,
            sourcePath,
            destPath
        });
    }

    /**
     * Handle external drop with folder support
     */
    async handleExternalDropWithFolders(items, targetPane) {
        const targetState = targetPane === 'left' ? this.leftPaneState : this.rightPaneState;

        try {
            // Collect all files (including from folders recursively)
            const filesWithPaths = [];

            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : item.getAsEntry?.();
                    if (entry) {
                        await this.traverseFileTree(entry, '', filesWithPaths);
                    } else {
                        // Fallback for browsers without folder support
                        const file = item.getAsFile();
                        if (file) {
                            filesWithPaths.push({ file, path: file.name });
                        }
                    }
                }
            }

            if (filesWithPaths.length === 0) {
                alert('No files found to upload');
                return;
            }

            // Check size limit
            const sizeCheck = this.uploadManager.checkUploadSizeLimit(filesWithPaths);
            if (!sizeCheck.valid) {
                alert(sizeCheck.error);
                return;
            }

            // Build destination path
            const destPath = targetState.remote ?
                `${targetState.remote}:${targetState.path}` :
                targetState.path;

            // Get file names for confirmation (show paths for nested files)
            const fileNames = filesWithPaths.map(f => f.path);

            // Show confirmation modal via callback
            this.onDragDropConfirm({
                type: 'external',
                isExternal: true,
                externalFiles: filesWithPaths,  // Array of {file, path}
                targetPane,
                targetState,
                hasDirectories: true,
                fileNames,
                sourcePath: 'Your Computer',
                destPath
            });

        } catch (error) {
            console.error('Error processing folder drop:', error);
            alert('Error processing dropped folders. Your browser may not support folder uploads.\n\nTry using Chrome, Edge, or Safari for folder support.');
        }
    }

    /**
     * Traverse file tree recursively (for folder uploads)
     */
    async traverseFileTree(entry, path, filesWithPaths) {
        if (entry.isFile) {
            // It's a file, get the File object
            return new Promise((resolve, reject) => {
                entry.file(
                    file => {
                        const fullPath = path + file.name;
                        filesWithPaths.push({ file, path: fullPath });
                        resolve();
                    },
                    error => {
                        console.error('Error reading file:', error);
                        resolve(); // Continue even if one file fails
                    }
                );
            });
        } else if (entry.isDirectory) {
            // It's a directory, read its contents
            const dirReader = entry.createReader();
            return new Promise((resolve, reject) => {
                const readEntries = () => {
                    dirReader.readEntries(
                        async entries => {
                            if (entries.length === 0) {
                                resolve(); // No more entries
                                return;
                            }
                            // Process all entries in this batch
                            for (const childEntry of entries) {
                                await this.traverseFileTree(childEntry, path + entry.name + '/', filesWithPaths);
                            }
                            // Continue reading (directories can have multiple batches)
                            readEntries();
                        },
                        error => {
                            console.error('Error reading directory:', error);
                            resolve(); // Continue even if one directory fails
                        }
                    );
                };
                readEntries();
            });
        }
    }

    /**
     * Handle external file drop (fallback without folder support)
     */
    async handleExternalFileDrop(files, targetPane) {
        const targetState = targetPane === 'left' ? this.leftPaneState : this.rightPaneState;

        // Convert FileList to Array immediately (FileList becomes invalid after event)
        const filesArray = Array.from(files);

        // Check size limit
        const sizeCheck = this.uploadManager.checkUploadSizeLimit(filesArray);
        if (!sizeCheck.valid) {
            alert(sizeCheck.error);
            return;
        }

        // Build destination path
        const destPath = targetState.remote ?
            `${targetState.remote}:${targetState.path}` :
            targetState.path;

        // Get file names for confirmation
        const fileNames = filesArray.map(f => f.name);

        // Show confirmation modal via callback
        this.onDragDropConfirm({
            type: 'external',
            isExternal: true,
            externalFiles: filesArray,  // Store as array, not FileList
            targetPane,
            targetState,
            fileNames,
            sourcePath: 'Your Computer',
            destPath
        });
    }
}
