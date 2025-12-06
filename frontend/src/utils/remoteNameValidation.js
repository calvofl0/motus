/**
 * Validate remote name according to rclone rules:
 * - May contain number, letter, _, -, ., +, @ and space
 * - May not start with - or space
 * - May not end with space
 *
 * @param {string} name - The remote name to validate
 * @returns {{isValid: boolean, error: string|null}} - Validation result
 */
export function validateRemoteName(name) {
  if (!name) {
    return { isValid: false, error: 'Remote name cannot be empty' }
  }

  // Check if starts with - or space
  if (name[0] === '-' || name[0] === ' ') {
    return { isValid: false, error: 'Remote name cannot start with \'-\' or space' }
  }

  // Check if ends with space
  if (name[name.length - 1] === ' ') {
    return { isValid: false, error: 'Remote name cannot end with space' }
  }

  // Check valid characters: letters, numbers, _, -, ., +, @, space
  const validCharsRegex = /^[a-zA-Z0-9_\-\.+@ ]+$/
  if (!validCharsRegex.test(name)) {
    return { isValid: false, error: 'Remote name may only contain letters, numbers, _, -, ., +, @ and space' }
  }

  return { isValid: true, error: null }
}
