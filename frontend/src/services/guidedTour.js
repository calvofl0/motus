/**
 * Guided Tour Service for Motus
 * Uses Driver.js for step-by-step user onboarding
 */
import { driver } from 'driver.js'
import 'driver.js/dist/driver.css'
import { apiCall } from './api'
import { loadPreferences, savePreferences } from './preferences'

// Cache for preferences to avoid repeated API calls during tour
let _preferencesCache = null

/**
 * Get current tour preferences from backend
 */
async function getTourPreferences() {
  if (_preferencesCache) {
    return _preferencesCache
  }
  _preferencesCache = await loadPreferences(apiCall)
  return _preferencesCache
}

/**
 * Check if tour is disabled (should not auto-show on startup)
 */
export async function isTourDisabled() {
  const prefs = await getTourPreferences()
  return prefs.show_tour === false
}

/**
 * Disable tour auto-show on startup
 */
export async function disableTour() {
  const prefs = await getTourPreferences()
  prefs.show_tour = false
  await savePreferences(apiCall, prefs)
}

/**
 * Reset tour preferences (for testing/debugging)
 */
export async function resetTourPreferences() {
  const prefs = await getTourPreferences()
  prefs.show_tour = true
  await savePreferences(apiCall, prefs)
  _preferencesCache = null
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
<div style="margin-top: 15px; background: var(--color-bg-white); border: 1px solid var(--color-border-darker); border-radius: 6px; overflow: hidden; font-size: 13px;">
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">⬇️ Download</div>
  <div id="tour-alias-item" style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">🔗 Create Alias</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">📁 Create Folder</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">✏️ Rename</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">🗑️ Delete</div>
  <div style="padding: 8px 12px;">📊 Sort by</div>
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
        description: 'The top dropdown switches between different storage locations - cloud services, servers, or local filesystem. Below it, the path field lets you navigate to specific folders by typing a path and pressing Enter. Later we\'ll simply call these "storage locations".',
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
      },
    },

    // Step 8: New Alias Feature (with highlighted "Create Alias")
    {
      popover: {
        title: 'Create Aliases for Quick Access',
        description: `Here's a powerful feature: right-click on any folder and select "Create Alias" to create a shortcut to that specific folder. Once created, the alias appears in your storage location dropdown as if it were a separate location, giving you instant access to frequently used folders without navigating through the entire directory tree.

<div style="margin-top: 15px; background: var(--color-bg-white); border: 1px solid var(--color-border-darker); border-radius: 6px; overflow: hidden; font-size: 13px;">
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">⬇️ Download</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter); background: var(--color-bg-primary-light); font-weight: bold;">🔗 Create Alias</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">📁 Create Folder</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">✏️ Rename</div>
  <div style="padding: 8px 12px; border-bottom: 1px solid var(--color-border-lighter);">🗑️ Delete</div>
  <div style="padding: 8px 12px;">📊 Sort by</div>
</div>`,
        side: 'center',
        align: 'center',
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

    // Step 10: Path Display Mode (with open View menu and highlighted toggle)
    {
      element: '.view-dropdown-container .view-menu-item:nth-child(3)',
      popover: {
        title: 'Understanding Path Display',
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
        description: 'Monitor your file operations in real-time. See progress, transfer speed, and estimated time remaining. You can cancel running jobs if needed.',
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
  <div style="background: #fff3cd; padding: 10px; border-radius: 4px; margin-bottom: 8px; border-left: 4px solid #ffc107;">
    <strong>⚠️ Interrupted Jobs (2) ▼</strong>
    <div style="font-size: 12px; margin-top: 5px; color: #666;">Jobs stopped by server shutdown - click to resume</div>
  </div>
  <div style="background: #ffebee; padding: 10px; border-radius: 4px; border-left: 4px solid #dc3545;">
    <strong>❌ Failed Jobs (1) ▼</strong>
    <div style="font-size: 12px; margin-top: 5px; color: #666;">Jobs that encountered errors - click to view logs or retry</div>
  </div>
</div>`,
        side: 'top',
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
        doneBtnText: 'Finish',
        showButtons: ['previous', 'next'], // Previous and Finish (next) buttons
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
 * Note: Tour should be destroyed before calling this to avoid overlay conflicts
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @returns {Promise<Object>} Result with confirmed and dontShowAgain flags
 */
export function showCancelConfirmation(noTourConfig) {
  return new Promise((resolve) => {
    // Create modal overlay (driver.js tour should already be destroyed)
    const overlay = document.createElement('div')
    overlay.className = 'modal-overlay tour-cancel-overlay'
    overlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: rgba(0, 0, 0, 0.6);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 100000;
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
 * Start the guided tour from a specific step
 * @param {Object} appStore - Pinia app store
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @param {number} startStep - Step index to start from (default 0)
 * @returns {Promise<void>} Resolves when tour is completed or cancelled
 */
function startGuidedTourFromStep(appStore, noTourConfig = false, startStep = 0) {
  return new Promise((resolveTour) => {
    const steps = getTourSteps(appStore, noTourConfig)
    let tourActive = true
    let currentStepIndex = 0

    const driverObj = driver({
      showProgress: true,
      steps: steps,
      nextBtnText: 'Next',
      prevBtnText: 'Previous',
      doneBtnText: 'Finish',
      allowClose: false, // Disable default X button, use custom handling
      onPopoverRender: (popover, { config, state }) => {
        currentStepIndex = state.activeIndex || 0

        // Add custom cancel button (X) for all steps
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
          const savedStepIndex = currentStepIndex

          // Destroy tour first to remove overlay, then show confirmation
          tourActive = false
          driverObj.destroy()

          // Now show confirmation dialog without driver.js blocking it
          const result = await showCancelConfirmation(noTourConfig)
          if (result.confirmed) {
            if (result.dontShowAgain) {
              await disableTour()
            }
            // Tour cancelled, resolve the promise
            resolveTour()
          } else {
            // Continue tour - we need to start a new tour instance and return its promise
            // This resolves the current promise when the new tour completes
            const newTourPromise = startGuidedTourFromStep(appStore, noTourConfig, savedStepIndex)
            newTourPromise.then(() => resolveTour())
          }
        }
        popover.wrapper.appendChild(cancelBtn)
      },
      onDestroyed: () => {
        // Clean up cancel overlay if exists
        const overlay = document.querySelector('.tour-cancel-overlay')
        if (overlay) {
          overlay.remove()
        }

        tourActive = false
        // Only resolve if tour was completed (not cancelled via X button)
        if (!tourActive) {
          resolveTour()
        }
      },
      onCloseClick: async () => {
        // This handles the Finish button on last step
        const checkbox = document.querySelector('#tour-no-show-again')
        if (checkbox && checkbox.checked && !noTourConfig) {
          await disableTour()
        }
        tourActive = false
        driverObj.destroy()
        resolveTour()
      },
    })

    // Add global ESC handler for tour
    const globalEscHandler = async (e) => {
      if (e.key === 'Escape' && tourActive) {
        // Check if cancel dialog is already open
        if (document.querySelector('.tour-cancel-overlay')) {
          return
        }

        e.stopPropagation()
        e.preventDefault()

        const savedStepIndex = currentStepIndex

        // Destroy tour first, then show confirmation
        tourActive = false
        driverObj.destroy()

        const result = await showCancelConfirmation(noTourConfig)
        if (result.confirmed) {
          if (result.dontShowAgain) {
            await disableTour()
          }
          document.removeEventListener('keydown', globalEscHandler, true)
          resolveTour()
        } else {
          // Continue tour - start new tour instance from same step
          document.removeEventListener('keydown', globalEscHandler, true)
          const newTourPromise = startGuidedTourFromStep(appStore, noTourConfig, savedStepIndex)
          newTourPromise.then(() => resolveTour())
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

    driverObj.drive(startStep)
  })
}

/**
 * Start the guided tour from the beginning
 * @param {Object} appStore - Pinia app store
 * @param {boolean} noTourConfig - Whether --no-tour flag is set
 * @returns {Promise<void>} Resolves when tour is completed or cancelled
 */
export function startGuidedTour(appStore, noTourConfig = false) {
  return startGuidedTourFromStep(appStore, noTourConfig, 0)
}
