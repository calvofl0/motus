/**
 * Utility Helper Functions
 *
 * Collection of pure utility functions for file operations,
 * formatting, and path manipulation.
 */

/**
 * Build a file path by joining base path and filename
 * @param {string} basePath - The base directory path
 * @param {string} filename - The filename to append
 * @returns {string} The joined path
 */
export function buildPath(basePath, filename) {
    // Normalize path to avoid double slashes
    const normalized = basePath.endsWith('/') ? basePath.slice(0, -1) : basePath;
    return `${normalized}/${filename}`;
}

/**
 * Sort files with directories first, then by specified field
 * @param {Array} files - Array of file objects
 * @param {string} sortBy - Field to sort by ('name', 'size', 'date')
 * @param {boolean} sortAsc - Sort ascending if true, descending if false
 * @returns {Array} Sorted array of files
 */
export function sortFiles(files, sortBy, sortAsc) {
    const sorted = [...files];
    sorted.sort((a, b) => {
        // Directories first
        if (a.IsDir !== b.IsDir) {
            return a.IsDir ? -1 : 1;
        }

        let comparison = 0;
        if (sortBy === 'name') {
            comparison = a.Name.localeCompare(b.Name);
        } else if (sortBy === 'size') {
            comparison = (a.Size || 0) - (b.Size || 0);
        } else if (sortBy === 'date') {
            const dateA = new Date(a.ModTime || 0);
            const dateB = new Date(b.ModTime || 0);
            comparison = dateA - dateB;
        }

        return sortAsc ? comparison : -comparison;
    });
    return sorted;
}

/**
 * Format bytes into human-readable file size
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size string (e.g., "1.5 MB")
 */
export function formatFileSize(bytes) {
    if (bytes === undefined || bytes === null || bytes < 0) return '';
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`;
}

/**
 * Format date string into localized date and time
 * @param {string} dateStr - ISO date string
 * @returns {string} Formatted date string
 */
export function formatFileDate(dateStr) {
    if (!dateStr) return '';
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});
}

/**
 * Expand tilde in path (backend handles actual expansion)
 * @param {string} path - Path that may contain ~
 * @returns {string} Path (returned as-is, backend expands)
 */
export function expandTildePath(path) {
    // Expand ~ to home directory (platform-aware)
    // Send as-is, backend should handle ~ expansion via os.path.expanduser
    return path;
}

/**
 * Resolve relative path against base path
 * @param {string} basePath - Base directory path
 * @param {string} relativePath - Relative or absolute path
 * @returns {string} Resolved absolute path
 */
export function resolveRelativePath(basePath, relativePath) {
    // If relative path starts with /, it's absolute
    if (relativePath.startsWith('/')) {
        return relativePath;
    }
    // Otherwise, join with base path
    const base = basePath.endsWith('/') ? basePath : basePath + '/';
    return base + relativePath;
}
