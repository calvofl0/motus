/**
 * Reusable wizard state management composable
 *
 * Features:
 * - Multi-step navigation with state preservation
 * - Auto-clear dependent steps when earlier steps change
 * - ENTER key to advance, ESC to go back
 * - Generic and reusable for any wizard
 */

import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

export function useWizard(options = {}) {
  const {
    totalSteps = 1,
    onComplete = () => {},
    onCancel = () => {},
  } = options

  // Current step (1-indexed)
  const currentStep = ref(1)

  // Store for each step's data
  const stepData = ref({})

  // Store for each step's validation state
  const stepValid = ref({})

  // Store which steps have been visited
  const visitedSteps = ref(new Set([1]))

  /**
   * Navigate to a specific step
   */
  function goToStep(step) {
    if (step < 1 || step > totalSteps) return
    currentStep.value = step
    visitedSteps.value.add(step)
  }

  /**
   * Go to next step
   */
  function next() {
    if (currentStep.value < totalSteps) {
      goToStep(currentStep.value + 1)
    } else {
      // On last step, call completion handler
      onComplete(stepData.value)
    }
  }

  /**
   * Go to previous step
   */
  function back() {
    if (currentStep.value > 1) {
      goToStep(currentStep.value - 1)
    } else {
      // On first step, cancel the wizard
      onCancel()
    }
  }

  /**
   * Set data for a specific step
   * @param {number} step - Step number
   * @param {any} data - Data to store
   * @param {boolean} clearNext - Whether to clear subsequent steps
   */
  function setStepData(step, data, clearNext = true) {
    stepData.value[step] = data

    // Clear data from subsequent steps if requested
    if (clearNext) {
      for (let i = step + 1; i <= totalSteps; i++) {
        delete stepData.value[i]
        delete stepValid.value[i]
      }
    }
  }

  /**
   * Get data for a specific step
   * @param {number} step - Step number
   * @returns {any} Step data
   */
  function getStepData(step) {
    return stepData.value[step]
  }

  /**
   * Set validation state for a step
   * @param {number} step - Step number
   * @param {boolean} valid - Whether the step is valid
   */
  function setStepValid(step, valid) {
    stepValid.value[step] = valid
  }

  /**
   * Check if current step is valid
   */
  const isCurrentStepValid = computed(() => {
    return stepValid.value[currentStep.value] === true
  })

  /**
   * Check if on first step
   */
  const isFirstStep = computed(() => currentStep.value === 1)

  /**
   * Check if on last step
   */
  const isLastStep = computed(() => currentStep.value === totalSteps)

  /**
   * Reset wizard to initial state
   */
  function reset() {
    currentStep.value = 1
    stepData.value = {}
    stepValid.value = {}
    visitedSteps.value = new Set([1])
  }

  /**
   * Handle keyboard shortcuts
   * ENTER = next (if valid)
   * ESC = back/cancel
   */
  function handleKeyDown(event) {
    // Only handle if not typing in an input
    const target = event.target
    const isInputField = target.tagName === 'INPUT' ||
                        target.tagName === 'TEXTAREA' ||
                        target.isContentEditable

    if (event.key === 'Escape') {
      event.preventDefault()
      back()
    } else if (event.key === 'Enter' && !isInputField) {
      // Only advance on ENTER if not in an input field
      // Input fields should handle ENTER themselves
      if (isCurrentStepValid.value) {
        event.preventDefault()
        next()
      }
    }
  }

  // Setup keyboard listener
  onMounted(() => {
    // Note: Individual input fields should handle their own ENTER logic
    // This is just for the general wizard navigation
  })

  onUnmounted(() => {
    // Cleanup if needed
  })

  return {
    // State
    currentStep,
    stepData: computed(() => stepData.value),
    isFirstStep,
    isLastStep,
    isCurrentStepValid,

    // Methods
    goToStep,
    next,
    back,
    setStepData,
    getStepData,
    setStepValid,
    reset,
    handleKeyDown,
  }
}
