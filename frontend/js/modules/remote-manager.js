/**
 * Remote Manager Module
 *
 * Handles rclone remote configuration management including:
 * - CRUD operations for remotes
 * - Template-based remote creation
 * - Remote configuration viewing and editing
 * - Modal UI management
 */

export class RemoteManager {
    constructor(apiCall, modalManager, callbacks = {}) {
        this.apiCall = apiCall;
        this.modalManager = modalManager;

        // Callbacks
        this.onRemotesChanged = callbacks.onRemotesChanged || (() => {});
        this.getActivePanes = callbacks.getActivePanes || (() => ({ left: '', right: '' }));
        this.onOAuthRefresh = callbacks.onOAuthRefresh || null;

        // Internal state
        this.state = {
            remotes: [],
            templates: [],
            selectedTemplate: null,
            formValues: {},
            editingRemote: null,
            currentViewedRemote: null
        };

        // Bind event handlers
        this.handleViewRemoteConfigKeydown = this.handleViewRemoteConfigKeydown.bind(this);
    }

    /**
     * Open the Manage Remotes dialog
     */
    async open() {
        this.modalManager.open('manage-remotes-modal', {
            onEscape: () => this.handleEscape(),
            onEnter: () => this.handleEnter(),
            onClose: () => this.cleanup()
        });

        this.showRemotesList();
        await this.loadRemotesList();
        await this.loadTemplatesList();
    }

    /**
     * Close the Manage Remotes dialog
     */
    close() {
        this.modalManager.close('manage-remotes-modal');
    }

    /**
     * Clean up state when modal closes
     */
    cleanup() {
        this.state.selectedTemplate = null;
        this.state.formValues = {};
    }

    /**
     * Handle Escape key in modal
     */
    handleEscape() {
        const step1 = document.getElementById('manage-remotes-step1');
        const step2 = document.getElementById('manage-remotes-step2');
        const step3 = document.getElementById('manage-remotes-step3');

        if (step2.style.display !== 'none' || step3.style.display !== 'none') {
            this.showRemotesList();
        } else {
            this.close();
        }
    }

    /**
     * Handle Enter key in modal
     */
    handleEnter() {
        const step2 = document.getElementById('manage-remotes-step2');
        const step3 = document.getElementById('manage-remotes-step3');

        const customTextarea = document.getElementById('custom-remote-config');
        const isInCustomTextarea = customTextarea && document.activeElement === customTextarea;

        if (step2.style.display !== 'none') {
            const nextBtn = document.getElementById('template-next-btn');
            if (!nextBtn.disabled) {
                this.showRemoteForm();
            }
        } else if (step3.style.display !== 'none' && !isInCustomTextarea) {
            const createBtn = document.getElementById('create-remote-btn');
            if (createBtn && !createBtn.disabled) {
                this.createRemote();
            }
        }
    }

    /**
     * Show remotes list (step 1)
     */
    showRemotesList() {
        this.state.selectedTemplate = null;
        this.state.formValues = {};

        document.getElementById('manage-remotes-step1').style.display = 'flex';
        document.getElementById('manage-remotes-step2').style.display = 'none';
        document.getElementById('manage-remotes-step3').style.display = 'none';
    }

    /**
     * Show template selection (step 2)
     */
    showTemplateSelection() {
        const step3 = document.getElementById('manage-remotes-step3');
        const isComingFromStep3 = step3.style.display !== 'none';

        if (!isComingFromStep3) {
            this.state.selectedTemplate = null;
            this.state.formValues = {};
        } else {
            this.saveCurrentFormValues();
        }

        document.getElementById('manage-remotes-step1').style.display = 'none';
        document.getElementById('manage-remotes-step2').style.display = 'flex';
        document.getElementById('manage-remotes-step3').style.display = 'none';
        this.renderTemplatesList();
        document.getElementById('template-next-btn').disabled = !this.state.selectedTemplate;
    }

    /**
     * Show remote configuration form (step 3)
     */
    showRemoteForm() {
        document.getElementById('manage-remotes-step1').style.display = 'none';
        document.getElementById('manage-remotes-step2').style.display = 'none';
        document.getElementById('manage-remotes-step3').style.display = 'flex';
        this.generateRemoteForm();
    }

    /**
     * Load remotes list from API
     */
    async loadRemotesList() {
        try {
            const data = await this.apiCall('/api/remotes');
            this.state.remotes = data.remotes || [];
            this.renderRemotesList();
        } catch (error) {
            document.getElementById('remotes-list-container').innerHTML =
                `<p style="color: #dc3545;">Error loading remotes: ${error.message}</p>`;
        }
    }

    /**
     * Load templates list from API
     */
    async loadTemplatesList() {
        try {
            const data = await this.apiCall('/api/templates');
            this.state.templates = data.templates || [];

            const addBtn = document.getElementById('add-remote-btn');
            if (data.available && data.templates.length > 0) {
                addBtn.style.display = 'inline-block';
            } else {
                addBtn.style.display = 'none';
            }

            this.renderTemplatesList();
        } catch (error) {
            console.error('Error loading templates:', error);
            document.getElementById('add-remote-btn').style.display = 'none';
        }
    }

    /**
     * Render remotes list
     */
    renderRemotesList() {
        const container = document.getElementById('remotes-list-container');

        if (this.state.remotes.length === 0) {
            container.innerHTML = '<p style="color: #666; text-align: center;">No remotes configured</p>';
            return;
        }

        const activePanes = this.getActivePanes();
        const activeRemotes = new Set();
        if (activePanes.left) activeRemotes.add(activePanes.left);
        if (activePanes.right) activeRemotes.add(activePanes.right);

        let html = '<table style="width: 100%; border-collapse: collapse;">';
        html += '<thead><tr style="border-bottom: 2px solid #ddd;">';
        html += '<th style="text-align: left; padding: 8px;">Name</th>';
        html += '<th style="text-align: left; padding: 8px;">Type</th>';
        html += '<th style="text-align: center; padding: 8px; width: 140px;">Actions</th>';
        html += '</tr></thead><tbody>';

        this.state.remotes.forEach(remote => {
            const isActive = activeRemotes.has(remote.name);
            html += '<tr class="remote-row" data-remote-name="' + remote.name + '" style="border-bottom: 1px solid #eee; cursor: pointer; transition: background-color 0.2s;" title="Click to view configuration">';
            html += `<td style="padding: 8px;">${remote.name}</td>`;
            html += `<td style="padding: 8px;">${remote.type}</td>`;
            html += `<td class="remote-actions" style="padding: 8px; text-align: center;">`;

            if (remote.is_oauth) {
                html += `<button class="remote-action-btn" data-action="refresh-oauth" data-remote-name="${remote.name}" style="background: none; border: none; font-size: 18px; cursor: pointer; color: #28a745; padding: 4px 8px; margin-right: 4px;" title="Refresh OAuth token">↻</button>`;
            } else {
                html += `<span style="display: inline-block; width: 32px; margin-right: 4px;"></span>`;
            }

            if (isActive) {
                html += `<button disabled style="background: none; border: none; font-size: 14px; cursor: not-allowed; color: #ccc; padding: 4px 8px; margin-right: 4px;" title="Cannot edit remote while in use">✏️</button>`;
            } else {
                html += `<button class="remote-action-btn" data-action="edit" data-remote-name="${remote.name}" style="background: none; border: none; font-size: 14px; cursor: pointer; color: #007bff; padding: 4px 8px; margin-right: 4px;" title="Edit remote">✏️</button>`;
            }

            if (isActive) {
                html += `<button disabled style="background: none; border: none; font-size: 18px; cursor: not-allowed; color: #ccc; padding: 4px 8px;" title="Cannot delete remote while in use">🗑️</button>`;
            } else {
                html += `<button class="remote-action-btn" data-action="delete" data-remote-name="${remote.name}" style="background: none; border: none; font-size: 18px; cursor: pointer; color: #dc3545; padding: 4px 8px;" title="Delete remote">🗑️</button>`;
            }
            html += '</td></tr>';
        });

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    /**
     * Render templates list
     */
    renderTemplatesList() {
        const container = document.getElementById('templates-list-container');

        if (this.state.templates.length === 0) {
            container.innerHTML = '<p style="color: #666; text-align: center;">No templates available</p>';
            return;
        }

        let html = '<div style="display: flex; flex-direction: column; gap: 10px;">';

        this.state.templates.forEach(template => {
            const isSelected = this.state.selectedTemplate?.name === template.name;
            const selectedStyle = isSelected ? 'border: 2px solid #007bff; background: #e7f3ff;' : 'border: 1px solid #ddd;';

            html += `<div class="template-item" data-template-name="${template.name}" style="padding: 12px; ${selectedStyle} border-radius: 6px; cursor: pointer;">`;
            html += `<strong style="display: block; margin-bottom: 4px;">${template.name}</strong>`;
            if (template.fields && template.fields.length > 0) {
                html += `<small style="color: #666;">Fields: ${template.fields.map(f => f.label).join(', ')}</small>`;
            }
            html += '</div>';
        });

        const isCustomSelected = this.state.selectedTemplate?.name === '__custom__';
        const customSelectedStyle = isCustomSelected ? 'border: 2px solid #007bff; background: #e7f3ff;' : 'border: 1px solid #ddd;';
        html += `<div class="template-item" data-template-name="__custom__" style="padding: 12px; ${customSelectedStyle} border-radius: 6px; cursor: pointer;">`;
        html += `<strong style="display: block; margin-bottom: 4px;">Custom Remote</strong>`;
        html += `<small style="color: #666;">Manually enter remote configuration</small>`;
        html += '</div>';

        html += '</div>';
        container.innerHTML = html;
    }

    /**
     * Select a template
     */
    selectTemplate(templateName) {
        const previousTemplate = this.state.selectedTemplate?.name;
        const isChangingTemplate = previousTemplate && previousTemplate !== templateName;

        if (templateName === '__custom__') {
            this.state.selectedTemplate = {
                name: '__custom__',
                fields: []
            };
        } else {
            const template = this.state.templates.find(t => t.name === templateName);
            this.state.selectedTemplate = template;
        }

        if (isChangingTemplate) {
            this.state.formValues = {};
        }

        this.renderTemplatesList();
        document.getElementById('template-next-btn').disabled = false;
    }

    /**
     * Generate remote configuration form
     */
    generateRemoteForm() {
        const container = document.getElementById('remote-form-container');
        const template = this.state.selectedTemplate;

        if (!template) return;

        if (template.name === '__custom__') {
            let html = `<p style="margin-bottom: 15px;"><strong>Custom Remote Configuration</strong></p>`;
            html += '<div style="margin-bottom: 15px;">';
            html += '<p style="color: #666; margin-bottom: 10px;">Enter the rclone configuration for your custom remote. Must include the [remote_name] section header.</p>';
            html += '<textarea id="custom-remote-config" ';
            html += 'style="width: 100%; min-height: 300px; max-height: 50vh; font-family: monospace; font-size: 12px; padding: 12px; border: 1px solid #ddd; border-radius: 4px; resize: vertical;" ';
            html += 'placeholder="[myremote]\ntype = s3\naccess_key_id = YOUR_ACCESS_KEY\nsecret_access_key = YOUR_SECRET_KEY\nregion = us-east-1\n..."></textarea>';
            html += '</div>';
            container.innerHTML = html;

            const textarea = document.getElementById('custom-remote-config');
            if (this.state.formValues['custom-config']) {
                textarea.value = this.state.formValues['custom-config'];
            }

            textarea.addEventListener('input', () => this.validateRemoteForm());
            this.validateRemoteForm();
        } else {
            let html = `<p style="margin-bottom: 15px;"><strong>Template:</strong> ${template.name}</p>`;
            html += '<div style="display: flex; flex-direction: column; gap: 12px;">';

            // Remote Name field
            html += '<div>';
            html += '<label style="display: block; margin-bottom: 4px; font-weight: 500;">Remote Name</label>';
            html += '<input type="text" id="remote-name-input" placeholder="Enter remote name" ';
            html += 'pattern="[a-zA-Z0-9_-]+" title="Use only letters, numbers, underscores, and hyphens" ';
            html += 'style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required />';
            html += '<small style="color: #666;">Use only letters, numbers, underscores, and hyphens</small>';
            html += '</div>';

            // Template fields
            template.fields.forEach(field => {
                const isSecret = field.label.toLowerCase().includes('password') ||
                                field.label.toLowerCase().includes('secret') ||
                                field.label.toLowerCase().includes('key');
                const inputType = isSecret ? 'password' : 'text';

                html += '<div>';

                // Label with optional help icon
                html += `<label style="display: block; margin-bottom: 4px; font-weight: 500;">`;
                html += field.label;
                if (field.help) {
                    // Add help icon with tooltip
                    html += ` <span class="help-icon" style="display: inline-block; cursor: help; position: relative;">`;
                    // Use SVG info icon with transparent background
                    html += `<svg width="16" height="16" viewBox="0 0 16 16" style="vertical-align: middle; margin-left: 4px;">`;
                    html += `<circle cx="8" cy="8" r="7" fill="none" stroke="#007bff" stroke-width="1.5"/>`;
                    html += `<text x="8" y="11" text-anchor="middle" fill="#007bff" font-size="11" font-weight="bold" font-family="serif">i</text>`;
                    html += `</svg>`;
                    html += `<span class="help-tooltip" style="display: none; position: absolute; left: 20px; top: -5px; background: #2c3e50; color: white; padding: 10px 14px; border-radius: 6px; z-index: 1000; font-size: 13px; font-weight: normal; min-width: 250px; max-width: 400px; white-space: normal; line-height: 1.4; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">`;
                    html += field.help; // HTML with links already converted
                    // Add small arrow pointing to icon
                    html += `<span style="position: absolute; left: -6px; top: 8px; width: 0; height: 0; border-top: 6px solid transparent; border-bottom: 6px solid transparent; border-right: 6px solid #2c3e50;"></span>`;
                    html += `</span>`;
                    html += `</span>`;
                }
                html += `</label>`;

                if (isSecret) {
                    // Password field with visibility toggle
                    html += '<div style="position: relative;">';
                    html += `<input type="${inputType}" id="field-${field.key}" placeholder="Enter ${field.label}" `;
                    html += 'style="width: 100%; padding: 8px; padding-right: 40px; border: 1px solid #ddd; border-radius: 4px;" required />';
                    html += `<button type="button" class="password-toggle-btn" data-field-id="field-${field.key}" `;
                    html += 'style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); background: none; border: none; cursor: pointer; font-size: 18px; color: #666; padding: 4px;" ';
                    html += 'title="Toggle password visibility">👁️</button>';
                    html += '</div>';
                } else {
                    // Regular text field
                    html += `<input type="${inputType}" id="field-${field.key}" placeholder="Enter ${field.label}" `;
                    html += 'style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;" required />';
                }

                html += '</div>';
            });

            html += '</div>';
            container.innerHTML = html;

            // Restore form values and add event listeners
            const nameInput = document.getElementById('remote-name-input');
            if (this.state.formValues['remote-name']) {
                nameInput.value = this.state.formValues['remote-name'];
            }

            template.fields.forEach(field => {
                const input = document.getElementById(`field-${field.key}`);
                if (input && this.state.formValues[field.key]) {
                    input.value = this.state.formValues[field.key];
                }
                input.addEventListener('input', () => this.validateRemoteForm());
            });

            nameInput.addEventListener('input', () => this.validateRemoteForm());

            // Add password toggle event listeners
            container.querySelectorAll('.password-toggle-btn').forEach(btn => {
                btn.addEventListener('click', (e) => this.togglePasswordVisibility(e));
            });

            // Add tooltip hover event listeners
            container.querySelectorAll('.help-icon').forEach(icon => {
                const tooltip = icon.querySelector('.help-tooltip');
                if (tooltip) {
                    // Show tooltip on hover of icon or tooltip itself
                    icon.addEventListener('mouseenter', () => {
                        tooltip.style.display = 'block';
                    });

                    // Hide tooltip when mouse leaves both icon and tooltip
                    let hideTimeout;
                    icon.addEventListener('mouseleave', () => {
                        hideTimeout = setTimeout(() => {
                            // Check if mouse is over tooltip
                            if (!tooltip.matches(':hover')) {
                                tooltip.style.display = 'none';
                            }
                        }, 100);
                    });

                    tooltip.addEventListener('mouseenter', () => {
                        clearTimeout(hideTimeout);
                        tooltip.style.display = 'block';
                    });

                    tooltip.addEventListener('mouseleave', () => {
                        tooltip.style.display = 'none';
                    });
                }
            });

            this.validateRemoteForm();
        }
    }

    /**
     * Save current form values
     */
    saveCurrentFormValues() {
        const template = this.state.selectedTemplate;
        if (!template) return;

        if (template.name === '__custom__') {
            const textarea = document.getElementById('custom-remote-config');
            if (textarea) {
                this.state.formValues = {
                    'custom-config': textarea.value
                };
            }
        } else {
            const values = {};
            const nameInput = document.getElementById('remote-name-input');
            if (nameInput) {
                values['remote-name'] = nameInput.value;
            }

            template.fields.forEach(field => {
                const input = document.getElementById(`field-${field.key}`);
                if (input) {
                    values[field.key] = input.value;
                }
            });

            this.state.formValues = values;
        }
    }

    /**
     * Validate remote form
     */
    validateRemoteForm() {
        const template = this.state.selectedTemplate;
        if (!template) return;

        const createBtn = document.getElementById('create-remote-btn');
        if (!createBtn) return;

        if (template.name === '__custom__') {
            const configText = document.getElementById('custom-remote-config')?.value.trim();
            const hasSection = configText && /^\[.+?\]/m.test(configText);
            createBtn.disabled = !hasSection;
            return;
        }

        const remoteName = document.getElementById('remote-name-input')?.value.trim();
        if (!remoteName) {
            createBtn.disabled = true;
            return;
        }

        for (const field of template.fields) {
            const input = document.getElementById(`field-${field.key}`);
            if (!input || !input.value.trim()) {
                createBtn.disabled = true;
                return;
            }
        }

        createBtn.disabled = false;
    }

    /**
     * Toggle password visibility
     * @param {Event} event - Click event from toggle button
     */
    togglePasswordVisibility(event) {
        const button = event.target;
        const fieldId = button.dataset.fieldId;
        const input = document.getElementById(fieldId);

        if (!input) return;

        if (input.type === 'password') {
            input.type = 'text';
            button.textContent = '👁️‍🗨️'; // Eye with lines (hidden state)
            button.title = 'Hide password';
        } else {
            input.type = 'password';
            button.textContent = '👁️'; // Regular eye
            button.title = 'Show password';
        }
    }

    /**
     * Create a new remote
     */
    async createRemote() {
        const template = this.state.selectedTemplate;
        if (!template) return;

        try {
            if (template.name === '__custom__') {
                const configText = document.getElementById('custom-remote-config').value;
                await this.apiCall('/api/remotes', 'POST', {
                    raw_config: configText
                });
            } else {
                const remoteName = document.getElementById('remote-name-input').value.trim();
                const config = { type: template.name };

                template.fields.forEach(field => {
                    const input = document.getElementById(`field-${field.key}`);
                    if (input) {
                        config[field.key] = input.value.trim();
                    }
                });

                await this.apiCall('/api/remotes', 'POST', {
                    name: remoteName,
                    config: config
                });
            }

            this.showRemotesList();
            await this.loadRemotesList();
            await this.onRemotesChanged();
            alert('Remote created successfully');
        } catch (error) {
            alert(`Failed to create remote: ${error.message}`);
        }
    }

    /**
     * View remote configuration
     */
    viewRemoteConfig(remoteName) {
        const remote = this.state.remotes.find(r => r.name === remoteName);
        if (!remote) return;

        this.state.currentViewedRemote = remote;
        const container = document.getElementById('remote-config-content');

        let html = `<h4 style="margin-top: 0; margin-bottom: 15px; color: #333;">${remote.name}</h4>`;
        html += '<div style="background: #f8f9fa; padding: 15px; border-radius: 6px; border: 1px solid #dee2e6;">';
        html += '<table style="width: 100%; border-collapse: collapse;">';

        const configEntries = Object.entries(remote.config);
        const lastIndex = configEntries.length - 1;

        configEntries.forEach(([key, value], index) => {
            const isSensitive = key.toLowerCase().includes('password') ||
                               key.toLowerCase().includes('secret') ||
                               key.toLowerCase().includes('key') ||
                               key.toLowerCase().includes('token');
            const displayValue = isSensitive ? '••••••••' : value;

            const borderStyle = index !== lastIndex ? 'border-bottom: 1px solid #e0e0e0;' : '';
            html += `<tr style="${borderStyle}">`;
            html += `<td style="padding: 8px; font-weight: 500; color: #495057; width: 40%;">${key}</td>`;
            html += `<td style="padding: 8px; color: #212529; font-family: monospace; word-break: break-all;">${displayValue}</td>`;
            html += '</tr>';
        });

        html += '</table></div>';
        container.innerHTML = html;

        this.modalManager.open('view-remote-config-modal', {
            onEscape: () => this.closeViewRemoteConfigModal()
        });

        document.addEventListener('keydown', this.handleViewRemoteConfigKeydown);
    }

    /**
     * Close view remote config modal
     */
    closeViewRemoteConfigModal() {
        document.removeEventListener('keydown', this.handleViewRemoteConfigKeydown);
        this.modalManager.close('view-remote-config-modal');
    }

    /**
     * Handle keydown in view remote config modal
     */
    handleViewRemoteConfigKeydown(event) {
        if ((event.ctrlKey || event.metaKey) && event.key === 'c') {
            const modal = document.getElementById('view-remote-config-modal');
            if (modal.style.display === 'flex') {
                const selection = window.getSelection();
                if (!selection || selection.toString().length === 0) {
                    event.preventDefault();
                    this.copyRemoteConfigToClipboard();
                }
            }
        }
    }

    /**
     * Copy remote config to clipboard
     */
    async copyRemoteConfigToClipboard() {
        const remoteName = this.state.currentViewedRemote?.name;
        if (!remoteName) return;

        try {
            const data = await this.apiCall(`/api/remotes/${encodeURIComponent(remoteName)}/raw`);
            const configText = data.raw_config;

            await navigator.clipboard.writeText(configText);

            const tooltip = document.getElementById('copy-tooltip');
            tooltip.style.display = 'inline';

            setTimeout(() => {
                tooltip.style.display = 'none';
            }, 1000);
        } catch (error) {
            console.error('Failed to copy to clipboard:', error);
            alert('Failed to copy to clipboard');
        }
    }

    /**
     * Edit remote configuration
     */
    async editRemoteConfig(remoteName) {
        try {
            const data = await this.apiCall(`/api/remotes/${encodeURIComponent(remoteName)}/raw`);

            this.state.editingRemote = {
                originalName: remoteName
            };

            document.getElementById('edit-remote-config-text').value = data.raw_config;

            this.modalManager.open('edit-remote-config-modal', {
                onEscape: () => this.closeEditRemoteConfigModal()
            });
        } catch (error) {
            console.error('Error loading remote config:', error);
            alert(`Failed to load remote config: ${error.message}`);
        }
    }

    /**
     * Close edit remote config modal
     */
    closeEditRemoteConfigModal() {
        this.state.editingRemote = null;
        this.modalManager.close('edit-remote-config-modal');
    }

    /**
     * Save remote configuration
     */
    async saveRemoteConfig() {
        if (!this.state.editingRemote) return;

        const configText = document.getElementById('edit-remote-config-text').value;
        const originalName = this.state.editingRemote.originalName;

        try {
            const data = await this.apiCall(`/api/remotes/${encodeURIComponent(originalName)}/raw`, 'PUT', {
                raw_config: configText
            });

            const newName = data.new_name;
            const isRename = newName !== originalName;

            this.closeEditRemoteConfigModal();
            await this.loadRemotesList();
            await this.onRemotesChanged();

            alert(isRename ?
                `Remote successfully renamed from "${originalName}" to "${newName}"` :
                `Remote "${newName}" updated successfully`);
        } catch (error) {
            alert(`Failed to save remote: ${error.message}`);
        }
    }

    /**
     * Delete a remote
     */
    async deleteRemote(remoteName) {
        const activePanes = this.getActivePanes();
        const activeRemotes = new Set();
        if (activePanes.left) activeRemotes.add(activePanes.left);
        if (activePanes.right) activeRemotes.add(activePanes.right);

        if (activeRemotes.has(remoteName)) {
            alert(`Cannot delete remote "${remoteName}" while it is in use. Please select a different remote first.`);
            return;
        }

        if (!confirm(`Are you sure you want to delete the remote "${remoteName}"?`)) {
            return;
        }

        try {
            await this.apiCall(`/api/remotes/${remoteName}`, 'DELETE');
            await this.loadRemotesList();
            await this.onRemotesChanged();
        } catch (error) {
            alert(`Failed to delete remote: ${error.message}`);
        }
    }
}
