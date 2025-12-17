/**
 * Sort remotes with readonly/extra remotes first (in original order), then user remotes
 *
 * Readonly/extra remotes (from --extra-remotes config) are shown first in their original
 * order from the config file. User remotes are shown second, sorted alphabetically.
 *
 * @param {Array} remotes - Array of remote objects with 'name' and 'is_readonly' properties
 * @returns {Array} Sorted array of remotes
 */
export function sortRemotes(remotes) {
  // Separate into two groups
  const readonlyRemotes = []
  const userRemotes = []

  for (const remote of remotes) {
    if (remote.is_readonly) {
      readonlyRemotes.push(remote)
    } else {
      userRemotes.push(remote)
    }
  }

  // Keep readonly remotes in original order (as they appear in the extra config file)
  // Sort user remotes alphabetically (case-insensitive)
  userRemotes.sort((a, b) => {
    return a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
  })

  // Return readonly first (in original order), then user (alphabetically)
  return [...readonlyRemotes, ...userRemotes]
}
