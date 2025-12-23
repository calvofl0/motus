import { ref } from 'vue'

/**
 * Reusable composable for copying text to clipboard with visual feedback
 *
 * @param {number} tooltipDuration - How long to show the "Copied!" tooltip (ms)
 * @returns {Object} - { copyToClipboard, showCopyTooltip }
 *
 * Usage:
 * const { copyToClipboard, showCopyTooltip } = useClipboard()
 * await copyToClipboard('text to copy')
 */
export function useClipboard(tooltipDuration = 1000) {
  const showCopyTooltip = ref(false)

  /**
   * Copy text to clipboard with fallback for older browsers
   * Shows tooltip on success
   *
   * @param {string} text - Text to copy
   * @throws {Error} - If copy fails
   */
  async function copyToClipboard(text) {
    if (!text) {
      throw new Error('No text provided to copy')
    }

    try {
      // Modern clipboard API
      await navigator.clipboard.writeText(text)

      // Show tooltip feedback
      showCopyTooltip.value = true
      setTimeout(() => {
        showCopyTooltip.value = false
      }, tooltipDuration)
    } catch (error) {
      console.error('Failed to copy with clipboard API:', error)

      // Fallback for older browsers
      try {
        const textarea = document.createElement('textarea')
        textarea.value = text
        textarea.style.position = 'fixed'
        textarea.style.opacity = '0'
        textarea.style.pointerEvents = 'none'
        document.body.appendChild(textarea)
        textarea.select()
        const success = document.execCommand('copy')
        document.body.removeChild(textarea)

        if (success) {
          // Show tooltip feedback
          showCopyTooltip.value = true
          setTimeout(() => {
            showCopyTooltip.value = false
          }, tooltipDuration)
        } else {
          throw new Error('execCommand copy failed')
        }
      } catch (fallbackError) {
        console.error('Fallback copy also failed:', fallbackError)
        throw new Error('Failed to copy to clipboard')
      }
    }
  }

  return {
    copyToClipboard,
    showCopyTooltip
  }
}
