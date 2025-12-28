// Shared keyboard shortcuts data - single source of truth
// Each section can be included in multiple shortcut modals

export const shortcutSections = {
  'global': {
    id: 'global',
    title: 'Global Shortcuts',
    shortcuts: [
      { keys: ['F1'], description: 'Show keyboard shortcuts' },
      { keys: ['R'], description: 'Open Remotes Manager' },
      { keys: ['J'], description: 'Open Completed Jobs' }
    ]
  },

  'file-navigation': {
    id: 'file-navigation',
    title: 'File Navigation',
    shortcuts: [
      { keys: ['↑', '↓', '←', '→'], description: 'Navigate files and switch between panes' },
      { keys: ['Enter'], description: 'Open folder or download file' },
      { keys: ['Backspace'], description: 'Navigate to parent directory' },
      { keys: ['Esc'], description: 'Unselect all files' },
      { keys: ['Shift', '←'], description: 'Switch to left pane (or <kbd>←</kbd> in list mode)' },
      { keys: ['Shift', '→'], description: 'Switch to right pane (or <kbd>→</kbd> in list mode)' },
      { keys: ['PgUp', 'PgDn'], description: 'Scroll file list' }
    ]
  },

  'file-operations': {
    id: 'file-operations',
    title: 'File Operations',
    shortcuts: [
      { keys: ['Ctrl', 'Shift', '←'], description: 'Copy selected files to left pane' },
      { keys: ['Ctrl', 'Shift', '→'], description: 'Copy selected files to right pane' },
      { keys: ['N'], description: 'Create new folder (when 0 or 1 item selected)' },
      { keys: ['S'], description: 'Sort by name and toggle sorting order' },
      { keys: ['Del'], description: 'Delete selected files' },
      { keys: ['A'], description: 'Create alias (when single folder is selected)' }
    ]
  },

  'view-options': {
    id: 'view-options',
    title: 'View Options',
    shortcuts: [
      { keys: ['L'], description: 'Toggle layout (list/grid)' },
      { keys: ['.'], description: 'Toggle hidden files visibility' },
      { keys: ['P'], description: 'Toggle relative/absolute paths' }
    ]
  },

  'common-modal': {
    id: 'common-modal',
    title: 'Common Modal Shortcuts',
    shortcuts: [
      { keys: ['↑', '↓'], description: 'Scroll modal content' },
      { keys: ['PgUp', 'PgDn'], description: 'Scroll by page' },
      { keys: ['Home', 'End'], description: 'Scroll to top/bottom' },
      { keys: ['Esc'], description: 'Close modal' },
      { keys: ['F1'], description: 'Show context-specific keyboard shortcuts' }
    ]
  },

  'completed-jobs': {
    id: 'completed-jobs',
    title: 'Completed Jobs Modal',
    shortcuts: [
      { keys: ['↑', '↓'], description: 'Select job' },
      { keys: ['Enter'], description: 'View job log' },
      { keys: ['D', 'Delete'], description: 'Delete job log' },
      { keys: ['P'], description: 'Purge all completed jobs' }
    ]
  },

  'manage-remotes': {
    id: 'manage-remotes',
    title: 'Manage Remotes Modal',
    shortcuts: [
      { keys: ['↑', '↓'], description: 'Select remote' },
      { keys: ['Enter'], description: 'View remote configuration' },
      { keys: ['E'], description: 'Edit remote configuration' },
      { keys: ['R'], description: 'Refresh OAuth token (if OAuth remote)' },
      { keys: ['D', 'Delete'], description: 'Delete remote' },
      { keys: ['+'], description: 'Add Remote (start wizard)' },
      { keys: ['C'], description: 'Custom Remote (in template selection)' },
      { keys: ['Backspace'], description: 'Back (in wizard configuration step)' }
    ]
  }
}

// Predefined section sets for different contexts
export const sectionSets = {
  main: [
    'global',
    'file-navigation',
    'file-operations',
    'view-options',
    'common-modal',
    'completed-jobs',
    'manage-remotes'
  ],
  completedJobs: [
    'common-modal',
    'completed-jobs'
  ],
  manageRemotes: [
    'common-modal',
    'manage-remotes'
  ]
}
