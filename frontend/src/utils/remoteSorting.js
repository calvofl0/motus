/**
 * Sort remotes with readonly/extra remotes first, then user remotes
 * Within each category, sort alphabetically
 *
 * @param {Array} remotes - Array of remote objects with 'name' and 'is_readonly' properties
 * @returns {Array} Sorted array of remotes
 */
export function sortRemotes(remotes) {
  return [...remotes].sort((a, b) => {
    // First, separate by readonly status (readonly/extra remotes first)
    const aReadonly = a.is_readonly || false
    const bReadonly = b.is_readonly || false

    if (aReadonly !== bReadonly) {
      // Readonly remotes come first
      return bReadonly - aReadonly
    }

    // Within same category, sort alphabetically (case-insensitive)
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })
}
