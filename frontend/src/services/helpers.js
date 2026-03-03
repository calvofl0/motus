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
