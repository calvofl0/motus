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
      <p style="margin-bottom: 15px; color: #666;">
        Create an alias remote for: <strong>{{ targetPath }}</strong>
      </p>
      <p style="margin-bottom: 15px; color: #666;">
        Resolved to: <strong>{{ resolvedPath }}</strong>
      </p>
      <div style="margin-bottom: 15px;">
        <label style="display: block; margin-bottom: 5px; font-weight: 500;">
          Alias Remote Name:
        </label>
        <input
          ref="nameInput"
          v-model="aliasName"
          type="text"
          placeholder="Enter alias name"
          style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"
          @keydown.enter="submit"
          pattern="[a-zA-Z0-9_\-]+"
          title="Only letters, numbers, underscores, and hyphens allowed"
        />
      </div>
    </template>

    <template #footer>
      <button @click="$emit('update:modelValue', false)" class="btn-secondary">
        Cancel
      </button>
      <button @click="submit" :disabled="!isValid" class="btn-primary">
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
    if (nameInput.value) {
      nameInput.value.focus()
    }
  }
})
</script>

<style scoped>
.btn-primary {
  background: #007bff;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-right: 10px;
}

.btn-secondary:hover {
  background: #5a6268;
}
</style>
