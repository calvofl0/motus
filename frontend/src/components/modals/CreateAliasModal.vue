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
          placeholder="e.g., my_alias"
          class="alias-input"
          :class="{ 'input-error': validationError }"
          @keydown.enter="submit"
        />
        <div v-if="validationError" class="error-message">{{ validationError }}</div>
        <div v-else class="help-text">May contain letters, numbers, _, -, ., +, @, and space. Cannot start with '-' or space, or end with space.</div>
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
import { validateRemoteName } from '../../utils/remoteNameValidation'

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

const validationError = computed(() => {
  const validation = validateRemoteName(aliasName.value)
  return validation.error
})

const isValid = computed(() => {
  const validation = validateRemoteName(aliasName.value)
  return validation.isValid
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

.input-error {
  border-color: #dc3545 !important;
}

.error-message {
  color: #dc3545;
  font-size: var(--font-size-sm);
  margin-top: 4px;
}

.help-text {
  color: var(--color-text-secondary);
  font-size: var(--font-size-sm);
  margin-top: 4px;
}
</style>
