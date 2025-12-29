// Shared keyboard shortcuts data - single source of truth
// Each section can be included in multiple shortcut modals

export const shortcutSections = {
  'global': {
    id: 'global',
    title: 'Global Shortcuts',
    shortcuts: [
      { keys: ['F1'], description: 'Show keyboard shortcuts' },
      { keys: ['F'], description: 'Focus file pane' },
      { keys: ['Alt', 'R'], description: 'Focus remote dropdown' },
      { keys: ['Alt', 'L'], description: 'Focus location input' },
      { keys: ['J'], description: 'Open Completed Jobs' },
      { keys: ['R'], description: 'Open Remotes Manager' },
      { keys: ['Q', 'Esc'], description: 'Quit server' }
    ]
  },

  'file-navigation': {
    id: 'file-navigation',
    title: 'File Navigation',
    note: 'File pane must be in focus (press F to focus)',
    shortcuts: [
      { keys: ['↑', '↓', '←', '→'], description: 'Navigate files and switch between panes' },
      { keys: ['Shift', '←'], description: 'Switch to left pane (with grid layout)' },
      { keys: ['Shift', '→'], description: 'Switch to right pane (with grid layout)' },
      { keys: ['Enter'], description: 'Open folder or download file' },
      { keys: ['Backspace'], description: 'Navigate to parent directory' },
      { keys: ['Esc'], description: 'Unselect all files' },
      { keys: ['S'], description: 'Sort by name and toggle sorting order' },
      { keys: ['PgUp', 'PgDn'], description: 'Scroll file list' },
      { keys: ['Home', 'End'], description: 'Scroll to top/bottom' }
    ]
  },

  'file-operations': {
    id: 'file-operations',
    title: 'File Operations',
    note: 'File pane must be in focus (press F to focus)',
    shortcuts: [
      { keys: ['Ctrl', 'Shift', '←'], description: 'Copy selected files to left pane' },
      { keys: ['Ctrl', 'Shift', '→'], description: 'Copy selected files to right pane' },
      { keys: ['Del'], description: 'Delete selected files' },
      { keys: ['A'], description: 'Create alias (when single folder is selected)' },
      { keys: ['N'], description: 'Create new folder (when 0 or 1 item selected)' }
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
      { keys: ['F1'], description: 'Show context-specific keyboard shortcuts' },
      { keys: ['↑', '↓'], description: 'Scroll modal content' },
      { keys: ['PgUp', 'PgDn'], description: 'Scroll by page' },
      { keys: ['Home', 'End'], description: 'Scroll to top/bottom' },
      { keys: ['Esc'], description: 'Close modal' }
    ]
  },

  'completed-jobs': {
    id: 'completed-jobs',
    title: 'Completed Jobs Modal',
    shortcuts: [
      { keys: ['↑', '↓'], description: 'Select job' },
      { keys: ['Enter'], description: 'View job log' },
      { keys: ['D'], description: 'Download log (when viewing job log)' },
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
      { keys: ['Alt', '<'], description: 'Back (in wizard)' },
      { keys: ['Alt', '>'], description: 'Next/Create (in wizard)' }
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
