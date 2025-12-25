/**
 * Guided Tour Service for Motus
 * Uses Driver.js for step-by-step user onboarding
 */
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'

/**
 * Check if tour has been completed
 */
export function isTourCompleted() {
  return localStorage.getItem('motus-tour-completed') === 'true'
}

/**
 * Mark tour as completed
 */
export function markTourCompleted() {
  localStorage.setItem('motus-tour-completed', 'true')
}

/**
 * Check if tour auto-show is disabled
 */
export function isTourAutoShowDisabled() {
  return localStorage.getItem('motus-tour-auto-show') === 'false'
}

/**
 * Disable tour auto-show
 */
export function disableTourAutoShow() {
  localStorage.setItem('motus-tour-auto-show', 'false')
}

/**
 * Reset tour preferences (for testing/debugging)
 */
export function resetTourPreferences() {
  localStorage.removeItem('motus-tour-completed')
  localStorage.removeItem('motus-tour-auto-show')
}

/**
 * Get tour steps configuration
 * @param {Object} appStore - Pinia app store for programmatic menu control
 * @param {boolean} noTourConfig - Whether --no-tour flag is set (hides checkbox if true)
 * @returns {Array} Array of tour step configurations
 */
export function getTourSteps(appStore, noTourConfig = false) {
  return [
    // Step 1: Welcome
    {
      popover: {
        title: 'Welcome to Motus!',
        description: 'Motus is a user-friendly interface for rclone that makes file operations between different storage locations easy and intuitive. Whether you\'re working with cloud storage like Dropbox or Google Drive, or transferring files between servers, Motus simplifies the process. Let\'s take a quick tour!',
        side: 'center',
        align: 'center',
        showButtons: ['next'], // Only show Next button
      },
    },

    // Step 2: Left File Pane
    {
      element: '.easy-mode-container .file-pane:first-child',
      popover: {
        title: 'Source File Pane',
        description: 'This is your source file browser. Navigate through folders by double-clicking on them. You can browse different storage locations configured in your system.',
        side: 'right',
      },
    },

    // Step 3: Remote Dropdown (Left)
    {
      element: '.easy-mode-container .file-pane:first-child select.remote-selector',
      popover: {
        title: 'Select Remote',
        description: 'Switch between different storage locations (called "remotes") using this dropdown. Choose from any configured storage service or file system. Later on we\'ll simply call them "storage locations".',
        side: 'bottom',
      },
    },

    // Step 4: Right File Pane
    {
      element: '.easy-mode-container .file-pane:last-child',
      popover: {
        title: 'Destination File Pane',
        description: 'This is your destination file browser. Select where you want to copy or move files. The left and right panes work symmetrically - you can transfer files in either direction.',
        side: 'left',
      },
    },

    // Step 5: Drag & Drop (Left to Right)
    {
      element: '.easy-mode-container .file-pane:last-child .file-list',
      popover: {
        title: 'Drag & Drop Transfer',
        description: 'Simply drag files or folders from the left pane and drop them here to start a copy operation. You can also drag and drop files directly from your desktop! Select multiple files by holding Ctrl while clicking, or Shift to select a range of consecutive files.',
        side: 'top',
      },
    },

    // Step 6: Copy Button (Right to Left Arrow)
    {
      element: '.copy-controls',
      popover: {
        title: 'Copy with Buttons',
        description: 'You can also use the arrow buttons to copy files. Select files in one pane and click the corresponding arrow button to copy them to the other side.',
        side: 'top',
      },
    },

    // Step 7: Context Menu (with fake menu)
    {
      popover: {
        title: 'Context Menu Actions',
        description: 'Right-click on any file or folder in either pane to access actions: Copy, Move, Integrity Check, Rename, Delete, and more. You can also right-click on empty space to create new folders.',
        side: 'center',
        align: 'center',
        onPopoverRender: (popover) => {
          // Create fake context menu
          const fakeMenu = document.createElement('div')
          fakeMenu.className = 'tour-fake-context-menu'
          fakeMenu.style.cssText = `
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background: var(--color-bg-white);
            border: 1px solid var(--color-border-darker);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            min-width: 180px;
            z-index: 9998;
          `
          fakeMenu.innerHTML = `
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">📋 Copy</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✂️ Move</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✓ Integrity Check</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✏️ Rename</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">🗑️ Delete</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer;">📁 New Folder</div>
          `
          document.body.appendChild(fakeMenu)

          // Remove on step change
          popover._fakeMenu = fakeMenu
        },
      },
      onDeselected: (element, step, options) => {
        // Clean up fake menu
        const fakeMenu = document.querySelector('.tour-fake-context-menu')
        if (fakeMenu) {
          fakeMenu.remove()
        }
      },
    },

    // Step 8: New Alias Feature (with fake menu highlighting)
    {
      popover: {
        title: 'Create Aliases for Quick Access',
        description: 'Here\'s a powerful feature: right-click on any folder and select "New Alias" to create a shortcut to that specific folder. Once created, the alias appears in your storage location dropdown as if it were a separate location, giving you instant access to frequently used folders without navigating through the entire directory tree.',
        side: 'center',
        align: 'center',
        onPopoverRender: (popover) => {
          // Create fake context menu with New Alias highlighted
          const fakeMenu = document.createElement('div')
          fakeMenu.className = 'tour-fake-context-menu'
          fakeMenu.style.cssText = `
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            background: var(--color-bg-white);
            border: 1px solid var(--color-border-darker);
            border-radius: var(--radius-md);
            box-shadow: var(--shadow-lg);
            min-width: 180px;
            z-index: 9998;
          `
          fakeMenu.innerHTML = `
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">📋 Copy</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✂️ Move</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✓ Integrity Check</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">✏️ Rename</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">🗑️ Delete</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; border-bottom: 1px solid var(--color-border-lighter);">📁 New Folder</div>
            <div style="padding: var(--spacing-sm) 12px; cursor: pointer; background: var(--color-bg-primary-light); font-weight: bold;">🔗 New Alias</div>
          `
          document.body.appendChild(fakeMenu)
        },
      },
      onDeselected: () => {
        const fakeMenu = document.querySelector('.tour-fake-context-menu')
        if (fakeMenu) {
          fakeMenu.remove()
        }
      },
    },

    // Step 9: View Menu (highlighted)
    {
      element: '.view-dropdown-container',
      popover: {
        title: 'View Options',
        description: 'Click "View" to customize what you see in the file panes: toggle between list and grid layouts, show or hide hidden files, and switch between relative and absolute path display.',
        side: 'bottom',
      },
    },

    // Step 10: Path Display Mode (with open View menu)
    {
      element: '.view-dropdown-container',
      popover: {
        title: 'Understanding Path Display',
        description: 'The path display toggle (third option in the View menu) controls how folder paths are shown. In relative mode, you see paths relative to your current location. In absolute mode, you see the complete path from the root - this is especially useful when working with aliases, as it reveals the full path within the original storage location that the alias points to.',
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
        // Close View menu
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
        description: 'Monitor your file operations in real-time. See progress, transfer speed, and estimated time remaining. You can cancel running jobs if needed.',
        side: 'top',
      },
    },

    // Step 12: Interrupted/Failed Jobs (make visible and highlight both)
    {
      element: '.job-panel',
      popover: {
        title: 'Resume Failed Operations',
        description: 'If a job is interrupted (server shutdown) or fails, it will appear in dropdowns at the top of this panel. You can resume or restart them with a single click.',
        side: 'top',
      },
      onHighlightStarted: () => {
        // Make dropdowns temporarily visible
        const interruptedDropdown = document.querySelector('.interrupted-jobs-dropdown')
        const failedDropdown = document.querySelector('.failed-jobs-dropdown')

        if (interruptedDropdown) {
          interruptedDropdown._originalDisplay = interruptedDropdown.style.display
          interruptedDropdown.style.display = 'block'
        }
        if (failedDropdown) {
          failedDropdown._originalDisplay = failedDropdown.style.display
          failedDropdown.style.display = 'block'
        }
      },
      onDeselected: () => {
        // Restore original visibility
        const interruptedDropdown = document.querySelector('.interrupted-jobs-dropdown')
        const failedDropdown = document.querySelector('.failed-jobs-dropdown')

        if (interruptedDropdown && interruptedDropdown._originalDisplay !== undefined) {
          interruptedDropdown.style.display = interruptedDropdown._originalDisplay
        }
        if (failedDropdown && failedDropdown._originalDisplay !== undefined) {
          failedDropdown.style.display = failedDropdown._originalDisplay
        }
      },
    },

    // Step 13: Manage Remotes (highlight button)
    {
      element: '.manage-remotes-button',
      popover: {
        title: 'Managing Storage Locations',
        description: 'Click "Manage Remotes" in the header to add, edit, or remove storage providers. Motus supports all rclone-compatible services including Dropbox, Google Drive, Amazon S3, and many more.',
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
      },
    },

    // Step 15: Finale & Help
    {
      popover: {
        title: 'You\'re All Set!',
        description: 'You\'ve completed the tour! If you need help or want to see this tour again, click the Help menu in the header (between View and Expert Mode). Enjoy using Motus!',
        side: 'center',
        align: 'center',
        showButtons: ['previous', 'close'], // Show Previous and Finish buttons
        onPopoverRender: (popover, options) => {
          // Only show checkbox if --no-tour is not set
          if (!noTourConfig) {
            const checkbox = document.createElement('label')
            checkbox.style.display = 'block'
            checkbox.style.marginTop = '15px'
            checkbox.style.fontSize = '14px'
            checkbox.innerHTML = `
              <input type="checkbox" id="tour-no-show-again" checked style="margin-right: 8px;">
              Don't show this tour again on startup
            `
            popover.wrapper.querySelector('.driver-popover-description')?.parentNode.appendChild(checkbox)
          }
        },
      },
    },
  ]
}

/**
 * Show cancellation confirmation dialog
 * @param {boolean} isLastStep - Whether user is on the last step
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @returns {Promise<Object>} Result with confirmed and dontShowAgain flags
 */
export function showCancelConfirmation(isLastStep, noTourConfig) {
  return new Promise((resolve) => {
    // Create modal overlay
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay tour-cancel-overlay'
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10001;
    `

    // Create modal
    const modal = document.createElement('div')
    modal.className = 'tour-cancel-modal'
    modal.style.cssText = `
      background: var(--modal-bg, white);
      color: var(--text-color, black);
      padding: 24px;
      border-radius: 8px;
      max-width: 500px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    `

    // Build modal content
    const title = document.createElement('h3')
    title.textContent = 'Exit Guided Tour?'
    title.style.marginTop = '0'

    const message = document.createElement('p')
    message.textContent = 'Are you sure you want to exit the guided tour? You can restart it anytime from the Help menu.'

    // Checkbox (only if --no-tour is not set)
    let checkbox = null
    if (!noTourConfig) {
      checkbox = document.createElement('label')
      checkbox.style.cssText = 'display: block; margin: 15px 0; font-size: 14px;'
      checkbox.innerHTML = `
        <input type="checkbox" id="tour-cancel-no-show" style="margin-right: 8px;">
        Don't show this tour automatically on startup
      `
    }

    // Buttons
    const buttonContainer = document.createElement('div')
    buttonContainer.style.cssText = 'display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;'

    const continueBtn = document.createElement('button')
    continueBtn.textContent = 'Continue Tour'
    continueBtn.className = 'btn btn-primary'
    continueBtn.onclick = () => {
      document.body.removeChild(overlay)
      resolve({ confirmed: false })
    }

    const exitBtn = document.createElement('button')
    exitBtn.textContent = 'Exit Tour'
    exitBtn.className = 'btn btn-secondary'
    exitBtn.onclick = () => {
      const dontShowAgain = checkbox ? checkbox.querySelector('input').checked : false
      document.body.removeChild(overlay)
      resolve({ confirmed: true, dontShowAgain })
    }

    buttonContainer.appendChild(continueBtn)
    buttonContainer.appendChild(exitBtn)

    modal.appendChild(title)
    modal.appendChild(message)
    if (checkbox) {
      modal.appendChild(checkbox)
    }
    modal.appendChild(buttonContainer)
    overlay.appendChild(modal)
    document.body.appendChild(overlay)

    // Allow ESC to close (continue tour)
    const escHandler = (e) => {
      if (e.key === 'Escape') {
        document.removeEventListener('keydown', escHandler)
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay)
        }
        resolve({ confirmed: false })
      }
    }
    document.addEventListener('keydown', escHandler)
  })
}

/**
 * Start the guided tour
 * @param {Object} appStore - Pinia app store
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 */
export function startGuidedTour(appStore, noTourConfig = false) {
  const steps = getTourSteps(appStore, noTourConfig)
  let tourActive = true

  const driverObj = driver({
    showProgress: true,
    steps: steps,
    nextBtnText: 'Next',
    prevBtnText: 'Previous',
    doneBtnText: 'Finish',
    allowClose: false, // Disable default X button, use custom handling
    onPopoverRender: (popover, { config, state }) => {
      const isLastStep = state.activeIndex === steps.length - 1

      if (!isLastStep) {
        // Add custom cancel button (X) for non-final steps
        const cancelBtn = document.createElement('button')
        cancelBtn.textContent = '×'
        cancelBtn.className = 'driver-popover-close-btn'
        cancelBtn.style.cssText = `
          position: absolute;
          top: 10px;
          right: 10px;
          background: transparent;
          border: none;
          font-size: 24px;
          cursor: pointer;
          color: var(--text-color, #666);
          padding: 0;
          width: 24px;
          height: 24px;
          line-height: 20px;
          z-index: 1;
        `
        cancelBtn.onclick = async () => {
          const result = await showCancelConfirmation(isLastStep, noTourConfig)
          if (result.confirmed) {
            if (result.dontShowAgain) {
              disableTourAutoShow()
            }
            tourActive = false
            driverObj.destroy()
          }
        }
        popover.wrapper.appendChild(cancelBtn)
      }
    },
    onDestroyed: () => {
      // Clean up any remaining fake menus
      const fakeMenus = document.querySelectorAll('.tour-fake-context-menu')
      fakeMenus.forEach(menu => menu.remove())

      // Clean up cancel overlay if exists
      const overlay = document.querySelector('.tour-cancel-overlay')
      if (overlay) {
        overlay.remove()
      }

      tourActive = false
    },
    onCloseClick: () => {
      // This handles the Finish button on last step
      const checkbox = document.querySelector('#tour-no-show-again')
      if (checkbox && checkbox.checked && !noTourConfig) {
        disableTourAutoShow()
      }
      markTourCompleted()
      tourActive = false
      driverObj.destroy()
    },
  })

  // Add global ESC handler for tour
  const globalEscHandler = async (e) => {
    if (e.key === 'Escape' && tourActive) {
      // Check if cancel dialog is already open
      if (document.querySelector('.tour-cancel-overlay')) {
        return
      }

      // Check current step
      const state = driverObj.getState()
      const isLastStep = state?.activeIndex === steps.length - 1

      e.stopPropagation()
      e.preventDefault()

      const result = await showCancelConfirmation(isLastStep, noTourConfig)
      if (result.confirmed) {
        if (result.dontShowAgain) {
          disableTourAutoShow()
        }
        tourActive = false
        document.removeEventListener('keydown', globalEscHandler, true)
        driverObj.destroy()
      }
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
}
