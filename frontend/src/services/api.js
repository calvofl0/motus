/**
 * API Communication Helper
 *
 * Provides centralized API call functionality with token-based authentication.
 */

let authToken = '';

/**
 * Set the authentication token
 * @param {string} token - Authentication token
 */
export function setAuthToken(token) {
    authToken = token;
}

/**
 * Get the current authentication token
 * @returns {string} Current auth token
 */
export function getAuthToken() {
    return authToken;
}

/**
 * Clear the authentication token
 */
export function clearAuthToken() {
    authToken = '';
}

/**
 * Check if authentication token is set
 * @returns {boolean} True if token is set
 */
export function isAuthenticated() {
    return authToken !== '';
}

/**
 * Make an authenticated API call
 * @param {string} endpoint - API endpoint path
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {Object} body - Request body (will be JSON stringified)
 * @returns {Promise<Object>} Parsed JSON response
 * @throws {Error} If request fails
 */
export async function apiCall(endpoint, method = 'GET', body = null) {
    if (endpoint.startsWith('/api')) {
      endpoint = `.${endpoint}`;
    }

	const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
        }
    };

    if (authToken) {
        options.headers['Authorization'] = `token ${authToken}`;
    }

    if (body) {
        options.body = JSON.stringify(body);
    }

    const response = await fetch(endpoint, options);
    if (!response.ok) {
        const error = await response.json().catch(() => ({ error: response.statusText }));
        const errorMsg = error.error || `Request failed with status ${response.status}`;
        const err = new Error(errorMsg);
        err.status = response.status;
        err.response = error;
        throw err;
    }
    return response.json();
}
