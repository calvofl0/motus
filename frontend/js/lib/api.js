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
 * Make an authenticated API call
 * @param {string} endpoint - API endpoint path
 * @param {string} method - HTTP method (GET, POST, PUT, DELETE)
 * @param {Object} body - Request body (will be JSON stringified)
 * @returns {Promise<Object>} Parsed JSON response
 * @throws {Error} If request fails
 */
export async function apiCall(endpoint, method = 'GET', body = null) {
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
        throw new Error(error.error || 'Request failed');
    }
    return response.json();
}
