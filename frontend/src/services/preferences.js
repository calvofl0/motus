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
 * @param {boolean} preferences.absolute_paths - Absolute paths mode (optional)
 * @param {boolean} preferences.show_tour - Show tour on startup flag (optional)
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
        theme: defaults.theme || 'auto',
        absolute_paths: defaults.absolute_paths,  // undefined means use config default
        show_tour: defaults.show_tour !== undefined ? defaults.show_tour : true
    };

    try {
        const prefs = await apiCall('/api/preferences');
        return {
            view_mode: prefs.view_mode || defaultPrefs.view_mode,
            show_hidden_files: prefs.show_hidden_files !== undefined ? prefs.show_hidden_files : defaultPrefs.show_hidden_files,
            theme: prefs.theme || defaultPrefs.theme,
            absolute_paths: prefs.absolute_paths !== undefined ? prefs.absolute_paths : defaultPrefs.absolute_paths,
            show_tour: prefs.show_tour !== undefined ? prefs.show_tour : defaultPrefs.show_tour
        };
    } catch (error) {
        console.error('Failed to load preferences:', error);
        return defaultPrefs;
    }
}
