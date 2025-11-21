/**
 * Modal Management System
 *
 * Centralized modal manager for handling modal stacking and keyboard shortcuts.
 * Provides a clean API for opening/closing modals with automatic focus management
 * and keyboard event handling.
 */

export const ModalManager = {
    stack: [],      // Stack of open modal IDs (last = topmost)
    handlers: {},   // Map of modalId -> {onEscape, onEnter, onClose}

    /**
     * Open a modal and register keyboard handlers
     * @param {string} modalId - ID of the modal element
     * @param {Object} options - Handler options
     * @param {Function} options.onEscape - Handler for ESC key (if not provided, closes modal by default)
     * @param {Function} options.onEnter - Handler for ENTER key (optional)
     * @param {Function} options.onClose - Additional cleanup when modal closes (optional)
     */
    open(modalId, options = {}) {
        // Add to stack if not already there
        if (!this.stack.includes(modalId)) {
            this.stack.push(modalId);
        }

        // Store handlers
        this.handlers[modalId] = {
            onEscape: options.onEscape || null,
            onEnter: options.onEnter || null,
            onClose: options.onClose || null,
        };

        // Show the modal
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'flex';

            // Auto-focus the first input/textarea/select field
            setTimeout(() => {
                const firstInput = modal.querySelector('input:not([type="hidden"]), textarea, select');
                if (firstInput) {
                    firstInput.focus();
                }
            }, 100); // Small delay to ensure modal is rendered
        }
    },

    /**
     * Close a modal and clean up handlers
     * @param {string} modalId - ID of the modal to close
     */
    close(modalId) {
        // Call onClose handler if registered
        const handler = this.handlers[modalId];
        if (handler && handler.onClose) {
            handler.onClose();
        }

        // Remove from stack
        const index = this.stack.indexOf(modalId);
        if (index > -1) {
            this.stack.splice(index, 1);
        }

        // Remove handlers
        delete this.handlers[modalId];

        // Hide the modal
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    },

    /**
     * Get the topmost (currently active) modal
     * @returns {string|null} Modal ID or null if no modals open
     */
    getTopModal() {
        return this.stack.length > 0 ? this.stack[this.stack.length - 1] : null;
    },

    /**
     * Check if focus is currently in a form field (to avoid interfering with typing)
     * @returns {boolean} True if focus is in input/textarea/select
     */
    isFocusInFormField() {
        const activeElement = document.activeElement;
        return activeElement && (
            activeElement.tagName === 'INPUT' ||
            activeElement.tagName === 'TEXTAREA' ||
            activeElement.tagName === 'SELECT'
        );
    },

    /**
     * Handle keydown events for the topmost modal
     * @param {KeyboardEvent} event - The keyboard event
     */
    handleKeyDown(event) {
        const topModalId = this.getTopModal();
        if (!topModalId) return;

        const handler = this.handlers[topModalId];
        if (!handler) return;

        const inFormField = this.isFocusInFormField();

        // ESC key - close or custom handler
        if (event.key === 'Escape') {
            event.preventDefault();
            event.stopPropagation();

            if (handler.onEscape) {
                handler.onEscape();
            } else {
                // Default: close the modal
                this.close(topModalId);
            }
        }
        // ENTER key - only if not in textarea (allow newlines in textarea)
        else if (event.key === 'Enter' && handler.onEnter) {
            // In single-line input: trigger submit
            // In textarea: allow default (newline)
            // Not in form field: trigger submit
            if (!inFormField || (document.activeElement.tagName === 'INPUT')) {
                event.preventDefault();
                event.stopPropagation();
                handler.onEnter();
            }
        }
    }
};

/**
 * Initialize the modal manager's global keyboard handler
 * Call this once when the application loads
 */
export function initModalManager() {
    document.addEventListener('keydown', (e) => ModalManager.handleKeyDown(e), true);
}
