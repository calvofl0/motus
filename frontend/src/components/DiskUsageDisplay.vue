<template>
  <div class="disk-usage-display">
    <!-- S3 root: no bucket selected, refresh not meaningful -->
    <template v-if="atS3Root">
      <span class="disk-usage-values disk-usage-na" title="Open a bucket to view disk usage">
        Usage: —
      </span>
      <button class="disk-usage-refresh" disabled title="Open a bucket to view disk usage">↻</button>
    </template>

    <!-- Normal display -->
    <template v-else>
      <span
        class="disk-usage-values"
        :title="objectCountTooltip"
      >
        <span class="disk-usage-label">Usage:</span>
        {{ formattedUsage }}<span v-if="percentage !== null" class="disk-usage-pct"> ({{ percentage }}%)</span>
        <span v-if="hasQuota" class="disk-usage-quota-sep"> · </span>
        <span v-if="hasQuota" class="disk-usage-quota">
          <span class="disk-usage-label">Quota:</span> {{ formattedQuota }}
        </span>
      </span>
      <button
        class="disk-usage-refresh"
        :class="{ 'disk-usage-spinning': isFetching }"
        :title="refreshTooltip"
        :disabled="isFetching"
        @click="handleRefresh"
        aria-label="Refresh disk usage"
      >↻</button>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useAppStore } from '../stores/app'
import { formatDiskSize, formatDateTime } from '../services/helpers'

const props = defineProps({
  remote: { type: String, default: '' },
  path:   { type: String, default: '/' },
})

const appStore = useAppStore()

// ── Data access ───────────────────────────────────────────────────────────────

const data = computed(() => appStore.getDiskUsage(props.remote, props.path))

const atS3Root   = computed(() => data.value?.at_s3_root === true)
const isFetching = computed(() => data.value?.is_computing === true)

// ── Formatting ────────────────────────────────────────────────────────────────

const formattedUsage = computed(() => {
  const b = data.value?.space_used_bytes
  return (b !== null && b !== undefined) ? formatDiskSize(b) : '—'
})

const hasQuota = computed(() => data.value?.quota_bytes != null)

const formattedQuota = computed(() => formatDiskSize(data.value?.quota_bytes))

const percentage = computed(() => {
  const used  = data.value?.space_used_bytes
  const quota = data.value?.quota_bytes
  if (used === null || used === undefined || !quota) return null
  return Math.round((used / quota) * 100)
})

const objectCountTooltip = computed(() => {
  const n = data.value?.object_count
  if (n === null || n === undefined) return ''
  return n.toLocaleString() + (n === 1 ? ' object' : ' objects')
})

const refreshTooltip = computed(() => {
  const ts = data.value?.fetched_at
  if (!ts) return 'Last fetched: never'
  return `Last fetched: ${formatDateTime(ts)}`
})

// ── Lifecycle ─────────────────────────────────────────────────────────────────

async function loadCurrent() {
  await appStore.fetchDiskUsage(props.remote, props.path)
}

async function handleRefresh() {
  await appStore.refreshDiskUsage(props.remote, props.path)
}

// When the pane navigates to a different location, cancel any in-flight fetch
// for the previous location and load the new one.
watch(
  () => [props.remote, props.path],
  async ([newRemote, newPath], [oldRemote, oldPath]) => {
    // Cancel previous fetch only if the location actually changed.
    if (oldRemote !== newRemote || oldPath !== newPath) {
      await appStore.cancelDiskUsageFetch(oldRemote, oldPath)
    }
    await loadCurrent()
  },
)

onMounted(() => { loadCurrent() })

onUnmounted(() => {
  // Cancel any in-flight fetch when the pane is destroyed.
  appStore.cancelDiskUsageFetch(props.remote, props.path)
})
</script>

<style scoped>
.disk-usage-display {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82em;
  color: var(--color-text-secondary, #666);
  white-space: nowrap;
  overflow: hidden;
}

.disk-usage-values {
  display: flex;
  align-items: center;
  gap: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.disk-usage-na {
  opacity: 0.45;
}

.disk-usage-label {
  font-weight: 600;
  margin-right: 1px;
}

.disk-usage-pct {
  opacity: 0.75;
}

.disk-usage-quota-sep {
  opacity: 0.4;
}

.disk-usage-refresh {
  background: none;
  border: none;
  cursor: pointer;
  color: inherit;
  padding: 0 2px;
  font-size: 1em;
  line-height: 1;
  opacity: 0.7;
  flex-shrink: 0;
}

.disk-usage-refresh:hover:not(:disabled) {
  opacity: 1;
}

.disk-usage-refresh:disabled {
  cursor: default;
  opacity: 0.3;
}

.disk-usage-spinning {
  display: inline-block;
  animation: disk-usage-spin 1s linear infinite;
}

@keyframes disk-usage-spin {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
