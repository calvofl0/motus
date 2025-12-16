<template>
  <BaseModal
    :modelValue="modelValue"
    @update:modelValue="$emit('update:modelValue', $event)"
    size="small"
  >
    <template #header>
      🔗 Create Alias
    </template>

    <template #body>
      <p class="info-text">
        Create an alias remote for: <strong>{{ targetPath }}</strong>
      </p>
      <p class="info-text">
        Resolved to: <strong>{{ displayResolvedPath }}</strong>
      </p>
      <div class="input-group">
        <label class="input-label">
          Alias Remote Name:
        </label>
        <input
          ref="nameInput"
          v-model="aliasName"
          type="text"
          placeholder="Enter alias name"
          class="alias-input"
          @keydown.enter="submit"
          pattern="[a-zA-Z0-9_\-]+"
          title="Only letters, numbers, underscores, and hyphens allowed"
        />
      </div>
    </template>

    <template #footer>
      <button @click="$emit('update:modelValue', false)" class="btn btn-secondary">
        Cancel
      </button>
      <button @click="submit" :disabled="!isValid" class="btn btn-primary">
        Create
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  targetPath: {
    type: String,
    default: ''
  },
  resolvedPath: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'create'])

const aliasName = ref('')
const nameInput = ref(null)

const isValid = computed(() => {
  return aliasName.value.trim().length > 0 && /^[a-zA-Z0-9_\-]+$/.test(aliasName.value)
})

// Format the resolved path for display
// If it resolves to a local filesystem path, show concatenated format
// If it resolves to a remote, show remote:path format
const displayResolvedPath = computed(() => {
  const path = props.resolvedPath

  if (path.includes(':')) {
    const colonIndex = path.indexOf(':')
    const beforeColon = path.substring(0, colonIndex)
    const afterColon = path.substring(colonIndex + 1)

    // Check if beforeColon is a local filesystem path (starts with /)
    if (beforeColon.startsWith('/')) {
      // Local filesystem path - show concatenated
      return beforeColon + afterColon
    }
  }

  // Otherwise return as-is
  return path
})

function submit() {
  if (!isValid.value) return
  emit('create', aliasName.value.trim())
  aliasName.value = ''
}

// Auto-focus input when modal opens
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    aliasName.value = ''
    await nextTick()
    // Use setTimeout to ensure modal is fully rendered
    setTimeout(() => {
      if (nameInput.value) {
        nameInput.value.focus()
      }
    }, 100)
  }
})
</script>

<style scoped>
.info-text {
  margin-bottom: var(--spacing-lg);
  color: var(--color-text-tertiary);
}

.input-group {
  margin-bottom: var(--spacing-lg);
}

.input-label {
  display: block;
  margin-bottom: 5px;
  font-weight: var(--font-weight-medium);
}

.alias-input {
  width: 100%;
  padding: var(--spacing-xs);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
}

.alias-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}
</style>
