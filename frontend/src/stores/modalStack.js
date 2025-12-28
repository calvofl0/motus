import { defineStore } from 'pinia'
import { ref } from 'vue'

/**
 * Modal Stack Store
 *
 * Manages a stack of active modals to ensure keyboard events and interactions
 * are only handled by the topmost (currently visible) modal.
 *
 * This eliminates the need for manual child modal tracking and provides a
 * centralized, automatic way to manage modal hierarchy.
 */
export const useModalStack = defineStore('modalStack', () => {
  // Stack of modal IDs (LIFO - Last In, First Out)
  // The last item in the array is the topmost (active) modal
  const stack = ref([])

  /**
   * Push a modal onto the stack (modal opened)
   * @param {Symbol|String} id - Unique identifier for the modal
   */
  const pushModal = (id) => {
    stack.value.push(id)
  }

  /**
   * Remove a modal from the stack (modal closed)
   * Removes the last occurrence of the given ID
   * @param {Symbol|String} id - Unique identifier for the modal
   */
  const popModal = (id) => {
    const index = stack.value.lastIndexOf(id)
    if (index !== -1) {
      stack.value.splice(index, 1)
    }
  }

  /**
   * Check if a modal is the topmost (active) modal
   * @param {Symbol|String} id - Unique identifier for the modal
   * @returns {Boolean} - True if this modal is on top of the stack
   */
  const isTopModal = (id) => {
    return stack.value.length > 0 && stack.value[stack.value.length - 1] === id
  }

  /**
   * Get the current stack (for debugging)
   * @returns {Array} - Current modal stack
   */
  const getStack = () => {
    return [...stack.value]
  }

  return {
    pushModal,
    popModal,
    isTopModal,
    getStack
  }
})
