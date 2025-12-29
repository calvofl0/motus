/**
 * Guided Tour Service for Motus
 * Uses Driver.js for step-by-step user onboarding
 */
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { useAppStore } from '../stores/app'

/**
 * Check if tour is disabled (should not auto-show on startup)
 */
export async function isTourDisabled() {
  const appStore = useAppStore()
  const showTour = await appStore.getPreference('show_tour')
  return showTour === false
}

/**
 * Disable tour auto-show on startup
 */
export async function disableTour() {
  const appStore = useAppStore()
  await appStore.setPreference('show_tour', false)
}

/**
 * Enable tour auto-show on startup
 */
export async function enableTour() {
  const appStore = useAppStore()
  await appStore.setPreference('show_tour', true)
}

/**
 * Reset tour preferences (for testing/debugging)
 */
export async function resetTourPreferences() {
  const appStore = useAppStore()
  await appStore.setPreference('show_tour', true)
}

/**
 * Get tour steps configuration
 * @param {Object} appStore - Pinia app store for programmatic menu control
 * @param {boolean} noTourConfig - Whether --no-tour flag is set (hides checkbox if true)
 * @returns {Array} Array of tour step configurations
 */
export function getTourSteps(appStore, noTourConfig = false) {
  // Context menu HTML for Steps 7 & 8
  const contextMenuHtml = `
<div style="margin-top: 15px; background: var(--color-bg-white); border: 1px solid var(--color-border-darker); border-radius: 6px; overflow: hidden; font-size: 14px;">
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">⬇️ Download</div>
  <div id="tour-alias-item" style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">🔗 Create Alias</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">📁 Create Folder</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">✏️ Rename</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">🗑️ Delete</div>
  <div style="padding: 10px 16px; color: var(--color-text-primary);">📊 Sort by</div>
</div>`

  return [
    // Step 1: Welcome
    {
      popover: {
        title: 'Welcome to Motus!',
        description: 'Motus is a user-friendly interface for rclone that makes file operations between different storage locations easy and intuitive. Whether you\'re working with cloud storage like Dropbox or Google Drive, or transferring files between servers, Motus simplifies the process. Let\'s take a quick tour!',
        side: 'center',
        align: 'center',
        showButtons: ['next'], // Only show Next button
        popoverClass: 'tour-center-popover',
      },
    },

    // Step 2: Left File Pane
    {
      element: '.pane.left-pane',
      popover: {
        title: 'Source File Pane',
        description: 'This is your source file browser. Navigate through folders by double-clicking on them. You can browse different storage locations configured in your system.',
        side: 'right',
      },
    },

    // Step 3: Remote Dropdown & Path Field
    {
      element: '.left-pane .pane-toolbar',
      popover: {
        title: 'Storage Selection and Navigation',
        description: 'The top dropdown (called the <em><strong>remotes dropdown</strong></em>) switches between different storage locations - cloud services, servers, or local filesystem. Below it, the path field lets you navigate to specific folders by typing a path and pressing Enter.',
        side: 'bottom',
      },
    },

    // Step 4: Right File Pane
    {
      element: '.pane.right-pane',
      popover: {
        title: 'Destination File Pane',
        description: 'This is your destination file browser. Select where you want to copy or move files. The left and right panes work symmetrically - you can transfer files in either direction.',
        side: 'left',
      },
    },

    // Step 5: Drag & Drop (Left to Right)
    {
      element: '.right-pane .file-list',
      popover: {
        title: 'Drag & Drop Transfer',
        description: 'Simply drag files or folders from the left pane and drop them here to start a copy operation. You can also drag and drop files directly from your desktop! Select multiple files by holding Ctrl while clicking, or Shift to select a range of consecutive files.',
        side: 'top',
      },
    },

    // Step 6: Copy Button (Arrow buttons)
    {
      element: '.arrow-buttons .arrow-button:first-child',
      popover: {
        title: 'Copy with Buttons',
        description: 'You can also use the arrow buttons to copy files. Select files in one pane and click the corresponding arrow button to copy them to the other side.',
        side: 'top',
      },
    },

    // Step 7: Context Menu (with real menu in popover)
    {
      popover: {
        title: 'Context Menu Actions',
        description: `Right-click on any file or folder in either pane to access these actions. You can download files, create new folders, rename, delete, and sort files.

${contextMenuHtml}`,
        side: 'center',
        align: 'center',
        popoverClass: 'tour-center-popover',
      },
    },

    // Step 8: New Alias Feature (with highlighted "Create Alias")
    {
      popover: {
        title: 'Create Aliases for Quick Access',
        description: `Here's a powerful feature: right-click on any folder and select <em>Create Alias</em> to create a shortcut to that specific folder. Once created, the alias appears in your <em>remotes dropdown</em> as if it were a separate location, giving you instant access to frequently used folders without navigating through the entire directory tree.

<div style="margin-top: 15px; background: var(--color-bg-white); border: 1px solid var(--color-border-darker); border-radius: 6px; overflow: hidden; font-size: 14px;">
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">⬇️ Download</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); background: var(--color-bg-primary-light); font-weight: bold; color: var(--color-text-primary);">🔗 Create Alias</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">📁 Create Folder</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">✏️ Rename</div>
  <div style="padding: 10px 16px; border-bottom: 1px solid var(--color-border-lighter); color: var(--color-text-primary);">🗑️ Delete</div>
  <div style="padding: 10px 16px; color: var(--color-text-primary);">📊 Sort by</div>
</div>`,
        side: 'center',
        align: 'center',
        popoverClass: 'tour-center-popover',
      },
    },

    // Step 9: View Menu (highlighted)
    {
      element: '.view-dropdown-container',
      popover: {
        title: 'View Options',
        description: 'Click <em>View</em> to customize what you see in the file panes: toggle between list and grid layouts, show or hide hidden files, and switch between relative and absolute path display.',
        side: 'bottom',
      },
    },

    // Step 10: Path Display Mode (with open View menu and highlighted toggle)
    {
      element: '.view-dropdown-container .view-menu-item:nth-child(3)',
      popover: {
        title: 'Path Display Toggle',
        description: 'This toggle controls how folder paths are shown in the path field. In relative mode, you see paths relative to your current location. In absolute mode, you see the complete path from the root - especially useful when working with aliases, as it reveals the full path within the original storage location that the alias points to.',
        side: 'bottom',
      },
      onHighlightStarted: () => {
        // Programmatically open View menu
        const viewButton = document.querySelector('.view-toggle-button')
        if (viewButton) {
          viewButton.click()
        }
      },
      onDeselected: () => {
        // Close View menu if it's open
        const viewMenu = document.querySelector('.view-dropdown-menu')
        if (viewMenu && !viewMenu.classList.contains('hidden')) {
          const viewButton = document.querySelector('.view-toggle-button')
          if (viewButton) {
            viewButton.click()
          }
        }
      },
    },

    // Step 11: Job Panel
    {
      element: '.job-panel',
      popover: {
        title: 'Active Jobs Panel',
        description: 'Monitor your file operations in real-time. See progress, transfer speed, and estimated time remaining. You can cancel running jobs if needed. Important: The Motus server continues processing active jobs even when you close the browser tab or switch off your laptop/desktop—jobs run on the server, not in your browser.',
        side: 'top',
      },
    },

    // Step 12: Interrupted/Failed Jobs
    {
      element: '.job-panel',
      popover: {
        title: 'Resume Failed Operations',
        description: `Below the Active Jobs panel, interrupted or failed jobs appear in dropdowns for easy resuming:

<div style="margin-top: 15px;">
  <div style="background: var(--color-warning-lighter); padding: 10px; border-radius: 6px; margin-bottom: 8px; border: 1px solid var(--color-warning);">
    <strong style="color: var(--color-text-primary);">⚠️ Interrupted Jobs (2) ▼</strong>
    <div style="font-size: 12px; margin-top: 5px; color: var(--color-text-secondary);">Jobs stopped by server shutdown - click to resume</div>
  </div>
  <div style="background: var(--color-danger-light); padding: 10px; border-radius: 6px; border: 1px solid var(--color-danger);">
    <strong style="color: var(--color-text-primary);">❌ Failed Jobs (1) ▼</strong>
    <div style="font-size: 12px; margin-top: 5px; color: var(--color-text-secondary);">Jobs that encountered errors - click to view logs or retry</div>
  </div>
</div>`,
        side: 'top',
      },
    },

    // Step 13: Manage Remotes (highlight button)
    {
      element: '.manage-remotes-button',
      popover: {
        title: 'Managing Remotes',
        description: 'Click <em>Manage Remotes</em> in the header to add, edit, or remove storage providers. Motus supports all rclone-compatible services including Dropbox, Google Drive, Amazon S3, and many more.',
        side: 'bottom',
      },
    },

    // Step 14: Completed Jobs
    {
      element: '.completed-jobs-button',
      popover: {
        title: 'Successfully Completed Jobs History',
        description: 'View your successfully completed file operations, including statistics, timing, and any errors that occurred. Great for auditing and troubleshooting.',
        side: 'bottom',
        // Mark tour as completed when moving from step 14 to step 15
        // This will be set in startGuidedTour() where tourCompleted variable is accessible
      },
    },

    // Step 15: Finale & Help
    {
      popover: {
        title: 'You\'re All Set!',
        description: 'You\'ve completed the tour! If you need help or want to see this tour again, click the <em>Help</em> menu in the header. Enjoy using Motus!',
        side: 'center',
        align: 'center',
        doneBtnText: 'Finish',
        showButtons: ['previous', 'next'], // Previous and Finish (next) buttons
        popoverClass: 'tour-center-popover',
        // Checkbox is now added by global onPopoverRender
        // onNextClick and onCloseClick will be set in startGuidedTour() where driverObj is available
      },
    },
  ]
}

/**
 * Show tour exit information dialog
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @param {boolean} currentShowTourValue - Current value of show_tour preference
 * @param {boolean} tourCompleted - Whether user completed the tour
 * @returns {Promise<boolean>} True if user wants to disable auto-show
 */
export function showTourExitDialog(noTourConfig, currentShowTourValue = true, tourCompleted = false) {
  return new Promise((resolve) => {
    // Create modal overlay
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay tour-exit-overlay'

    // Create modal
    const modal = document.createElement('div')
    modal.className = 'tour-exit-modal'

    // Build modal content
    const title = document.createElement('h3')
    title.textContent = 'Guided Tour'

    const message = document.createElement('p')
    message.textContent = 'You can restart the guided tour anytime from the Help menu in the header.'

    // Checkbox (only if --no-tour is not set)
    let checkbox = null
    if (!noTourConfig) {
      checkbox = document.createElement('label')
      checkbox.className = 'tour-exit-checkbox'
      // Checkbox is checked if tour was completed OR show_tour is currently false
      const isChecked = tourCompleted || !currentShowTourValue
      checkbox.innerHTML = `
        <input type="checkbox" id="tour-exit-no-show" ${isChecked ? 'checked' : ''}>
        Don't show this tour automatically on startup
      `
    }

    // OK Button
    const buttonContainer = document.createElement('div')
    buttonContainer.className = 'tour-exit-buttons'

    const okBtn = document.createElement('button')
    okBtn.textContent = 'OK'
    okBtn.className = 'btn btn-primary'
    okBtn.onclick = () => {
      const dontShowAgain = checkbox ? checkbox.querySelector('input').checked : false
      document.body.removeChild(overlay)
      resolve(dontShowAgain)
    }

    buttonContainer.appendChild(okBtn)

    modal.appendChild(title)
    modal.appendChild(message)
    if (checkbox) {
      modal.appendChild(checkbox)
    }
    modal.appendChild(buttonContainer)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    // Focus the OK button for keyboard interaction
    setTimeout(() => okBtn.focus(), 0)

    // Allow ESC and ENTER to close
    const keyHandler = (e) => {
      if (e.key === 'Escape' || e.key === 'Enter') {
        e.preventDefault()
        e.stopPropagation()
        document.removeEventListener('keydown', keyHandler)
        if (document.body.contains(overlay)) {
          const dontShowAgain = checkbox ? checkbox.querySelector('input').checked : false
          document.body.removeChild(overlay)
          resolve(dontShowAgain)
        }
      }
    }
    document.addEventListener('keydown', keyHandler, true)
  })
}

/**
 * Start the guided tour
 * @param {Object} appStore - Pinia app store
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @returns {Promise<void>} Resolves when tour is completed or cancelled
 */
export function startGuidedTour(appStore, noTourConfig = false) {
  return new Promise(async (resolveTour) => {
    const steps = getTourSteps(appStore, noTourConfig)
    let tourActive = true
    let currentStepIndex = 0
    let tourCompleted = false

    // Helper function to save preference based on checkbox
    const savePreferenceFromCheckbox = async () => {
      if (!noTourConfig) {
        const checkboxInput = document.querySelector('#tour-no-show-again')
        if (checkboxInput) {
          if (checkboxInput.checked) {
            await disableTour()
          } else {
            await enableTour()
          }
        }
      }
    }

    // Create driver object (we'll need reference for hooks)
    let driverObj = null

    // Add onNextClick hook to Step 14's popover (mark tour as completed when user has seen everything)
    const step14 = steps[steps.length - 2]
    step14.popover.onNextClick = () => {
      tourCompleted = true
      // Continue to next step normally
      driverObj.moveNext()
    }

    // Add onNextClick hook to Step 15's popover (for Finish button)
    const step15 = steps[steps.length - 1]
    step15.popover.onNextClick = async () => {
      await savePreferenceFromCheckbox()
      // tourCompleted already set in step 14
      // Call moveNext() to follow driver.js's proper flow
      // On last step, moveNext() will destroy the tour
      driverObj.moveNext()
    }
    // Note: X button is handled in onPopoverRender's custom button onclick

    driverObj = driver({
      showProgress: true,
      steps: steps,
      nextBtnText: 'Next',
      prevBtnText: 'Previous',
      doneBtnText: 'Finish',
      allowClose: false, // Disable default X button, use custom handling
      onPopoverRender: (popover, { config, state }) => {
        currentStepIndex = state.activeIndex || 0

        // Focus the Next button for better keyboard navigation
        setTimeout(() => {
          const nextBtn = popover.nextButton
          if (nextBtn && !nextBtn.disabled) {
            nextBtn.focus()
          }
        }, 0)

        // Add custom cancel button (X) for all steps
        const cancelBtn = document.createElement('button')
        cancelBtn.textContent = '×'
        cancelBtn.className = 'tour-custom-close-btn'
        cancelBtn.onclick = async () => {
          // On last step, save preference before destroying
          if (currentStepIndex === steps.length - 1) {
            await savePreferenceFromCheckbox()
          }
          tourActive = false
          driverObj.destroy()
        }
        popover.wrapper.appendChild(cancelBtn)

        // Add checkbox on Step 15 (last step)
        if (currentStepIndex === steps.length - 1 && !noTourConfig) {
          const checkbox = document.createElement('label')
          checkbox.className = 'tour-step-checkbox'
          checkbox.innerHTML = `
            <input type="checkbox" id="tour-no-show-again" checked>
            Don't show this tour again on startup
          `
          popover.wrapper.querySelector('.driver-popover-description')?.parentNode.appendChild(checkbox)
        }
      },
      onDestroyed: async () => {
        // Clean up exit overlay if exists
        const overlay = document.querySelector('.tour-exit-overlay')
        if (overlay) {
          overlay.remove()
        }

        tourActive = false

        // Show exit dialog if user didn't reach last step
        const reachedLastStep = currentStepIndex === steps.length - 1
        if (!reachedLastStep) {
          try {
            // Get current preference value to show in checkbox
            const appStore = useAppStore()
            const currentShowTour = await appStore.getPreference('show_tour') !== false

            const disableAutoShow = await showTourExitDialog(noTourConfig, currentShowTour, tourCompleted)
            if (disableAutoShow) {
              await disableTour()
            } else {
              await enableTour()
            }
          } catch (error) {
            console.error('[Tour] Error showing exit dialog:', error)
          }
        }

        // Resolve the Promise now (after dialog if shown)
        resolveTour()
      },
    })

    // Add global ESC handler for tour
    const globalEscHandler = (e) => {
      if (e.key === 'Escape' && tourActive) {
        // Check if exit dialog is already open
        if (document.querySelector('.tour-exit-overlay')) {
          return
        }

        e.stopPropagation()
        e.preventDefault()

        tourActive = false
        driverObj.destroy()
      }
    }

    // Use capture phase to intercept ESC before other handlers
    document.addEventListener('keydown', globalEscHandler, true)

    // Clean up listener when tour ends
    const originalDestroy = driverObj.destroy.bind(driverObj)
    driverObj.destroy = () => {
      tourActive = false
      document.removeEventListener('keydown', globalEscHandler, true)
      originalDestroy()
    }

    driverObj.drive()
  })
}
