/**
 * User Preferences Management
 *
 * Handles saving and loading user preferences to/from the backend.
 */

/**
 * Save user preferences to backend
 * @param {Function} apiCall - API call function
 * @param {Object} preferences - Preferences object
 * @param {string} preferences.view_mode - View mode ('grid' or 'list')
 * @param {boolean} preferences.show_hidden_files - Show hidden files flag
 * @param {string} preferences.theme - Theme ('auto', 'light', or 'dark')
 * @returns {Promise<void>}
 */
export async function savePreferences(apiCall, preferences) {
    try {
        await apiCall('/api/preferences', 'POST', preferences);
    } catch (error) {
        console.error('Failed to save preferences:', error);
    }
}

/**
 * Load user preferences from backend
 * @param {Function} apiCall - API call function
 * @param {Object} defaults - Default preferences (optional)
 * @returns {Promise<Object>} Preferences object
 */
export async function loadPreferences(apiCall, defaults = {}) {
    const defaultPrefs = {
        view_mode: defaults.view_mode || 'list',
        show_hidden_files: defaults.show_hidden_files !== undefined ? defaults.show_hidden_files : false,
        theme: defaults.theme || 'auto'
    };

    try {
        const prefs = await apiCall('/api/preferences');
        return {
            view_mode: prefs.view_mode || defaultPrefs.view_mode,
            show_hidden_files: prefs.show_hidden_files !== undefined ? prefs.show_hidden_files : defaultPrefs.show_hidden_files,
            theme: prefs.theme || defaultPrefs.theme
        };
    } catch (error) {
        console.error('Failed to load preferences:', error);
        return defaultPrefs;
    }
}
