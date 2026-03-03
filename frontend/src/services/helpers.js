/**
 * Format file size in human-readable format (base-1024, KiB/MiB/GiB/TiB labels).
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)

  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

/**
 * Format a byte count for disk-usage display (base-1024, KiB/MiB/GiB/TiB).
 * Uses integer display for values ≥ 10 in the chosen unit, one decimal place
 * below that, giving at most ~50 MiB rounding error at the GiB boundary.
 */
export function formatDiskSize(bytes) {
  if (bytes === null || bytes === undefined) return '—'
  if (bytes === 0) return '0 B'

  const k = 1024
  const sizes = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1)
  const val = bytes / Math.pow(k, i)
  const formatted = (val < 10 && i > 0) ? val.toFixed(1) : Math.round(val).toString()
  return `${formatted} ${sizes[i]}`
}

/**
 * Return the user's local IANA timezone string, falling back to 'UTC'.
 */
export function getUserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

/**
 * Format an ISO datetime string for display in the user's local timezone.
 * Returns 'never' for a falsy input.
 * Example output: "Tue 23 Dec 2025 23:33:17 CET"
 */
export function formatDateTime(isoString) {
  if (!isoString) return 'never'
  const date = new Date(isoString)
  const tz = getUserTimezone()
  const weekday  = new Intl.DateTimeFormat('en-US', { weekday: 'short', timeZone: tz }).format(date)
  const datePart = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: tz }).format(date)
  const timePart = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: tz }).format(date)
  const tzName   = new Intl.DateTimeFormat('en-US', { timeZoneName: 'short', timeZone: tz })
    .formatToParts(date).find(p => p.type === 'timeZoneName')?.value || 'UTC'
  return `${weekday} ${datePart} ${timePart} ${tzName}`
}
