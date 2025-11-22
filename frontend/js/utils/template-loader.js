/**
 * Template Loader Utility
 *
 * Loads HTML templates from separate files and injects them into the DOM.
 */

/**
 * Load an HTML template file and return its content
 * @param {string} path - Path to the template file
 * @returns {Promise<string>} The HTML content
 */
async function loadTemplate(path) {
    try {
        const response = await fetch(path);
        if (!response.ok) {
            throw new Error(`Failed to load template: ${path} (${response.status})`);
        }
        return await response.text();
    } catch (error) {
        console.error(`Error loading template ${path}:`, error);
        throw error;
    }
}

/**
 * Load an HTML template and inject it into a target element
 * @param {string} path - Path to the template file
 * @param {string} targetSelector - CSS selector for the target element
 * @param {string} position - Where to insert: 'beforeend', 'afterbegin', 'beforebegin', 'afterend'
 */
export async function loadTemplateInto(path, targetSelector, position = 'beforeend') {
    const content = await loadTemplate(path);
    const target = document.querySelector(targetSelector);

    if (!target) {
        throw new Error(`Target element not found: ${targetSelector}`);
    }

    target.insertAdjacentHTML(position, content);
}

/**
 * Load multiple templates in parallel
 * @param {Array<{path: string, target: string, position?: string}>} templates
 */
export async function loadTemplates(templates) {
    const promises = templates.map(({ path, target, position }) =>
        loadTemplateInto(path, target, position)
    );

    await Promise.all(promises);
}

/**
 * Load a template and return it as a DOM element
 * @param {string} path - Path to the template file
 * @returns {Promise<HTMLElement>} The template as a DOM element
 */
export async function loadTemplateAsElement(path) {
    const content = await loadTemplate(path);
    const template = document.createElement('template');
    template.innerHTML = content.trim();
    return template.content.firstChild;
}
