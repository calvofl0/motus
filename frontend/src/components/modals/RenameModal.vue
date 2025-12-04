<template>
  <BaseModal
    v-model="isOpen"
    title="Rename"
    size="small"
    @close="handleClose"
    @confirm="handleConfirm"
  >
    <p class="label-text">Enter new name:</p>
    <input
      ref="inputRef"
      type="text"
      v-model="newName"
      class="rename-input"
      placeholder="New name..."
    />

    <template #footer>
      <button class="btn btn-secondary" @click="handleClose">
        Cancel
      </button>
      <button class="btn btn-primary" @click="handleConfirm">
        Rename
      </button>
    </template>
  </BaseModal>
</template>

<script setup>
import { ref, watch, nextTick } from 'vue'
import BaseModal from './BaseModal.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    required: true
  },
  currentName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:modelValue', 'confirm', 'cancel'])

const isOpen = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})

const newName = ref('')
const inputRef = ref(null)

// Watch for modal opening to set initial value and focus input
watch(() => props.modelValue, async (isOpen) => {
  if (isOpen) {
    newName.value = props.currentName
    await nextTick()
    // Use setTimeout to ensure modal is fully rendered
    setTimeout(() => {
      if (inputRef.value) {
        inputRef.value.focus()
        inputRef.value.select()
      }
    }, 100)
  }
})

function handleConfirm() {
  if (newName.value.trim()) {
    emit('confirm', newName.value)
    isOpen.value = false
  }
}

function handleClose() {
  emit('cancel')
  isOpen.value = false
}
</script>

<script>
import { computed } from 'vue'
export default {
  name: 'RenameModal'
}
</script>

<style scoped>
.label-text {
  margin: 0 0 var(--spacing-sm) 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-base);
}

.rename-input {
  width: 100%;
  padding: var(--spacing-sm);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-base);
}

.rename-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}
</style>
